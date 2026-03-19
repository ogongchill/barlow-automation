"""reject_end -- 중복 이슈로 워크플로우 종료."""

from dataclasses import dataclass

from src.domain.feat.agents.relevant_issue_finder.schema import RelevantIssue


@dataclass(frozen=True)
class RejectEndInput:
    relevant_issues: RelevantIssue | None


@dataclass(frozen=True)
class RejectEndOutput:
    completion_message: str


class RejectEndStep:

    async def execute(self, input: RejectEndInput) -> RejectEndOutput:
        return RejectEndOutput(
            completion_message="중복 이슈가 존재하여 요청이 거절되었습니다."
        )
