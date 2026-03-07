from src.config import config
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp, MCPServerStreamableHttpParams
from src.config import config, OsType

_GITHUB_READ_TOOLS = [
    "get_file_contents",
    "projects_get",
    "projects_list",
    "list_branches",
    "search_code"
]

GITHUB_LOCAL_MCP = MCPServerStdio(
            params={
                "command": "npx.cmd" if config.os_type == OsType.WINDOWS else "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": config.github_token},
            },
            name="github",
            cache_tools_list=True,
            tool_filter={
                "allowed_tool_names": _GITHUB_READ_TOOLS
            },
            client_session_timeout_seconds=60,
)

GITHUB_REMOTE_MCP = MCPServerStreamableHttp(
    params=MCPServerStreamableHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": config.github_token,
            "X-MCP-Tools": ", ".join(_GITHUB_READ_TOOLS),
            "X-MCP-Readonly": "true",
        },
    ),
    name="github",
    cache_tools_list=True,
)