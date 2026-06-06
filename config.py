from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None


load_dotenv()


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    openai_api_key: str | None
    openai_model: str
    gmail_credentials_file: Path
    gmail_token_file: Path
    enable_gmail_send: bool
    public_demo_mode: bool


def _resolve_project_path(value: str, default: str) -> Path:
    path = Path(value or default).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _read_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value

    try:
        import streamlit as st

        secret_value = st.secrets.get(name, default)
        return str(secret_value) if secret_value is not None else None
    except Exception:
        return default


def _read_bool(name: str, default: bool = False) -> bool:
    value = _read_setting(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    root = _resolve_project_path(_read_setting("AGENT_WORKSPACE_ROOT", ".") or ".", ".")
    credentials = _resolve_project_path(
        _read_setting("GMAIL_CREDENTIALS_FILE", "credentials.json") or "credentials.json",
        "credentials.json",
    )
    token = _resolve_project_path(_read_setting("GMAIL_TOKEN_FILE", "token.json") or "token.json", "token.json")
    return Settings(
        workspace_root=root,
        openai_api_key=_read_setting("OPENAI_API_KEY") or None,
        openai_model=_read_setting("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
        gmail_credentials_file=credentials,
        gmail_token_file=token,
        enable_gmail_send=_read_bool("ENABLE_GMAIL_SEND", False),
        public_demo_mode=_read_bool("PUBLIC_DEMO_MODE", True),
    )
