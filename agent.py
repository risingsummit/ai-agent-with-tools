from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from config import get_settings
from tools import TOOL_REGISTRY, available_tools_snapshot


SYSTEM_PROMPT = """You are a practical autonomous deskwork assistant.
Use tools when the user asks for fresh web data, page scraping, local files, PDFs, or email.
Do not send email unless the user and app settings explicitly allow sending.
Return concise findings, cite tool outputs by name, and make next actions clear."""


@dataclass
class AgentResponse:
    answer: str
    mode: str
    tool_outputs: list[str]


def _extract_first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s)>\]]+", text)
    return match.group(0).rstrip(".,") if match else None


def _extract_file_path(text: str) -> str | None:
    quoted = re.search(r"['\"]([^'\"]+\.(?:pdf|txt|md|csv|json|log|py))['\"]", text, re.I)
    if quoted:
        return quoted.group(1)
    loose = re.search(r"([A-Za-z]:\\[^\n]+?\.(?:pdf|txt|md|csv|json|log|py)|[\w./\\ -]+\.(?:pdf|txt|md|csv|json|log|py))", text, re.I)
    return loose.group(1).strip() if loose else None


def _fallback_agent(message: str, allow_email_send: bool) -> AgentResponse:
    lower = message.lower()
    outputs: list[str] = []

    if "scrape" in lower or _extract_first_url(message):
        url = _extract_first_url(message)
        if url:
            outputs.append(TOOL_REGISTRY["scrape_url"](url))

    if any(word in lower for word in ["search", "find jobs", "job board", "competitor", "recent"]):
        query = re.sub(r"\b(search|find|jobs?|job board|competitor|recent|for|about)\b", " ", message, flags=re.I)
        query = " ".join(query.split()) or message
        outputs.append(TOOL_REGISTRY["web_search"](query, 5))

    if any(word in lower for word in ["read", "parse", "pdf", "file", "document", "report"]):
        path = _extract_file_path(message)
        if path:
            outputs.append(TOOL_REGISTRY["read_local_file"](path))

    if "email" in lower or "send" in lower or "draft" in lower:
        to_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", message)
        to = to_match.group(0) if to_match else "recipient@example.com"
        subject = "Follow-up from AI Agent"
        body = "Here is the requested follow-up. Please review and customize this draft before sending."
        outputs.append(
            TOOL_REGISTRY["send_email_gmail"](
                to=to,
                subject=subject,
                body=body,
                allow_send=allow_email_send,
                confirmation="SEND" if allow_email_send and "send" in lower else "",
            )
        )

    if not outputs:
        tool_names = ", ".join(tool["name"] for tool in available_tools_snapshot())
        answer = (
            "I can help with web search, website scraping, local file reading, PDF parsing, "
            f"and Gmail drafting/sending. Available tools: {tool_names}."
        )
        return AgentResponse(answer=answer, mode="fallback", tool_outputs=[])

    answer = (
        "I handled the request with the available local tools. Review the tool output below, "
        "then ask for a summary, comparison, or approved email send when you are ready."
    )
    return AgentResponse(answer=answer, mode="fallback", tool_outputs=outputs)


def _build_langgraph_agent(allow_email_send: bool):
    from langchain_core.messages import SystemMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.prebuilt import ToolNode, tools_condition

    @tool
    def web_search(query: str, max_results: int = 5) -> str:
        """Search the web for real-time information."""
        return TOOL_REGISTRY["web_search"](query, max_results)

    @tool
    def scrape_url(url: str) -> str:
        """Scrape title, headings, links, and text from a website."""
        return TOOL_REGISTRY["scrape_url"](url)

    @tool
    def read_local_file(path: str) -> str:
        """Read a workspace text file or PDF."""
        return TOOL_REGISTRY["read_local_file"](path)

    @tool
    def parse_pdf(path: str) -> str:
        """Extract text from a PDF inside the workspace."""
        return TOOL_REGISTRY["parse_pdf"](path)

    @tool
    def send_email_gmail(to: str, subject: str, body: str, confirmation: str = "") -> str:
        """Draft or send a Gmail message. Sending requires confirmation='SEND' and app approval."""
        return TOOL_REGISTRY["send_email_gmail"](
            to=to,
            subject=subject,
            body=body,
            allow_send=allow_email_send,
            confirmation=confirmation,
        )

    settings = get_settings()
    llm = ChatOpenAI(model=settings.openai_model, temperature=0).bind_tools(
        [web_search, scrape_url, read_local_file, parse_pdf, send_email_gmail]
    )

    def call_model(state: MessagesState) -> dict[str, Any]:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode([web_search, scrape_url, read_local_file, parse_pdf, send_email_gmail]))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    graph.add_edge("agent", END)
    return graph.compile()


def run_agent(message: str, history: list[dict[str, str]] | None = None, allow_email_send: bool = False) -> AgentResponse:
    settings = get_settings()
    if not settings.openai_api_key:
        return _fallback_agent(message, allow_email_send)

    try:
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    except ImportError:
        return _fallback_agent(message, allow_email_send)

    try:
        graph = _build_langgraph_agent(allow_email_send)
        messages = []
        for item in history or []:
            if item.get("role") == "user":
                messages.append(HumanMessage(content=item.get("content", "")))
            elif item.get("role") == "assistant":
                messages.append(AIMessage(content=item.get("content", "")))
        messages.append(HumanMessage(content=message))
        result = graph.invoke({"messages": messages})
    except Exception as exc:
        fallback = _fallback_agent(message, allow_email_send)
        fallback.answer = f"LangGraph was unavailable for this run, so I used the local fallback. Details: {exc}"
        return fallback

    final_messages = result.get("messages", [])
    final_answer = ""
    tool_outputs: list[str] = []
    for msg in final_messages:
        if isinstance(msg, ToolMessage):
            tool_outputs.append(str(msg.content))
        if isinstance(msg, AIMessage) and msg.content:
            final_answer = str(msg.content)

    return AgentResponse(answer=final_answer or "Done.", mode="langgraph", tool_outputs=tool_outputs)
