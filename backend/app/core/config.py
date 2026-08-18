from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Rafaela – AI Secretary"
    APP_VERSION: str = "0.1.0-trial"
    ENVIRONMENT: str = "development"  # development | trial | production
    DEBUG: bool = True
    DRY_RUN: bool = True  # When True, write actions are simulated

    # API
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # LLM (primary OpenAI-compatible slot — official OpenAI when OPENAI_BASE_URL is empty)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None  # empty = https://api.openai.com/v1
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_PROVIDER: str = "openai"  # openai | anthropic (anthropic path reserved)
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: float = 20.0

    # --- Multi-provider failover (tokens / credits resilience) ---
    # Explicit chain (optional). Format:
    #   name|model|base_url|ENV_VAR_NAME;name2|model2|base_url2|ENV_VAR2
    # Empty base_url = official OpenAI. Hops without a real key are skipped.
    # Example:
    #   openai|gpt-4o-mini||OPENAI_API_KEY;opencode|kimi-k3|https://opencode.ai/zen/go/v1|OPENCODE_API_KEY
    LLM_FAILOVER_CHAIN: str = ""

    # OpenCode / Zen slot (optional backup; do not put this key in OPENAI_API_KEY)
    OPENCODE_API_KEY: Optional[str] = None
    OPENCODE_BASE_URL: str = "https://opencode.ai/zen/go/v1"
    OPENCODE_MODEL: str = "kimi-k3"

    # xAI / Grok slot (auto-added to failover when key is set)
    XAI_API_KEY: Optional[str] = None
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    XAI_MODEL: str = "grok-3-mini"

    # Official OpenAI fallback slot (different key from OPENAI_API_KEY when primary is a proxy)
    OPENAI_FALLBACK_API_KEY: Optional[str] = None
    OPENAI_FALLBACK_MODEL: str = "gpt-4o-mini"

    # ChatGPT / Codex OAuth (Sign in with ChatGPT) — no Platform API key required
    OPENAI_OAUTH_REDIRECT_URI: str = "http://localhost:1455/auth/callback"
    OPENAI_OAUTH_MODEL: str = "gpt-5.5"

    # Firecrawl
    FIRECRAWL_API_KEY: Optional[str] = None

    # Microsoft 365
    MS_CLIENT_ID: Optional[str] = None
    MS_CLIENT_SECRET: Optional[str] = None
    MS_TENANT_ID: str = "common"
    MS_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/microsoft/callback"
    MS_SCOPES: List[str] = [
        "User.Read",
        "Mail.Read",
        # Read-only mail by design: Mail.ReadWrite/Mail.Send intentionally omitted.
        "Calendars.Read",
        "Calendars.ReadWrite",
        "Files.Read",
        # offline_access/openid/profile are added automatically by MSAL (reserved scopes)
    ]

    # Google
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    # Identity login (Sign in with Google) – separate from Gmail/Calendar integration
    GOOGLE_LOGIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/login/google/callback"
    MS_LOGIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/login/microsoft/callback"
    # Frontend URL after successful login
    FRONTEND_URL: str = "http://localhost:3000"
    # Cookie
    COOKIE_SECURE: bool = False  # True behind HTTPS
    COOKIE_NAME: str = "rafaela_session"
    GOOGLE_SCOPES: List[str] = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/gmail.readonly",
        # gmail.send / gmail.compose intentionally omitted (read-only mail).
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://secretary:secretary@db:5432/secretary"
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    ENCRYPTION_KEY: Optional[str] = None  # Fernet key for token encryption
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    # Refuse the anonymous "demo-user" fallback on user-scoped endpoints.
    # Always on in production — see auth_required below.
    REQUIRE_AUTH: bool = False

    # GDPR
    DEFAULT_RETENTION_DAYS: int = 30
    AUDIT_LOG_RETENTION_DAYS: int = 365

    # Knowledge / RAG
    # Host path is mounted in docker-compose; container default /knowledge
    KNOWLEDGE_DIR: str = "/knowledge"
    QDRANT_URL: Optional[str] = None  # e.g. http://qdrant:6333 — optional
    KNOWLEDGE_COLLECTION: str = "rafaela_knowledge"
    KNOWLEDGE_TOP_K: int = 5
    KNOWLEDGE_EMBED_MODEL: str = "text-embedding-3-small"

    @property
    def auth_required(self) -> bool:
        """
        Whether user-scoped endpoints may fall back to the demo user.

        Production never allows it, regardless of REQUIRE_AUTH: an anonymous
        caller would otherwise act as demo-user and reach that account's
        conversations and OAuth tokens.
        """
        return self.REQUIRE_AUTH or self.ENVIRONMENT == "production"


settings = Settings()

# Note: login redirect URIs (identity) – can differ from integration redirects
# Added as optional attributes via model - we patch Settings class
