import logging
from enum import Enum
from src.config import config
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

logger = logging.getLogger(__name__)


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
        _SEARCH_CODE
    ]

    READ_TREE = [
        _GET_REPOSITORY_TREE,
        _GET_FILE_CONTENTS
    ]

    READ_ISSUES = [
        _ISSUE_READ,
        _LIST_ISSUES,
        _LIST_ISSUE_TYPES,
        _SEARCH_ISSUES,
     ]


def _build_server(toolset: GithubToolSet) -> MCPServerStreamableHttp:
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


class GitHubMCPFactory:
    """필요한 MCP 서버만 lazy connect하는 팩토리."""

    _read_tree: MCPServerStreamableHttp = _build_server(GithubToolSet.READ_TREE)
    _read_files: MCPServerStreamableHttp = _build_server(GithubToolSet.READ_FILES)
    _read_issues: MCPServerStreamableHttp = _build_server(GithubToolSet.READ_ISSUES)
    _connected: set[str] = set()

    @classmethod
    async def _ensure(
        cls, server: MCPServerStreamableHttp, name: str
    ) -> MCPServerStreamableHttp:
        if name not in cls._connected:
            await server.connect()
            cls._connected.add(name)
        return server

    @classmethod
    async def disconnect(cls) -> None:
        """연결된 MCP 서버만 해제한다."""
        servers = {
            "read_tree": cls._read_tree,
            "read_files": cls._read_files,
            "read_issues": cls._read_issues,
        }
        for name in list(cls._connected):
            try:
                await servers[name].cleanup()
            except BaseException as e:
                logger.debug("mcp cleanup suppressed: %s", e)
        cls._connected.clear()

    @classmethod
    async def readProjectTree(cls) -> MCPServerStreamableHttp:
        return await cls._ensure(cls._read_tree, "read_tree")

    @classmethod
    async def readProject(cls) -> MCPServerStreamableHttp:
        return await cls._ensure(cls._read_files, "read_files")

    @classmethod
    async def readIssues(cls) -> MCPServerStreamableHttp:
        return await cls._ensure(cls._read_issues, "read_issues")
