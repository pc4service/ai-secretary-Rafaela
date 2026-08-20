"""Haystack tools: scrape a public website and propose saving it to knowledge/."""

from haystack.tools import tool

from app.services.pending_actions import create_pending_action
from app.tools.ms365_tools import _run

_PREVIEW_CHARS = 1500


def _content_preview(content: str) -> str:
    """
    Show what will actually be written, so approving is informed consent and
    not a size estimate. Long pages are trimmed with the remainder counted.
    """
    body = (content or "").strip()
    shown = body[:_PREVIEW_CHARS]
    hidden = len(body) - len(shown)
    lines = ["--- Περιεχόμενο προς αποθήκευση ---", shown]
    if hidden > 0:
        lines.append(f"… (+{hidden} χαρακτήρες ακόμα)")
    return "\n".join(lines)


@tool
def firecrawl_scrape_website(url: str, max_pages: int = 1) -> str:
    """
    Read a PUBLIC website with Firecrawl and return markdown in this chat only.
    Does NOT save to the knowledge base. Use for company sites like https://pc4service.gr/
    Do not scrape CRM, login, admin, or private pages.
    max_pages: 1 = only this URL; 2–6 = also a few same-host public pages.
    """
    try:
        from app.services.firecrawl_web import scrape_site
        from app.services.untrusted import DATA_NOT_INSTRUCTIONS, wrap_untrusted

        data = scrape_site(url, max_pages=max_pages)
        preview = data["markdown"][:4000]
        extra = ""
        if len(data["markdown"]) > 4000:
            extra = "\n\n…(κομμένο στην προεπισκόπηση· για μόνιμη αποθήκευση χρησιμοποίησε firecrawl_propose_save_to_knowledge)"
        pages = ", ".join(data.get("page_urls") or [data["url"]])
        return (
            f"Δημόσιο περιεχόμενο από {data['url']} ({data['pages']} σελίδα/ες: {pages}). "
            f"Δεν αποθηκεύτηκε στο knowledge.\n\n"
            + wrap_untrusted(preview + extra, DATA_NOT_INSTRUCTIONS)
        )
    except Exception as e:
        return f"Error scraping website: {e}"


@tool
def firecrawl_propose_save_to_knowledge(
    url: str,
    max_pages: int = 3,
    user_id: str = "demo-user",
) -> str:
    """
    Scrape a PUBLIC company website and propose saving it as knowledge/*.md + Qdrant index.
    Creates a pending action — the user must Approve before any file is written.
    Never scrape CRM/login/admin. Typical use: https://pc4service.gr/
    """
    try:
        from app.services.agent_context import current_agent_user
        from app.services.firecrawl_web import (
            scrape_site,
            knowledge_document,
            slug_from_url,
        )

        # Resolve here, not inside _inner(): that runs in a worker thread.
        uid = current_agent_user(user_id)

        async def _inner():
            data = scrape_site(url, max_pages=max_pages)
            filename = f"website-{slug_from_url(data['url'])}.md"
            content = knowledge_document(data)
            desc = (
                f"Αποθήκευση δημόσιου site στο knowledge/\n"
                f"URL: {data['url']}\n"
                f"Αρχείο: {filename}\n"
                f"Σελίδες: {data['pages']} ({', '.join(data.get('page_urls') or [])})\n"
                f"Μέγεθος: ~{len(content)} χαρακτήρες\n\n"
                f"{_content_preview(content)}"
            )
            action = await create_pending_action(
                user_id=uid,
                action_type="knowledge_save_page",
                payload={
                    "filename": filename,
                    "content": content,
                    "url": data["url"],
                    "pages": data["pages"],
                },
                description=desc,
            )
            return (
                f"[PENDING_ACTION:{action.id}]\n"
                f"Πρότεινα να αποθηκευτεί το δημόσιο περιεχόμενο του site ως {filename} "
                f"και να ενημερωθεί το Qdrant. Ενέκρινε ή απόρριψε.\n\n{desc}"
            )

        return _run(_inner())
    except Exception as e:
        return f"Error proposing knowledge save: {e}"
