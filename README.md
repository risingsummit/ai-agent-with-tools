# AI Agent With Tools

A local Python agent that can research the web, scrape pages, read local files, parse PDF documents, and prepare or send email through the Gmail API with an explicit approval gate.

The app is built for practical deskwork: competitor snapshots, job-board scanning, report parsing, email drafting, and structured follow-up tasks.

## What It Includes

- Web search and scraping with `requests` and `BeautifulSoup4`
- PDF parsing with `PyMuPDF`
- Local file reading with workspace path safety checks
- Tool-calling agent flow with `LangChain` and `LangGraph`
- Gmail execution tool with dry-run mode and a required send confirmation
- Streamlit front-end for chat, tool settings, and source uploads
- Offline fallback controller when no model key is configured

## Quick Start

```powershell
cd "C:\Users\nguye\OneDrive\Documents\Threat model assistants\ai-agent-with-tools"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

Add your OpenAI key to `.env` if you want the LangGraph AI planner:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

Without an API key, the app still runs and can execute direct tool commands from the UI.

## Example Prompts

```text
Search for 5 recent product manager jobs in fintech and summarize required skills.
```

```text
Scrape https://example.com and tell me the main positioning, pricing signals, and links.
```

```text
Read reports/market-outlook.pdf and extract risks, trends, and action items.
```

```text
Draft an email to alex@example.com about the report findings.
```

## Gmail Setup

Email sending is protected by two controls:

1. The Streamlit sidebar must enable email sending.
2. The tool call must include the confirmation phrase `SEND`.

To send through Gmail:

1. Create OAuth desktop credentials in Google Cloud.
2. Download the OAuth file as `credentials.json`.
3. Place it in this project folder.
4. Run the app and send one approved email; a local `token.json` will be created after browser authorization.

If sending is disabled or the confirmation phrase is missing, the email tool returns a draft preview instead of sending.

## Project Files

- `app.py` - Streamlit interface
- `agent.py` - LangGraph agent and fallback controller
- `tools.py` - Web, file, PDF, and Gmail tool functions
- `config.py` - Environment and runtime settings
- `tests/` - Focused tests for path safety and tool behavior

## Safety Notes

- Local file reads are restricted to the configured workspace root.
- Network tools use timeouts and return concise extracted text.
- Email execution is never automatic by default.
- Keep Gmail OAuth files out of source control.
