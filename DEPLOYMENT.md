# Streamlit Cloud Deployment

Use this when you are ready to make the app live and share it on LinkedIn.

## Recommended Setup

Create a new GitHub repository using only the `ai-agent-with-tools` folder as the repo root. That keeps deployment clean and avoids pulling in the other projects from the parent workspace.

Your public repo should include:

- `app.py`
- `agent.py`
- `tools.py`
- `config.py`
- `requirements.txt`
- `.streamlit/config.toml`
- `README.md`

It should not include:

- `.env`
- `.venv/`
- `credentials.json`
- `token.json`
- uploaded documents
- cache folders

## Streamlit Community Cloud Steps

1. Push this folder to GitHub.
2. Go to `https://share.streamlit.io`.
3. Choose **Create app**.
4. Choose your GitHub repository, branch, and entrypoint file.
5. If this folder is its own repo, the entrypoint is `app.py`.
6. If this folder stays inside the larger workspace repo, the entrypoint is `ai-agent-with-tools/app.py`.
7. Open **Advanced settings**.
8. Select Python `3.12`.
9. Paste secrets from `.streamlit/secrets.example.toml`.
10. Deploy and wait for the app to build.

Streamlit's current docs say Community Cloud deploys from GitHub, installs dependencies from a requirements file at the repo root or next to the app entrypoint, and lets you paste app secrets in Advanced settings.

## Public Demo Settings

For a LinkedIn showcase, keep:

```toml
PUBLIC_DEMO_MODE = "true"
ENABLE_GMAIL_SEND = "false"
```

That lets people try the app without giving the public internet access to your Gmail send button. The email tool will return safe draft previews.

Add this secret only if you want LangGraph AI planning live:

```toml
OPENAI_API_KEY = "sk-your-key-here"
OPENAI_MODEL = "gpt-4o-mini"
```

If you do not add an OpenAI key, the app still runs in local fallback mode and can demonstrate the direct tools.

## LinkedIn Demo Script

Use this flow for a short screen recording:

1. Show the app title and the public demo banner.
2. Run: `Search for recent AI agent job postings and summarize common skills.`
3. Run: `Scrape https://www.python.org and summarize the page.`
4. Upload a small PDF or text file and parse it.
5. Run: `Draft an email to alex@example.com about this demo.`
6. Point out that public demo mode prevents live Gmail sends.

## Troubleshooting

- Build failed: check that `requirements.txt` is committed.
- App imports fail: confirm the Streamlit entrypoint is correct.
- Secrets missing: open the app settings in Streamlit Cloud and update Secrets.
- OpenAI calls fail: confirm `OPENAI_API_KEY` is set and has available billing.
- Gmail sending is disabled: this is intentional for public demos.
