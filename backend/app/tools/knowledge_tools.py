"""Haystack tools for Rafaela knowledge base (RAG / templates)."""

from haystack.tools import tool

from app.services.knowledge import format_search_for_agent, knowledge_status


@tool
def search_knowledge(query: str, top_k: int = 5) -> str:
    """
    Search company knowledge base for templates and procedures
    (email drafts, meeting agenda/notes, tone of voice, escalation, OOO, status updates).

    Use this whenever the user asks for:
    - email/letter drafts based on a template
    - meeting agenda or notes structure
    - company tone of voice / writing style
    - escalation or support process
    - out-of-office text
    - weekly status format
    - any internal playbook content

    Args:
        query: Natural language search query (Greek or English).
        top_k: Max chunks to return (default 5).
    """
    try:
        k = int(top_k) if top_k else 5
        k = max(1, min(k, 10))
        return format_search_for_agent(query, top_k=k)
    except Exception as e:
        return f"Error searching knowledge: {e}"


@tool
def knowledge_base_status() -> str:
    """Return whether the knowledge base is loaded and how many documents/chunks are available."""
    try:
        s = knowledge_status()
        if not s.get("available"):
            return "Knowledge base folder not found."
        return (
            f"Knowledge OK — dir={s.get('knowledge_dir')}, "
            f"files={s.get('file_count')}, chunks={s.get('chunk_count')}, "
            f"modes={', '.join(s.get('search_modes') or [])}."
        )
    except Exception as e:
        return f"Error reading knowledge status: {e}"
