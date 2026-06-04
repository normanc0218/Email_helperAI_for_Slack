from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from .sub_agents import (
    audit_agent,
    casual_agent,
    digest_agent,
    inbox_processing_agent,
    inbox_query_agent,
    mailbox_sync_agent,
    project_chat_agent
)

# ── Identity & rules ──────────────────────────────────────────────────────────

SYSTEM_IDENTITY = """You are the master Email Agent.
Your ONLY job: classify intent → route to the correct sub-agent.
Never produce output for the user yourself — sub-agents own all responses."""

CRITICAL_RULES = """ABSOLUTE RULES — never break these:
- Never delete emails. Archive only.
- Never call tools directly. Route to sub-agents only.
- Never write a response to the user — your job is routing, not responding."""

# ── Routing ───────────────────────────────────────────────────────────────────

ROUTING = """## Intent classification

Classify the user message into exactly one intent based on meaning, not keywords.

| Intent       | User wants to...                                          | Route to              |
|--------------|-----------------------------------------------------------|-----------------------|
| ORGANIZE     | process, tidy, or act on emails in inbox                  | → ORGANIZE workflow   |
| DIGEST       | get a summary or overview of recent email activity        | → digest_agent        |
| UNDO         | reverse or cancel a previous action                       | → audit_agent         |
| QUERY        | look up information without changing anything             | → inbox_query_agent   |
| PROJECT_CHAT | ask about or discuss the currently-selected project       | → project_chat_agent  |
| CASUAL       | chat, greet, or ask something unrelated to email          | → casual_agent        |
"""

ORGANIZE_WORKFLOW = """## ORGANIZE steps (execute in order, one transfer at a time)
1. Transfer to mailbox_sync_agent
2. Transfer to inbox_processing_agent
3. Transfer to audit_agent  ← audit_agent writes the final ORGANIZE report for the user"""

# ── Tool hints (routing aids only) ───────────────────────────────────────────

_TOOL_HINTS: dict[str, str] = {
    "ORGANIZE":     "Workflow: mailbox_sync_agent → inbox_processing_agent → audit_agent",
    "DIGEST":       "Sub-agent: digest_agent",
    "UNDO":         "Sub-agent: audit_agent",
    "QUERY":        "Sub-agent: inbox_query_agent",
    "PROJECT_CHAT": "Sub-agent: project_chat_agent",
    "CASUAL":       "Sub-agent: casual_agent",
}


def get_tools(job_type: str) -> str:
    hint = _TOOL_HINTS.get(job_type, "")
    return f"## Workflow\n{hint}" if hint else ""


# ── Dynamic system prompt (routing only — no output formats) ─────────────────

def build_system_prompt(job_type: str, project_md: str | None = None) -> str:
    parts = [
        SYSTEM_IDENTITY,
        CRITICAL_RULES,
        get_tools(job_type),
        ROUTING,
    ]
    if job_type == "ORGANIZE":
        parts.append(ORGANIZE_WORKFLOW)
    if project_md:
        parts.append(f"## Selected project\n{project_md}")
    return "\n\n".join(p for p in parts if p)


def dynamic_instruction(context: ReadonlyContext) -> str:
    job_type   = context.state.get("job_type", "CASUAL")
    project_md = context.state.get("project_md", None)
    return build_system_prompt(job_type, project_md)


# ── Root agent ────────────────────────────────────────────────────────────────


root_agent = Agent(
    name="email_agent",
    model="openai/gpt-4o-mini",
    description="Master orchestrator for Gmail inbox management. Routes every message to the correct sub-agent.",
    instruction=dynamic_instruction,
    sub_agents=[
        mailbox_sync_agent,
        inbox_processing_agent,
        digest_agent,
        audit_agent,
        inbox_query_agent,
        casual_agent,
        project_chat_agent,
    ],
)
