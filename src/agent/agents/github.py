from enum import Enum

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

_GITHUB_TREE_READ_TOOLS = [
    "get_repository_tree"
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

GIHUB_MCP_READ_TREE = MCPServerStreamableHttp(
     params=MCPServerStreamableHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": config.github_token,
            "X-MCP-Tools": ", ".join(_GITHUB_TREE_READ_TOOLS),
            "X-MCP-Readonly": "true",
        },
    ),
    name="github-read-tree",
    cache_tools_list=True,
)

class GithubToolSet(Enum):
    # see https://github.com/github/github-mcp-server/blob/main/README.md#default-toolset

    # actions
    _ACTIONS_GET = "actions_get"
    _ACTIONS_LIST = "actions_list"
    _ACTIONS_RUN_TRIGGER = "actions_run_trigger"
    _GET_JOB_LOGS = "get_job_logs"

    # code security
    _GET_CODE_SCANNING_ALERT = "get_code_scanning_alert"
    _LIST_CODE_SCANNING_ALERTS = "list_code_scanning_alerts"

    # context
    _GET_ME = "get_me"
    _GET_TEAM_MEMBERS = "get_team_members"
    _GET_TEAMS = "get_teams"

    # copilot
    _ASSIGN_COPILOT_TO_ISSUE = "assign_copilot_to_issue"
    _REQUEST_COPILOT_REVIEW = "request_copilot_review"

    # dependabot
    _GET_DEPENDBOT_ALERT = "get_dependabot_alert"
    _LIST_DEPENDABOT_ALERTS = "list_dependabot_alerts"
    
    # discussions
    _GET_DISCUSSION = "get_discussion"
    _GET_DISCUSSION_COMMENTS = "get_discussion_comments"
    _LIST_DISCUSSION_CATEGORIES = "list_discussion_categories"
    _LIST_DISCUSSIONS = "list_discussions"

    # gists
    _CREATE_GIST = "create_gist"
    _GET_GIST = "get_gist"
    _LIST_GISTS = "list_gists"
    _UPDATE_GIST = "update_gist"

    #git
    _GET_REPOSITORY_TREE = "get_repository_tree"

    #issues
    _ADD_ISSUE_COMMENT = "add_issue_comment"
    _GET_LABEL = "get_label"
    _ISSUE_READ = "issue_read"
    _ISSUE_WRITE = "issue_write"
    _LIST_ISSUE_TYPES = "list_issue_types"
    _LIST_ISSUES = "list_issues"
    _SEARCH_ISSUES = "search_issues"
    _SUB_ISSUE_WRITE = "sub_issue_write"

    # label
    _LABEL_WRITE = "label_write"
    _LIST_LABEL = "list_lable"

    # notifications
    _DISMISS_NOTIFICATION = "dismiss_notification"
    _GET_NOTIFICATION_DETAILS = "get_notification_details"
    _LIST_NOTIFICATIONS = "list_notifications"
    _MANAGE_NOTIFICATION_SUBSCRIPTION = "manage_notification_subscription"
    _MANAGE_REPOSITORY_NOTIFICATION_SUBSCRIPTION = "manage_repository_notification_subscription"
    _MARK_ALL_NOTIFICATIONS_READ = "mark_all_notifications_read"

    # organizations
    _SERACH_ORGANIZATIONS = "search_orgs"

    # projects
    _PROJECTS_GET = "projects_get"
    _PROJECTS_LIST = "projects_list"
    _PROJECTS_WRITE = "projects_write"

    # pull requests
    _ADD_COMMENT_TO_PENDING_REVIEW = "add_comment_to_pending_review"
    _ADD_REPLY_TO_PULL_REQUEST_COMMENT = "add_reply_to_pull_request_command"
    _CREATE_PULL_REQUEST = "create_pull_request"
    _LIST_PULL_REQUESTS = "list_pull_requests"
    _MERGE_PULL_REQUEST = "merge_pull_request"
    _PULL_REQUEST_READ = "pull_request_read"
    _PULL_REQUEST_REVIEW_WRITE = "pull_request_review_write"
    _SEARCH_PULL_REQUESTS = "search_pull_requests"
    _UPDATE_PULL_REQUEST = "update_pull_request"
    _UPDATE_PULL_REQUEST_BRANCH = "update_pull_request_branch"

    # repository
    _CREATE_BRANCH = "create_branch"
    _CREATE_OR_UPDATE_FILE = "create_or_update_file"
    _CREATE_REPOSITORY = "create_repository"
    _DELETE_FILE = "delete_file"
    _FORK_REPOSITORY = "fork_repository"
    _GET_COMMIT = "get_commit"
    _GET_FILE_CONTENTS = "get_file_contents"
    _GET_LATEST_RELEASE = "get_latest_release"
    _GET_RELEASE_BY_TAG = "get_release_by_tag"
    _GET_TAG = "get_tag"
    _LIST_BRANCHES = "list_branches"
    _LIST_COMMITS = "list_commits"
    _LIST_RELEASES = "list_releases"
    _LIST_TAGS = "list_tags"
    _PUSH_FILES = "push_files"
    _SEARCH_CODE = "search_code"
    _SEARCH_REPOSITORIES = "search_repositories"

    # secret
    _GET_SECRET_SCANNING_ALERT = "get_secret_scanning_alert"
    _LIST_SECRET_SCANNING_ALERTS = "list_secret_scanning_alerts"

    # security advisories
    _GET_GLOBAL_SECURITY_ADVISORY = "get_global_security_advisory"
    _LIST_GLOBAL_SECURITY_ADVISORIES = "list_global_security_advisories"
    _LIST_ORG_REPOSITORY_SECURITY_ADVISORIES = "list_org_repository_security_advisories"
    _LIST_REPOSITORY_SECURITY_ADVISORIES = "list_repository_security_advisories"

    # stargazers
    _LIST_STARRED_REPOSITORIES = "list_starred_repositories"
    _STAR_REPOSITORY = "star_repository"
    _UNSTAR_REPOSITORY = "unstar_repository"

    # users
    _SEARCH_USERS = "search_users"

    READ_FILES = [
        _GET_FILE_CONTENTS,
        _PROJECTS_GET,
        _PROJECTS_LIST,
        _LIST_BRANCHES,
        _SEARCH_CODE
    ]
    
    READ_TREE = [
        _GET_REPOSITORY_TREE,
        _GET_FILE_CONTENTS
    ]

class GitHubMcpType(Enum):
    
    LOCAL = "local",
    REMOTE = "remote"

class GitHubMCPFactory:

    @staticmethod
    def _create(
        mcp_type: GitHubMcpType,
        toolset: GithubToolSet,
    ):

        if mcp_type == GitHubMcpType.LOCAL:
            return MCPServerStdio(
                params={
                    "command": "npx.cmd" if config.os_type == OsType.WINDOWS else "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": config.github_token},
                },
                name="github",
                cache_tools_list=True,
                tool_filter={
                    "allowed_tool_names": toolset.value
                },
                client_session_timeout_seconds=60,
            )

        elif mcp_type == GitHubMcpType.REMOTE:
            return MCPServerStreamableHttp(
                params=MCPServerStreamableHttpParams(
                    url="https://api.githubcopilot.com/mcp/",
                    headers={
                        "Authorization": config.github_token,
                        "X-MCP-Tools": ", ".join(toolset.value),
                        "X-MCP-Readonly": "true",
                    },
                ),
                name="github",
                cache_tools_list=True,
            )

        raise ValueError("Unsupported MCP type")
    
    @classmethod
    def readProjectTree(cls):
        return cls._create(
            mcp_type = GitHubMcpType.REMOTE,
            toolset = GithubToolSet.READ_TREE
        )
    
    @classmethod
    def readProject(cls):
        return cls._create(
            mcp_type = GitHubMcpType.REMOTE,
            toolset = GithubToolSet.READ_FILES
        )