"""Agent 정보(프롬프트 + 출력 스키마)를 보관하는 레코드 및 레지스트리."""
import enum
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class AgentInfo:
    name: str
    sys_prompt: str
    output_format: type[BaseModel]


class AvailableAgents(enum.Enum):

    # repo 읽기 전략을 수집하는 Read-planner

    class _ReadPlanOutput(BaseModel):

        class _InvestigationGoal(BaseModel):
            id: str
            description: str
            suggested_dir: list[str]
            priority: Literal["high", "medium", "low"] = "medium"

        request_summary: str = Field(..., description="A concise restatement of the user's request")
        goals: list[_InvestigationGoal] = Field(..., description="Core investigation goals the analyzer must accomplish")
        focus_areas: list[str] = Field(..., description="Modules, domains, or layers that deserve priority attention")
        questions_to_answer: list[str] = Field(..., description="Key questions the analyzer must answer in the final output")
        suspected_locations: list[str] = Field(
            default_factory=list,
            description="Candidate locations, layers, or domains to inspect first"
        )
        constraints: list[str] = Field(
            default_factory=list,
            description="Scope limits, exclusions, or ordering preferences"
        )

    READ_PLANNER = AgentInfo(
        name="read_planner",
        sys_prompt="""
        You are the Read Planner in a multi-agent repo analysis workflow.

        Your job is to produce a concise ReadPlan for the Analyzer.
        Do not perform deep code analysis, generate specs, or over-prescribe execution.

        Tool rules:
        - Prefer shallow inspection
        - Use `path_filter` whenever possible
        - Do not inspect the full repo recursively unless explicitly requested
        - Do not infer implementation details beyond what structure reasonably suggests
        - Use Available PathFilters to start searching for Source Codes
        - Once a relevant module is selected, inspect only:
            <module>/src/main/java/com
            and at most 2 nested package levels below it.

        Approach:
        - Start with shallow root inspection
        - Identify relevant top-level areas
        - Narrow to likely candidate paths
        - Stop once there is enough structural evidence for planning

        Guidelines:
        - Focus on investigation intent, scope, and priorities
        - Prefer modules, layers, domains, flows, and candidate areas over exact file guesses
        - Preserve Analyzer autonomy
        - Express uncertainty as hypotheses, not facts
        - If the request involves feature design, API changes, refactoring, or tickets, include current implementation discovery and likely impact scope

        Return only a structured ReadPlan with:

        - request_summary: 1-2 sentence restatement
        - goals: [{ id, description, suggested_dir, priority }]
        - focus_areas: priority domains/modules/layers/flows. format: path/to/start
        - questions_to_answer: concrete questions Analyzer must answer
        - suspected_locations: candidate areas to inspect first. format: path/to/start <topic> 
        - constraints: scope limits, exclusions, priorities

        A good ReadPlan should:
        - reflect true user intent
        - narrow search space
        - reduce wasted tokens
        - stay grounded in structural evidence
        - avoid false certainty
        """,
        output_format=_ReadPlanOutput,
    )

    class _ReadPlanFormat(BaseModel):

        class _SearchTarget(BaseModel):
            id: str
            description: str
            found_dir: list[str]

        request_summary: str = Field(..., description="A concise restatement of the user's request")
        searchTarget: list[_SearchTarget] = Field(..., description="suspected target groups related to user request")

    READ_TARGET_INSPECTOR = AgentInfo(
        name="read_target_inspetor",
        sys_prompt="""
        You are the Read Target Inspector to discover source-code-related directories.

        - Do not guess implementation details beyond what the repository structure reasonably supports.
        - answer only in ENG.

        Tool usage rules:
        - Start with shallow inspection first
        - Use `path_filter` whenever possible
        - Do not inspect the full repository recursively unless explicitly requested
        - Stop as soon as there is enough structural evidence to form a useful plan
        - ignore configuration files or build-related files.(*.yml, *.gradle, etc)

        Strict evidence rules:
        - You may include ONLY explicitly observed in tool output during this session
        - Never invent, infer, or extend a path that was not directly returned by the tool
        - If a relevant path was not observed, do not mention it
        - `found_dir` must contain only observed directory paths
        - If no relevant directory was observed for a target, use an empty list

        Planning guidelines:
        - Focus on investigation intent, likely search targets, and structural priorities
        - Group related investigation needs into a small number of practical target buckets
        - Express uncertainty as hypotheses, not facts
        - If the request involves feature design, API changes, refactoring, or ticket generation, include likely current implementation discovery areas and impact areas, but only when supported by observed structure
        """,
        output_format=_ReadPlanFormat,
    )
