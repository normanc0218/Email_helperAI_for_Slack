from google.adk.agents import Agent

from ..tools.inbox_query_tools import get_group_emails, get_inbox_stats

project_chat_agent = Agent(
    name="project_chat_agent",
    model="openai/gpt-4o-mini",
    description="Answers questions about a specific email project/group selected by the user.",
    instruction="""You are the Project Chat agent.
The user has opened a specific project and wants to discuss it.
The project name and summary are provided in the system prompt under "## Selected project".

Steps:
1. Read the project context from the system prompt.
2. If the user needs email details, call get_group_emails(group_name=<project name>).
3. Answer the user's question in 2-4 sentences. Be concise and direct.
4. Surface action items or key threads when relevant.

Stay strictly scoped to the selected project. Do not answer about other projects.""",
    tools=[get_group_emails, get_inbox_stats],
)
