"""
Structured logger for all LLM calls in the email agent.

Usage:
    from core.logger import get_logger, call_llm_with_log

    log = get_logger(__name__)
    log.info("agent_event", agent="casual_agent", intent_routed="CASUAL")

    result = await call_llm_with_log(
        fn=my_llm_call,
        agent="digest_agent",
        job_type="DIGEST",
        trace_id=trace_id,
        input_preview="show me my digest...",
    )

Environment:
    ENV=production  → JSON renderer (stdout, for Cloud Logging)
    ENV=development → ConsoleRenderer (human-readable, default)
"""

import os
import time
import uuid
from typing import Any, Callable

import structlog


def _configure_structlog() -> None:
    env = os.getenv("ENV", "development")
    renderer = (
        structlog.processors.JSONRenderer()
        if env == "production"
        else structlog.dev.ConsoleRenderer(colors=True)
    )
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


_configure_structlog()


def get_logger(name: str = __name__):
    return structlog.get_logger(name)


def new_trace_id() -> str:
    return str(uuid.uuid4())


async def call_llm_with_log(
    fn: Callable,
    *,
    agent: str,
    job_type: str,
    trace_id: str | None = None,
    input_preview: str = "",
    intent_routed: str | None = None,
    **fn_kwargs: Any,
) -> Any:
    """
    Wraps an async LLM call with structured logging.

    Logs: trace_id, agent, job_type, latency_ms, intent_routed,
          input_preview (first 100 chars), token counts if available.
    On failure: logs error_type + error_msg (truncated to 200 chars), then re-raises.

    Never logs full email body or any credential/token value.
    """
    log = get_logger(agent)
    trace_id = trace_id or new_trace_id()
    preview = (input_preview or "")[:100]

    start = time.monotonic()
    try:
        result = await fn(**fn_kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        # Extract token usage if the result carries it (OpenAI-style)
        input_tokens = output_tokens = cached_tokens = None
        if hasattr(result, "usage"):
            usage = result.usage
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)
            cached_tokens = getattr(
                getattr(usage, "prompt_tokens_details", None),
                "cached_tokens",
                None,
            )

        log.info(
            "llm_call",
            trace_id=trace_id,
            agent=agent,
            job_type=job_type,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            intent_routed=intent_routed,
            input_preview=preview,
        )
        return result

    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        log.error(
            "llm_call_failed",
            trace_id=trace_id,
            agent=agent,
            job_type=job_type,
            latency_ms=latency_ms,
            error_type=type(exc).__name__,
            error_msg=str(exc)[:200],
            input_preview=preview,
        )
        raise
