"""
Local tool definitions using the claude-agent-sdk @tool decorator.
Add new tools here and register them in build_server().
"""

from datetime import datetime

from claude_agent_sdk import tool, create_sdk_mcp_server


@tool("get_current_time", "Returns the current date and time.", {})
async def get_current_time(args: dict) -> dict:
    return {
        "content": [{"type": "text", "text": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]}


def build_server():
    return create_sdk_mcp_server(
        name="local",
        version="1.0.0",
        tools=[get_current_time],
    )
