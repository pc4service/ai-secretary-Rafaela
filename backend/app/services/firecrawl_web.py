"""Firecrawl helpers: scrape a public URL to markdown (no login/CRM)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import structlog

from app.core.config import settings

logger = structlog.get_logger()

_BLOCKED_HOST_PARTS = ("crm.", "localhost", "127.0.0.1", "0.0.0.0")
# Internal-only namespaces that must never be fetched.
_BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localdomain", ".lan", ".home.arpa")
_BLOCKED_PATHS = (
    "/wp-admin", "/login", "/crm", "/wp-login", "/admin", "/administrator",
    "/signin", "/sign-in", "/webmail", "/phpmyadmin", "/dashboard",
)
# Only ordinary web ports — an odd port usually means an internal service.
_ALLOWED_PORTS = (80, 443)
_MAX_CHARS = 14000


def _reject_private_address(host: str) -> None:
    """
    Block IP literals that point back at our own network.

    Firecrawl fetches the page from its own infrastructure, so this is scope
    enforcement rather than a complete SSRF defence — a hostname resolving to a
    private address still passes. Keep the guard here anyway: it is what stops
    an obvious `http://10.0.0.5/` from being treated as a public company site.
    """
    import ipaddress

    candidate = host.strip("[]")  # IPv6 literals arrive bracketed
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return  # not an IP literal — nothing to check here

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # includes 169.254.169.254 cloud metadata
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise ValueError(f"Blocked non-public address: {host}")


def normalize_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise ValueError("Empty URL")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL: {raw}")
    if parsed.username or parsed.password:
        raise ValueError("Blocked URL with embedded credentials")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError(f"Invalid URL: {raw}")
    if any(p in host for p in _BLOCKED_HOST_PARTS):
        raise ValueError(f"Blocked host (login/private): {host}")
    if any(host.endswith(s) for s in _BLOCKED_HOST_SUFFIXES):
        raise ValueError(f"Blocked internal host: {host}")
    _reject_private_address(host)

    try:
        port = parsed.port
    except ValueError:
        raise ValueError(f"Invalid port in URL: {raw}")
    if port is not None and port not in _ALLOWED_PORTS:
        raise ValueError(f"Blocked non-web port: {port}")

    path = (parsed.path or "").lower()
    if any(path.startswith(p) or p in path for p in _BLOCKED_PATHS):
        raise ValueError(f"Blocked path (login/admin): {parsed.path}")
    return url


def looks_like_url(text: str) -> bool:
    t = (text or "").strip()
    if re.search(r"https?://", t, re.I):
        return True
    return bool(re.search(r"\b[\w-]+\.[a-z]{2,}(/|\b)", t, re.I))


def extract_url(text: str) -> Optional[str]:
    m = re.search(r"https?://[^\s)>\"]+", text or "", re.I)
    if m:
        return m.group(0).rstrip(".,;)]")
    m = re.search(r"\b([\w-]+\.[a-z]{2,}(?:/[^\s]*)?)", text or "", re.I)
    if m:
        return m.group(1).rstrip(".,;)]")
    return None


def slug_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "site").lower()
    host = re.sub(r"^www\.", "", host)
    slug = re.sub(r"[^a-z0-9]+", "-", host).strip("-")
    return slug or "site"


def _extract_markdown(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("markdown", "content"):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val
        data = result.get("data")
        if isinstance(data, dict):
            return _extract_markdown(data)
        if isinstance(data, list) and data:
            parts = [_extract_markdown(item) for item in data]
            return "\n\n---\n\n".join(p for p in parts if p)
    # firecrawl-py objects
    md = getattr(result, "markdown", None)
    if isinstance(md, str) and md.strip():
        return md
    data = getattr(result, "data", None)
    if data is not None and data is not result:
        return _extract_markdown(data)
    return ""


def _scrape_one(app, url: str) -> str:
    last_err = None
    attempts = (
        lambda: app.scrape_url(url, params={"formats": ["markdown"]}),
        lambda: app.scrape_url(url, formats=["markdown"]),
        lambda: app.scrape(url, formats=["markdown"]),
        lambda: app.scrape_url(url),
    )
    for fn in attempts:
        try:
            md = _extract_markdown(fn())
            if md.strip():
                return md
        except TypeError as e:
            last_err = e
            continue
        except Exception as e:
            last_err = e
            logger.warning("firecrawl_scrape_try_failed", url=url, error=str(e)[:200])
            continue
    if last_err:
        raise last_err
    return ""


def scrape_public_url(url: str) -> Dict[str, Any]:
    """Scrape one public page. Returns {url, title, markdown}."""
    if not settings.FIRECRAWL_API_KEY:
        raise ValueError("FIRECRAWL_API_KEY is not configured")
    url = normalize_url(url)
    from firecrawl import FirecrawlApp

    app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
    markdown = _scrape_one(app, url).strip()
    if not markdown:
        raise ValueError(f"Firecrawl returned empty content for {url}")
    if len(markdown) > _MAX_CHARS:
        markdown = markdown[:_MAX_CHARS] + "\n\n…(truncated)"
    title = url
    m = re.search(r"^#\s+(.+)$", markdown, re.M)
    if m:
        title = m.group(1).strip()
    return {"url": url, "title": title, "markdown": markdown}


def _same_host_links(base_url: str, markdown: str, limit: int) -> List[str]:
    host = (urlparse(base_url).hostname or "").lower().removeprefix("www.")
    found: List[str] = []
    seen = {normalize_url(base_url)}
    for href in re.findall(r"https?://[^\s)>\"]+", markdown, re.I):
        href = href.rstrip(".,;)]")
        try:
            n = normalize_url(href)
        except ValueError:
            continue
        h = (urlparse(n).hostname or "").lower().removeprefix("www.")
        if h != host or n in seen:
            continue
        seen.add(n)
        found.append(n)
        if len(found) >= limit:
            break
    # common marketing paths if few links extracted
    if len(found) < limit:
        for path in ("/υπηρεσίες", "/ypiresies", "/services", "/επικοινωνία", "/epikoinonia", "/contact"):
            extra = urljoin(base_url if base_url.endswith("/") else base_url + "/", path.lstrip("/"))
            try:
                n = normalize_url(extra)
            except ValueError:
                continue
            if n not in seen:
                seen.add(n)
                found.append(n)
            if len(found) >= limit:
                break
    return found[:limit]


def scrape_site(url: str, max_pages: int = 1) -> Dict[str, Any]:
    """Scrape homepage (and optionally a few same-host public pages)."""
    first = scrape_public_url(url)
    pages = [first]
    extra = max(1, min(int(max_pages or 1), 6)) - 1
    if extra > 0:
        for link in _same_host_links(first["url"], first["markdown"], extra):
            try:
                pages.append(scrape_public_url(link))
            except Exception as e:
                logger.info("firecrawl_extra_page_skipped", url=link, error=str(e)[:160])
    combined = []
    for p in pages:
        combined.append(f"# {p['title']}\n\n**Source:** {p['url']}\n\n{p['markdown']}")
    body = "\n\n---\n\n".join(combined)
    if len(body) > _MAX_CHARS * 2:
        body = body[: _MAX_CHARS * 2] + "\n\n…(truncated)"
    return {
        "url": first["url"],
        "title": first["title"],
        "pages": len(pages),
        "markdown": body,
        "page_urls": [p["url"] for p in pages],
    }


def knowledge_document(scraped: Dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slug_from_url(scraped["url"])
    tags = f"company, website, {slug}"
    return (
        f"# Εταιρικό site: {scraped['title']}\n\n"
        f"**Tags:** {tags}\n"
        f"**Source:** {scraped['url']}\n"
        f"**Fetched:** {now} (public Firecrawl scrape)\n\n"
        "Μόνο δημόσιο περιεχόμενο. Όχι CRM, login ή προσωπικά δεδομένα.\n\n"
        f"{scraped['markdown']}\n"
    )
