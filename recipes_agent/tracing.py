"""Langfuse tracing — the replacement for LangSmith in this project.

Call `setup_tracing()` once per process (first cell of a notebook, top of a
script). After that every LangChain / LangGraph run in that process is traced,
without passing callbacks to each `.invoke()` call.

Credentials come from .env:
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL
Set LANGFUSE_TRACING=false to turn tracing off without touching the code.
"""

from __future__ import annotations

import os
from contextvars import ContextVar

from dotenv import load_dotenv
from langchain_core.tracers.context import register_configure_hook
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# LangChain's callback manager adds the handler stored in this ContextVar to
# every run. Passing CallbackHandler as handle_class makes it skip the global
# handler whenever one was already given in config={"callbacks": [...]}, so a
# run is never traced twice.
_handler_var: ContextVar[CallbackHandler | None] = ContextVar(
    "langfuse_handler", default=None
)
register_configure_hook(_handler_var, True, CallbackHandler)


def setup_tracing(*, verbose: bool = True) -> CallbackHandler | None:
    """Enable Langfuse tracing for every LangChain run in this process.

    Returns the handler (also usable explicitly via
    `config={"callbacks": [handler]}`), or None when tracing is disabled or
    the keys are missing.
    """
    load_dotenv()

    if os.getenv("LANGFUSE_TRACING", "true").lower() == "false":
        _handler_var.set(None)
        if verbose:
            print("Langfuse tracing disabled (LANGFUSE_TRACING=false)")
        return None

    missing = [
        key
        for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
        if not os.getenv(key)
    ]
    if missing:
        print(f"Langfuse tracing OFF - missing in .env: {', '.join(missing)}")
        return None

    if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
        print("Warning: LANGSMITH_TRACING is also true - runs go to both backends")

    handler = CallbackHandler()
    _handler_var.set(handler)

    if verbose:
        client = get_client()
        base_url = os.getenv("LANGFUSE_BASE_URL") or os.getenv(
            "LANGFUSE_HOST", "https://cloud.langfuse.com"
        )
        if client.auth_check():
            print(f"Langfuse tracing ON -> {base_url}")
        else:
            print(f"Langfuse keys rejected by {base_url} - check .env")

    return handler


def flush() -> None:
    """Send buffered traces now — worth calling at the end of a notebook."""
    get_client().flush()
