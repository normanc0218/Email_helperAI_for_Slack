from google.adk.agents import Agent

from ..tools.digest_tools import daily_digest

digest_agent = Agent(
    name="digest_agent",
    model="openai/gpt-4o-mini",
    description=(
        "Generates a concise daily digest of email group activity and urgent items. "
        "Call for /digest or on schedule."
    ),
    instruction="""You are the Digest agent.

1. Call daily_digest() to fetch inbox data.
2. Format the result using standard Markdown (not Slack mrkdwn):

## 📅 Daily Digest

## 🔴 Needs Response
- **[Sender]** — [subject] ([N] days waiting)
(write "None" if nothing urgent)

## 📁 Project Updates
- **[Group Name]** — [one-line update]
(max 6 groups)

Hard rules:
- Use **bold** and ## headers — not *bold* or Slack mrkdwn.
- No JSON, no code blocks.
- Total response under 600 characters.
""",
    tools=[daily_digest],
)
