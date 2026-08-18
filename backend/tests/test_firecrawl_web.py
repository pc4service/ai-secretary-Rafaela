from app.services.firecrawl_web import normalize_url, looks_like_url, extract_url, slug_from_url


def test_normalize_adds_https():
    assert normalize_url("pc4service.gr").startswith("https://")


def test_block_crm():
    try:
        normalize_url("https://crm.pc4service.gr/login")
        assert False, "should block crm"
    except ValueError:
        pass


def test_extract_url():
    assert "pc4service.gr" in (extract_url("δες το https://pc4service.gr/ υπηρεσίες") or "")


def test_slug():
    assert slug_from_url("https://www.pc4service.gr/") == "pc4service-gr"


def test_looks_like_url():
    assert looks_like_url("https://pc4service.gr")
    assert looks_like_url("pc4service.gr")
    assert not looks_like_url("τι ώρα είναι")


# --- scope / SSRF guard ---

import pytest

from app.services.firecrawl_web import normalize_url as _n


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.9/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://[::1]/",
        "http://0.0.0.0/",
        "http://intranet.local/",
        "http://wiki.internal/",
        "https://user:pass@pc4service.gr/",
        "http://pc4service.gr:8080/",
        "https://pc4service.gr/wp-admin/",
        "https://crm.pc4service.gr/",
    ],
)
def test_blocked_targets(url):
    with pytest.raises(ValueError):
        _n(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://pc4service.gr/",
        "https://www.pc4service.gr/services",
        "http://pc4service.gr:80/",
        "https://pc4service.gr:443/contact",
    ],
)
def test_public_urls_allowed(url):
    assert _n(url).startswith("http")
