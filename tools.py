from __future__ import annotations

import base64
import html
import json
import mimetypes
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from config import get_settings


USER_AGENT = "AI-Agent-With-Tools/1.0 (+local research assistant)"
REQUEST_TIMEOUT = 15
MAX_TEXT_CHARS = 12000


@dataclass
class ToolResult:
    tool: str
    ok: bool
    summary: str
    data: dict[str, Any]

    def to_markdown(self) -> str:
        status = "Success" if self.ok else "Issue"
        details = json.dumps(self.data, indent=2, ensure_ascii=False)
        return f"**{self.tool} - {status}**\n\n{self.summary}\n\n```json\n{details}\n```"


def _result(tool: str, ok: bool, summary: str, **data: Any) -> str:
    return ToolResult(tool=tool, ok=ok, summary=summary, data=data).to_markdown()


def _safe_workspace_path(path_text: str) -> Path:
    settings = get_settings()
    requested = Path(path_text).expanduser()
    if not requested.is_absolute():
        requested = settings.workspace_root / requested
    resolved = requested.resolve()
    if not resolved.is_relative_to(settings.workspace_root):
        raise ValueError(f"Path is outside the allowed workspace: {resolved}")
    if not resolved.exists():
        raise FileNotFoundError(f"File does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"Path is not a file: {resolved}")
    return resolved


def _clean_text(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    compact = " ".join(html.unescape(text).split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web through DuckDuckGo's lightweight HTML endpoint."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return _result(
            "web_search",
            False,
            "Install requests and beautifulsoup4 before using web search.",
            missing=["requests", "beautifulsoup4"],
        )

    if not query.strip():
        return _result("web_search", False, "Enter a search query.")

    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return _result("web_search", False, f"Search failed: {exc}", query=query)

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    for item in soup.select(".result"):
        link = item.select_one(".result__a")
        snippet = item.select_one(".result__snippet")
        if not link:
            continue
        results.append(
            {
                "title": _clean_text(link.get_text(" ", strip=True), 240),
                "url": link.get("href", ""),
                "snippet": _clean_text(snippet.get_text(" ", strip=True), 500) if snippet else "",
            }
        )
        if len(results) >= max(1, min(max_results, 10)):
            break

    if not results:
        return _result("web_search", False, "No search results were found.", query=query)
    return _result("web_search", True, f"Found {len(results)} result(s) for '{query}'.", results=results)


def scrape_url(url: str) -> str:
    """Fetch a web page and extract title, headings, text, and links."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return _result(
            "scrape_url",
            False,
            "Install requests and beautifulsoup4 before using web scraping.",
            missing=["requests", "beautifulsoup4"],
        )

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return _result("scrape_url", False, "Only http and https URLs are supported.", url=url)

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return _result("scrape_url", False, f"Scrape failed: {exc}", url=url)

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()

    title = _clean_text(soup.title.get_text(" ", strip=True), 240) if soup.title else ""
    headings = [_clean_text(tag.get_text(" ", strip=True), 240) for tag in soup.select("h1, h2, h3")[:20]]
    links = []
    for link in soup.select("a[href]")[:40]:
        text = _clean_text(link.get_text(" ", strip=True), 160)
        href = link.get("href", "")
        if text or href:
            links.append({"text": text, "href": href})

    text = _clean_text(soup.get_text(" ", strip=True))
    return _result(
        "scrape_url",
        True,
        f"Scraped {url}.",
        title=title,
        headings=headings,
        links=links,
        text=text,
    )


def read_local_file(path: str) -> str:
    """Read a local text file or parse a PDF inside the allowed workspace."""
    try:
        resolved = _safe_workspace_path(path)
    except (OSError, ValueError) as exc:
        return _result("read_local_file", False, str(exc), path=path)

    if resolved.suffix.lower() == ".pdf":
        return parse_pdf(str(resolved))

    content_type, _ = mimetypes.guess_type(resolved.name)
    if content_type and not content_type.startswith("text/"):
        allowed = {".md", ".csv", ".json", ".yaml", ".yml", ".log", ".py", ".txt"}
        if resolved.suffix.lower() not in allowed:
            return _result("read_local_file", False, "Unsupported binary file type.", path=str(resolved))

    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _result("read_local_file", False, f"Could not read file: {exc}", path=str(resolved))

    return _result("read_local_file", True, f"Read {resolved.name}.", path=str(resolved), text=_clean_text(text))


def parse_pdf(path: str) -> str:
    """Extract text from a PDF with PyMuPDF."""
    try:
        resolved = _safe_workspace_path(path)
    except (OSError, ValueError) as exc:
        return _result("parse_pdf", False, str(exc), path=path)

    try:
        import fitz
    except ImportError:
        return _result("parse_pdf", False, "PyMuPDF is not installed. Run pip install -r requirements.txt.")

    try:
        pages: list[dict[str, Any]] = []
        with fitz.open(resolved) as doc:
            for page_number, page in enumerate(doc, start=1):
                text = _clean_text(page.get_text("text"), 4000)
                pages.append({"page": page_number, "text": text})
    except Exception as exc:
        return _result("parse_pdf", False, f"Could not parse PDF: {exc}", path=str(resolved))

    combined = _clean_text("\n\n".join(page["text"] for page in pages))
    return _result(
        "parse_pdf",
        True,
        f"Parsed {resolved.name} with {len(pages)} page(s).",
        path=str(resolved),
        page_count=len(pages),
        text=combined,
        pages=pages[:5],
    )


def send_email_gmail(
    to: str,
    subject: str,
    body: str,
    allow_send: bool = False,
    confirmation: str = "",
) -> str:
    """Draft or send an email through the Gmail API."""
    message_preview = {"to": to, "subject": subject, "body": body}
    if not allow_send or confirmation != "SEND":
        return _result(
            "send_email_gmail",
            True,
            "Email sending is disabled, so this returned a draft preview.",
            sent=False,
            draft=message_preview,
        )

    settings = get_settings()
    if not settings.gmail_credentials_file.exists():
        return _result(
            "send_email_gmail",
            False,
            "Missing Gmail OAuth credentials file.",
            expected_credentials_file=str(settings.gmail_credentials_file),
            draft=message_preview,
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        return _result("send_email_gmail", False, "Gmail dependencies are not installed.", draft=message_preview)

    scopes = ["https://www.googleapis.com/auth/gmail.send"]
    creds = None
    if settings.gmail_token_file.exists():
        creds = Credentials.from_authorized_user_file(str(settings.gmail_token_file), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(settings.gmail_credentials_file), scopes)
            creds = flow.run_local_server(port=0)
        settings.gmail_token_file.write_text(creds.to_json(), encoding="utf-8")

    email_message = EmailMessage()
    email_message["To"] = to
    email_message["Subject"] = subject
    email_message.set_content(body)
    encoded = base64.urlsafe_b64encode(email_message.as_bytes()).decode()

    try:
        service = build("gmail", "v1", credentials=creds)
        sent = service.users().messages().send(userId="me", body={"raw": encoded}).execute()
    except Exception as exc:
        return _result("send_email_gmail", False, f"Email send failed: {exc}", draft=message_preview)

    return _result("send_email_gmail", True, "Email sent through Gmail.", sent=True, gmail_response=sent)


TOOL_REGISTRY = {
    "web_search": web_search,
    "scrape_url": scrape_url,
    "read_local_file": read_local_file,
    "parse_pdf": parse_pdf,
    "send_email_gmail": send_email_gmail,
}


def available_tools_snapshot() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": func.__doc__ or "",
        }
        for name, func in TOOL_REGISTRY.items()
    ]
