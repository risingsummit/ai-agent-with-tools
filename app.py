from __future__ import annotations

from pathlib import Path

import streamlit as st

from agent import run_agent
from config import get_settings
from tools import TOOL_REGISTRY, available_tools_snapshot


st.set_page_config(
    page_title="AI Agent With Tools",
    page_icon=":material/smart_toy:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _init_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("last_tool_outputs", [])


def _save_upload(uploaded_file) -> str:
    upload_dir = Path.cwd() / "uploaded_documents"
    upload_dir.mkdir(exist_ok=True)
    target = upload_dir / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return str(target)


_init_state()
settings = get_settings()

st.title("AI Agent With Tools")
st.caption("Research, scrape, read documents, and prepare Gmail follow-ups from one local workspace.")

if settings.public_demo_mode:
    st.info(
        "Public demo mode is on. Gmail sending is locked to draft previews, while search, scraping, "
        "PDF parsing, local uploads, and AI planning remain available when configured."
    )

with st.sidebar:
    st.subheader("Controls")
    allow_email_send = st.toggle(
        "Allow Gmail sending",
        value=False,
        disabled=not settings.enable_gmail_send or settings.public_demo_mode,
    )
    if settings.public_demo_mode:
        st.caption("Public demo mode keeps Gmail locked to safe draft previews.")
    elif not settings.enable_gmail_send:
        st.caption("Set ENABLE_GMAIL_SEND=true to unlock the send toggle.")
    else:
        st.caption("Sending still requires the tool confirmation phrase SEND.")

    st.divider()
    st.subheader("Workspace")
    st.text_input("Allowed file root", value=str(settings.workspace_root), disabled=True)
    st.text_input("Model", value=settings.openai_model, disabled=True)
    st.text_input("Agent mode", value="LangGraph" if settings.openai_api_key else "Local fallback", disabled=True)

    st.divider()
    st.subheader("Demo Prompts")
    st.caption("Try these during a walkthrough.")
    st.code("Search for recent AI agent job postings and summarize common skills.")
    st.code("Scrape https://www.python.org and summarize the page.")
    st.code("Draft an email to alex@example.com about this demo.")

    st.divider()
    st.subheader("Document Upload")
    uploaded = st.file_uploader("Add a PDF or text file", type=["pdf", "txt", "md", "csv", "json", "log"])
    if uploaded:
        saved_path = _save_upload(uploaded)
        st.success(f"Saved: {Path(saved_path).name}")
        if st.button("Parse uploaded file", use_container_width=True):
            output = TOOL_REGISTRY["read_local_file"](saved_path)
            st.session_state.last_tool_outputs = [output]

    st.divider()
    st.subheader("Available Tools")
    for tool_info in available_tools_snapshot():
        st.markdown(f"**{tool_info['name']}**")
        st.caption(tool_info["description"])

left, right = st.columns([0.62, 0.38], gap="large")

with left:
    st.subheader("Agent Chat")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask the agent to search, scrape, parse, summarize, draft, or send...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Working through the tools..."):
                response = run_agent(
                    prompt,
                    history=st.session_state.messages[:-1],
                    allow_email_send=allow_email_send,
                )
            st.markdown(response.answer)
            st.caption(f"Mode: {response.mode}")

        st.session_state.messages.append({"role": "assistant", "content": response.answer})
        st.session_state.last_tool_outputs = response.tool_outputs
        st.rerun()

with right:
    st.subheader("Tool Output")
    if not st.session_state.last_tool_outputs:
        st.info("Tool results will appear here after the agent runs.")
    for index, output in enumerate(st.session_state.last_tool_outputs, start=1):
        with st.expander(f"Result {index}", expanded=index == 1):
            st.markdown(output)

    st.divider()
    st.subheader("Direct Tool Run")
    tool_name = st.selectbox("Tool", list(TOOL_REGISTRY.keys()))

    if tool_name == "web_search":
        query = st.text_input("Search query")
        max_results = st.slider("Max results", min_value=1, max_value=10, value=5)
        if st.button("Run search", use_container_width=True):
            st.session_state.last_tool_outputs = [TOOL_REGISTRY[tool_name](query, max_results)]
            st.rerun()
    elif tool_name == "scrape_url":
        url = st.text_input("URL")
        if st.button("Scrape", use_container_width=True):
            st.session_state.last_tool_outputs = [TOOL_REGISTRY[tool_name](url)]
            st.rerun()
    elif tool_name in {"read_local_file", "parse_pdf"}:
        path = st.text_input("Path inside workspace")
        if st.button("Read", use_container_width=True):
            st.session_state.last_tool_outputs = [TOOL_REGISTRY[tool_name](path)]
            st.rerun()
    elif tool_name == "send_email_gmail":
        to = st.text_input("To")
        subject = st.text_input("Subject")
        body = st.text_area("Body", height=160)
        confirmation = st.text_input("Confirmation phrase")
        if st.button("Draft or send", use_container_width=True):
            st.session_state.last_tool_outputs = [
                TOOL_REGISTRY[tool_name](
                    to=to,
                    subject=subject,
                    body=body,
                    allow_send=allow_email_send,
                    confirmation=confirmation,
                )
            ]
            st.rerun()
