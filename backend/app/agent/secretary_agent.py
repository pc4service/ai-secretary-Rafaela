"""
Haystack-based AI Secretary Agent – Rafaela
"""

from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from haystack.utils import Secret
from typing import List, Optional, Dict, Any
import structlog

from app.core.config import settings

logger = structlog.get_logger()

SECRETARY_SYSTEM_PROMPT = """
You are "Rafaela", a highly competent, discreet and professional AI Executive Secretary (female character).

### Role
You assist the user with calendar management, email handling, task organization, meeting preparation, research and daily administrative work. You speak Greek when the user writes in Greek and English otherwise. Be concise, proactive, warm and reliable.

### Core Principles
1. Privacy First & GDPR Compliance
   - Never process more data than necessary.
   - Always respect the user’s current consents and retention settings.
   - Never use user data for training or any purpose other than assisting the current user.
   - You can READ emails but you can NEVER send or modify emails — no send-email capability is available to you. If asked to send an email, politely explain that mail is read-only and offer to draft the text for the user to send manually.
   - Before any other write action (create/update/delete calendar event), you MUST use the propose_* tools that create a pending action. Never create anything directly.
   - If the user requests data deletion or export, immediately call the corresponding GDPR tool.

2. Confirmation for Write Actions (Human-in-the-loop)
   - Read operations can be performed freely (list emails, list calendar).
   - For ANY action that changes external state, use the propose_* tools (ms_propose_create_event, google_propose_create_event).
   - These tools return a [PENDING_ACTION:id] marker. The UI will show Approve / Reject buttons.
   - Never claim that an event was created until the user has approved it.

3. Tool Usage
   - Use the available tools when needed.
   - Prefer the least-privilege tool and the minimal amount of data.
   - After using a tool, summarize the result clearly for the user.

4. Communication Style
   - Professional, calm, efficient, warm and friendly (female voice).
   - Structure longer answers with short paragraphs or bullet points.
   - When proposing actions, explain clearly what will happen after approval.
   - Always confirm time zones when dealing with calendar.

5. Safety & Boundaries
   - Do not access or expose special category data without additional explicit consent.
   - If a request could violate privacy or law, politely refuse and explain why.
   - Log every significant action through the audit system (via tools).

6. Proactivity
   - When appropriate, suggest useful next steps.
   - Keep track of open loops and gently remind the user when relevant.

You are not a general chatbot. Stay focused on secretary and productivity tasks. If the user asks something completely outside your role, politely redirect.
"""


@tool
def get_current_datetime(timezone: str = "Europe/Athens") -> str:
    """Return the current date and time in the given timezone."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        now = datetime.now(ZoneInfo(timezone))
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def research_with_firecrawl(query: str, max_results: int = 3) -> str:
    """Research a topic using Firecrawl. Returns clean markdown summaries."""
    if not settings.FIRECRAWL_API_KEY:
        return "Firecrawl API key is not configured."
    try:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
        result = app.scrape_url(
            f"https://www.google.com/search?q={query}",
            params={"formats": ["markdown"]},
        )
        markdown = result.get("markdown", "")[:3000]
        return f"Research results for '{query}':\n\n{markdown}"
    except Exception as e:
        logger.exception("Firecrawl error")
        return f"Research failed: {str(e)}"


@tool
def gdpr_export_user_data(user_id: str = "current") -> str:
    """Export all data belonging to the current user (GDPR Right of Access / Portability)."""
    return (
        f"[GDPR] Data export requested for user '{user_id}'. "
        "In production this returns a downloadable JSON archive."
    )


@tool
def gdpr_delete_user_data(user_id: str = "current", confirm: bool = False) -> str:
    """Delete all data belonging to the current user (GDPR Right to Erasure). Requires confirm=True."""
    if not confirm:
        return "Please confirm deletion by calling this tool again with confirm=True."
    return (
        f"[GDPR] All data for user '{user_id}' has been scheduled for permanent deletion."
    )


def create_secretary_agent(
    tools: Optional[List] = None,
    streaming_callback=None,
) -> Agent:
    if tools is None:
        # NOTE: send-email tools are intentionally NOT registered (read-only mail).
        # Calendar writes remain as propose-and-approve (human-in-the-loop).
        from app.tools.ms365_tools import (
            ms_list_emails,
            ms_list_calendar,
            ms_propose_create_event,
        )
        from app.tools.google_tools import (
            google_list_emails,
            google_list_calendar,
            google_propose_create_event,
        )

        tools = [
            get_current_datetime,
            research_with_firecrawl,
            gdpr_export_user_data,
            gdpr_delete_user_data,
            ms_list_emails,
            ms_list_calendar,
            ms_propose_create_event,
            google_list_emails,
            google_list_calendar,
            google_propose_create_event,
        ]

    if not settings.OPENAI_API_KEY and settings.LLM_PROVIDER == "openai":
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    chat_generator = OpenAIChatGenerator(
        api_key=Secret.from_token(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else Secret.from_env_var("OPENAI_API_KEY"),
        model=settings.LLM_MODEL,
        api_base_url=settings.OPENAI_BASE_URL,
    )

    agent = Agent(
        chat_generator=chat_generator,
        tools=tools,
        system_prompt=SECRETARY_SYSTEM_PROMPT,
        streaming_callback=streaming_callback,
    )
    return agent


async def run_agent(messages: List[ChatMessage], agent: Optional[Agent] = None) -> Dict[str, Any]:
    if agent is None:
        agent = create_secretary_agent()
    result = agent.run(messages=messages)
    return result
