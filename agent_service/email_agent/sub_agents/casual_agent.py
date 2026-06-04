from google.adk.agents import Agent

from ..prompts.shared import SHARED_RULES

CASUAL_IDENTITY = """You are the Casual Conversation agent for an email assistant.
Respond naturally and warmly. Keep replies short and friendly."""

CASUAL_CAPABILITIES = """If the user asks what this assistant can do:
- Organise inbox: classify and group emails into projects
- Daily digest: summary of recent email activity
- Undo: reverse the last action taken
- Query: look up inbox stats or project details"""

CASUAL_OUTPUT_FORMAT = """Reply in 1-2 sentences.
Plain text only. No markdown. No bullets. No emoji unless user used them first."""

casual_agent = Agent(
    name="casual_agent",
    model="openai/gpt-4o-mini",
    description="Handles greetings, small talk, and general questions unrelated to email.",
    instruction="\n\n".join([
        CASUAL_IDENTITY,
        SHARED_RULES,
        CASUAL_CAPABILITIES,
        CASUAL_OUTPUT_FORMAT,
    ]),
)
