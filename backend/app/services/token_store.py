"""
Encrypted OAuth token persistence in PostgreSQL.
"""

import asyncio
import base64
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import User, OAuthToken, AsyncSessionLocal
from app.core.security import encrypt_token, decrypt_token
import structlog

logger = structlog.get_logger()


class ReconnectRequired(Exception):
    """Provider credentials are missing or revoked — the user must reconnect."""


async def ensure_user(session: AsyncSession, user_id: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(id=user_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def save_oauth_token(
    user_id: str,
    provider: str,
    token_data: Dict[str, Any],
    expires_in: Optional[int] = None,
    scopes: Optional[str] = None,
) -> None:
    """Encrypt and store (or update) OAuth tokens for a provider."""
    async with AsyncSessionLocal() as session:
        await ensure_user(session, user_id)

        encrypted = encrypt_token(json.dumps(token_data))
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        result = await session.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.encrypted_data = encrypted
            existing.expires_at = expires_at
            existing.updated_at = datetime.now(timezone.utc)
            if scopes is not None:
                existing.scopes = scopes
        else:
            token = OAuthToken(
                user_id=user_id,
                provider=provider,
                encrypted_data=encrypted,
                expires_at=expires_at,
                scopes=scopes,
            )
            session.add(token)

        await session.commit()
        logger.info("oauth_token_saved", user_id=user_id, provider=provider)


async def get_oauth_token(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    """Retrieve and decrypt OAuth tokens."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        try:
            return json.loads(decrypt_token(row.encrypted_data))
        except Exception as e:
            logger.error("token_decrypt_failed", error=str(e), user_id=user_id, provider=provider)
            return None


async def delete_oauth_token(user_id: str, provider: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider,
            )
        )
        await session.commit()
        logger.info("oauth_token_deleted", user_id=user_id, provider=provider)


async def is_connected(user_id: str, provider: str) -> bool:
    token = await get_oauth_token(user_id, provider)
    return token is not None


def _scopes_from_jwt(access_token: str) -> list[str]:
    """Read granted scopes from the JWT 'scp' claim (no signature check —
    used only for display/drift detection; Microsoft Graph enforces for real)."""
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return str(claims.get("scp", "")).split()
    except Exception:
        return []


async def get_fresh_openai_tokens(user_id: str) -> Dict[str, Any]:
    """Valid ChatGPT OAuth access token, refreshing when expired."""
    from app.services.openai_oauth import refresh_access_token

    skew = timedelta(minutes=5)
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == "openai",
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise ReconnectRequired("OpenAI / ChatGPT is not connected")
        try:
            data = json.loads(decrypt_token(row.encrypted_data))
        except Exception as e:
            raise ReconnectRequired(f"OpenAI token unreadable: {e}") from e

        if row.expires_at and row.expires_at - skew > now and data.get("access_token"):
            return data

        refresh = data.get("refresh_token")
        if not refresh:
            await session.delete(row)
            await session.commit()
            raise ReconnectRequired("OpenAI session expired — connect ChatGPT again")

        try:
            fresh = await refresh_access_token(refresh)
        except Exception as e:
            await session.delete(row)
            await session.commit()
            raise ReconnectRequired("OpenAI refresh failed — connect ChatGPT again") from e

        data["access_token"] = fresh["access_token"]
        if fresh.get("refresh_token"):
            data["refresh_token"] = fresh["refresh_token"]
        row.encrypted_data = encrypt_token(json.dumps(data))
        if fresh.get("expires_in"):
            row.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(fresh["expires_in"]))
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return data


async def get_fresh_microsoft_tokens(user_id: str) -> Dict[str, Any]:
    """Return Microsoft tokens with a valid access token — no OAuth login needed
    after the first connect.

    Professional token lifecycle:
    1. Access token still valid (5-min skew) -> return as-is.
    2. Tokens stored as an MSAL SerializableTokenCache (enterprise path, set at
       login) -> MSAL acquire_token_silent: serves the cached AT or redeems the
       cached RT, handling rotation internally; the updated cache is persisted.
    3. Legacy tokens (plain RT) -> redeem the refresh token and PERSIST the
       rotated set (Microsoft RTs are rolling: each redemption invalidates the
       previous one). The next OAuth login upgrades the record to the cache.
    4. Everything rejected (invalid_grant = revoked/expired) -> drop the stale
       record and raise ReconnectRequired so the UI can ask for reconnection.
    """
    from app.services.microsoft import (  # local imports: avoid circulars
        refresh_microsoft_access_token,
        silent_acquire_from_cache,
    )

    skew = timedelta(minutes=5)
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == "microsoft",
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise ReconnectRequired("Microsoft 365 is not connected")

        data = json.loads(decrypt_token(row.encrypted_data))

        expires_at = row.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if data.get("access_token") and expires_at and expires_at > now + skew:
            return data

        # --- Enterprise path: MSAL-managed cache (set at OAuth login) ---
        if data.get("msal_cache"):
            silent_result, new_cache = await asyncio.to_thread(
                silent_acquire_from_cache, data["msal_cache"]
            )
            if silent_result:
                new_data = {**data, "access_token": silent_result["access_token"]}
                if new_cache:
                    new_data["msal_cache"] = new_cache
                row.encrypted_data = encrypt_token(json.dumps(new_data))
                if silent_result.get("expires_in"):
                    row.expires_at = now + timedelta(seconds=int(silent_result["expires_in"]))
                if silent_result.get("scope"):
                    row.scopes = silent_result["scope"]
                row.updated_at = now
                await session.commit()
                logger.info("microsoft_token_refreshed_via_cache", user_id=user_id)
                return new_data
            if new_cache:  # cache changed (e.g. RT dropped) even though no token
                row.encrypted_data = encrypt_token(json.dumps({**data, "msal_cache": new_cache}))
                await session.commit()
            logger.warning("microsoft_silent_acquire_failed", user_id=user_id)

        # --- Legacy path: plain refresh-token redemption ---
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            await session.delete(row)
            await session.commit()
            raise ReconnectRequired("Microsoft 365 session expired — please reconnect in Settings")

        # MSAL is synchronous — keep it off the event loop.
        refreshed = await asyncio.to_thread(refresh_microsoft_access_token, refresh_token)

        if "error" in refreshed:
            if refreshed.get("error") == "invalid_grant":
                await session.delete(row)
                await session.commit()
                logger.info("microsoft_refresh_token_revoked", user_id=user_id)
                raise ReconnectRequired("Microsoft 365 connection was revoked — please reconnect in Settings")
            raise RuntimeError(refreshed.get("error_description", refreshed["error"]))

        new_data = {
            **data,
            "access_token": refreshed["access_token"],
            "refresh_token": refreshed.get("refresh_token", refresh_token),
        }
        row.encrypted_data = encrypt_token(json.dumps(new_data))
        if refreshed.get("expires_in"):
            row.expires_at = now + timedelta(seconds=int(refreshed["expires_in"]))
        if refreshed.get("scope"):
            row.scopes = refreshed["scope"]
        row.updated_at = now
        await session.commit()
        logger.info("microsoft_token_refreshed", user_id=user_id)
        return new_data


async def get_token_info(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    """Non-secret metadata about a stored token: granted scopes + expiry.

    Falls back to decoding the access token JWT when the scopes column was
    never populated (tokens stored before scope tracking existed).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None

        scopes = row.scopes.split() if row.scopes else None
        if scopes is None:
            try:
                data = json.loads(decrypt_token(row.encrypted_data))
                scopes = _scopes_from_jwt(data.get("access_token", "")) or None
            except Exception:
                scopes = None

        expires_at = row.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return {
            "scopes": scopes,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
