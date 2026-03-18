# Refactor Plan: Workflow Runtime 아키텍처 전환

## 목표

`refactor.md`의 설계 원칙에 따라 현재 코드를 **Workflow / Step 중심 런타임 아키텍처**로 전환한다.

---

## 현재 → 목표 구조 매핑

### 현재 구조의 문제점

| 문제 | 현재 코드 위치 |
|------|----------------|
| worker가 모든 핸들러를 포함 (거대한 `if-dict`) | `src/lambda_worker.py` |
| Step 간 계약이 raw agent output (str) | `services/` → `lambda_worker.py` |
| Agent lifecycle = Workflow lifecycle (MCP connect/disconnect이 _process에 묶임) | `lambda_worker._process()` |
| PendingRecord가 workflow state 역할 + 도메인 모델 역할을 동시에 수행 | `src/domain/pending.py` |
| 승인/거부가 일반 핸들러와 동일하게 처리 (1급 시민 아님) | `lambda_worker._handle_accept/reject` |
| provider 로직(AgentFactory, MCP)이 서비스 레이어와 결합 | `src/services/*.py` |

---

## 목표 패키지 구조

```
src/
  app/
    handlers/
      workflow_start_handler.py     # 기존: controller/handler/slash.py (SQS 전송 부분)
      step_worker_handler.py        # 기존: lambda_worker.handler()
      slack_interaction_handler.py  # 기존: controller/handler/slash.py (버튼 액션 부분)

  workflow/
    definitions/
      feat_issue_workflow.py        # step 순서, branch 조건 정의
      fix_issue_workflow.py
      refactor_issue_workflow.py

    runtime/
      workflow_runtime.py           # step 실행, state 로드/저장, transition 결정
      workflow_resumer.py           # Slack 인터랙션 → workflow 재개
      transition_resolver.py        # StepResult.control_signal → 다음 step 결정
      human_gate_manager.py         # waiting step 진입/해제

    models/
      workflow_definition.py        # WorkflowDefinition dataclass
      workflow_instance.py          # 기존: PendingRecord (확장)
      workflow_state.py             # step 간 공유 typed state
      step_definition.py            # StepDefinition dataclass
      step_result.py                # 기존: raw str 대체
      lifecycle.py                  # WorkflowStatus, StepStatus Enum

    contracts/
      common.py
      feat_issue/
        bc_candidates.py            # 기존: AvailableAgents.Candidates (이동)
        bc_decision.py              # 기존: AvailableAgents.BcDecision (이동)
        issue_draft.py              # 기존: FeatTemplate (래핑)
        issue_action_decision.py    # 신규

    steps/
      common/
        wait_for_human_action_step.py   # 승인/거부 대기 (1급 step)
        send_slack_message_step.py
      feat_issue/
        find_relevant_bc_step.py        # 기존: run_relevant_bc_finder()
        decide_bc_step.py               # 기존: run_bc_decision_maker()
        generate_issue_draft_step.py    # 기존: run_issue_generator()
        regenerate_issue_draft_step.py  # 기존: run_re_issue_generator()
        create_github_issue_step.py     # 기존: run_issue_creator()

    executors/
      base.py                       # StepExecutor ABC
      agent_executor.py             # 기존: AgentFactory._build() 패턴 추상화
      code_executor.py
      human_gate_executor.py        # 기존: _handle_accept/reject 로직

    agents/
      relevant_bc_finder/
        prompt.py                   # 기존: agent_info.py RELEVANT_BC_FINDER sys_prompt
        schema.py                   # 기존: AvailableAgents.Candidates (이동)
        adapter.py                  # raw output → BcCandidates contract 변환
      bc_decision_maker/
        prompt.py
        schema.py                   # 기존: AvailableAgents.BcDecision (이동)
        adapter.py
      feat_issue_generator/
        prompt.py                   # 기존: FEAT_ISSUE_GEN sys_prompt
        schema.py                   # FeatTemplate 유지
        adapter.py
      feat_issue_regenerator/
        prompt.py
        schema.py
        adapter.py

    mappers/
      agent_output_mapper.py        # raw agent output → workflow contract
      state_patch_builder.py        # StepResult → WorkflowState patch
      slack_payload_mapper.py       # 기존: _reply.py (이동)
      github_issue_mapper.py        # issue draft → GitHub API payload

  domain/
    issue/
      entities.py                   # 기존: issue_templates.py (이동)
      policies.py                   # label policy, sub-issue policy
      services.py

  infrastructure/
    persistence/
      workflow_instance_repository.py   # 기존: IPendingRepository (확장)
      pending_action_repository.py      # 기존: IIdempotencyRepository (역할 분리)
    storage/
      dynamodb/
        workflow_instance_store.py      # 기존: request_dynamo_repository.py
        pending_action_store.py         # 기존: idempotency_dynamo_repository.py
      memory/
        workflow_instance_store.py      # 기존: memory_pending_repository.py
        pending_action_store.py         # 기존: memory_idempotency_repository.py
    queue/
      sqs_publisher.py                  # 기존: sqs_queue_sender.py
      local_publisher.py                # 기존: local_queue_sender.py
    llm/
      openai_client.py                  # 기존: agent/openai.py + agent/models.py
    github/
      github_client.py                  # 신규: httpx 기반 GitHub REST API
    slack/
      slack_client.py                   # 기존: AsyncWebClient 래퍼

  shared/
    enums.py
    exceptions.py
    ids.py                              # workflow_id, step_id 생성
    clock.py
```

---

## 핵심 신규 모델

### WorkflowInstance (기존 PendingRecord 대체)

```python
# workflow/models/workflow_instance.py
@dataclass
class WorkflowInstance:
    workflow_id: str              # 기존 pk (message_ts) → 의미있는 ID로 변경
    workflow_type: str            # "feat_issue" | "fix_issue" | "refactor_issue"
    status: WorkflowStatus        # CREATED / RUNNING / WAITING / FAILED / COMPLETED
    current_step: str             # 현재 step 이름
    state: WorkflowState          # step 간 공유 typed state
    pending_action_token: str | None   # 사용자 응답 대기 중인 action token
    slack_channel_id: str
    slack_user_id: str
    slack_message_ts: str | None  # 현재 Slack 메시지 ts
    created_at: int
    ttl: int
```

### WorkflowState (기존 필드들 → typed state)

```python
# workflow/models/workflow_state.py
@dataclass
class FeatIssueWorkflowState:
    user_message: str
    bc_candidates: BcCandidates | None = None      # find_relevant_bc_step 결과
    bc_decision: BcDecision | None = None          # decide_bc_step 결과
    issue_draft: IssueDraft | None = None          # generate_issue_draft_step 결과
    github_issue_url: str | None = None            # create_github_issue_step 결과
    user_feedback: str | None = None               # bc_reject / reject 시 사용자 입력
    dropped_item_ids: list[str] = field(default_factory=list)
```

### StepResult (raw str 대체)

```python
# workflow/models/step_result.py
class StepResult(BaseModel):
    status: Literal["success", "waiting", "failed"]
    state_patch: dict = Field(default_factory=dict)
    control_signal: Literal["continue", "wait_for_user", "stop"] = "continue"
    next_step: str | None = None              # 명시적 지정 시
    user_action_request: dict | None = None   # Slack 버튼 payload 등
    internal_trace: dict | None = None        # token usage, raw output
```

---

## 변경 파일 목록 및 내용

### 제거 (삭제 또는 분해)

| 파일 | 처리 방법 |
|------|-----------|
| `src/lambda_worker.py` | `step_worker_handler.py` + `workflow/steps/` 로 분해 |
| `src/services/relevant_bc_finder.py` | `workflow/steps/feat_issue/find_relevant_bc_step.py` 로 이동 |
| `src/services/issue_generator.py` | `workflow/steps/feat_issue/generate_issue_draft_step.py` 로 이동 |
| `src/services/re_issue_generator.py` | `workflow/steps/feat_issue/regenerate_issue_draft_step.py` 로 이동 |
| `src/services/issue_creator.py` | `workflow/steps/feat_issue/create_github_issue_step.py` 로 이동 |
| `src/agent/agent_info.py` | `workflow/agents/*/prompt.py + schema.py` 로 분해 |
| `src/agent/agent_factory.py` | `workflow/executors/agent_executor.py` 로 흡수 |
| `src/domain/pending.py` | `workflow/models/workflow_instance.py` + `workflow/models/workflow_state.py` 로 대체 |

### 이동 (경로 변경)

| 현재 | 목표 |
|------|------|
| `src/domain/issue_templates.py` | `src/domain/issue/entities.py` |
| `src/controller/_reply.py` | `src/workflow/mappers/slack_payload_mapper.py` |
| `src/storage/request_dynamo_repository.py` | `src/infrastructure/storage/dynamodb/workflow_instance_store.py` |
| `src/storage/idempotency_dynamo_repository.py` | `src/infrastructure/storage/dynamodb/pending_action_store.py` |
| `src/storage/memory_pending_repository.py` | `src/infrastructure/storage/memory/workflow_instance_store.py` |
| `src/storage/memory_idempotency_repository.py` | `src/infrastructure/storage/memory/pending_action_store.py` |
| `src/storage/sqs_queue_sender.py` | `src/infrastructure/queue/sqs_publisher.py` |
| `src/storage/local_queue_sender.py` | `src/infrastructure/queue/local_publisher.py` |
| `src/agent/openai.py` | `src/infrastructure/llm/openai_client.py` |

### 신규 작성

| 파일 | 역할 |
|------|------|
| `workflow/runtime/workflow_runtime.py` | 핵심 오케스트레이터 |
| `workflow/runtime/transition_resolver.py` | StepResult → 다음 step 결정 |
| `workflow/runtime/human_gate_manager.py` | waiting step 진입/해제 |
| `workflow/definitions/feat_issue_workflow.py` | feat step 순서 정의 |
| `workflow/models/workflow_instance.py` | PendingRecord 대체 |
| `workflow/models/workflow_state.py` | step 간 typed state |
| `workflow/models/step_result.py` | StepResult |
| `workflow/models/lifecycle.py` | WorkflowStatus, StepStatus Enum |
| `workflow/executors/agent_executor.py` | AgentFactory 추상화 |
| `workflow/executors/human_gate_executor.py` | 승인/거부 처리 |
| `workflow/agents/*/adapter.py` | raw output → contract 변환 |
| `workflow/mappers/state_patch_builder.py` | StepResult → state patch |
| `workflow/mappers/github_issue_mapper.py` | issue draft → GitHub payload |
| `infrastructure/github/github_client.py` | httpx 기반 GitHub REST API |

---

## 단계별 구현 순서

### Phase 1. 모델 레이어 (기반 작업)

**목표**: 새 데이터 계약 정의. 기존 코드 건드리지 않음.

1. `workflow/models/lifecycle.py` — WorkflowStatus, StepStatus Enum
2. `workflow/models/step_result.py` — StepResult
3. `workflow/models/workflow_state.py` — FeatIssueWorkflowState 등
4. `workflow/models/workflow_instance.py` — WorkflowInstance
5. `workflow/contracts/feat_issue/` — BcCandidates, BcDecision, IssueDraft
6. `domain/issue/entities.py` — issue_templates.py 이동 (import alias 유지)

### Phase 2. Agent 레이어 분해

**목표**: agent_info.py → agents/*/{prompt,schema,adapter}.py 분해

1. `workflow/agents/relevant_bc_finder/` 3파일
2. `workflow/agents/bc_decision_maker/` 3파일
3. `workflow/agents/feat_issue_generator/` 3파일
4. `workflow/agents/feat_issue_regenerator/` 3파일
5. `workflow/executors/agent_executor.py`

### Phase 3. Step 구현

**목표**: services/*.py → steps/*/*.py 이동 + StepResult 반환으로 변경

1. `steps/feat_issue/find_relevant_bc_step.py`
2. `steps/feat_issue/decide_bc_step.py`
3. `steps/feat_issue/generate_issue_draft_step.py`
4. `steps/feat_issue/regenerate_issue_draft_step.py`
5. `steps/feat_issue/create_github_issue_step.py`
6. `steps/common/wait_for_human_action_step.py`
7. `steps/common/send_slack_message_step.py`

### Phase 4. Workflow Runtime

**목표**: lambda_worker의 _process() 로직 → workflow runtime으로 이관

1. `workflow/definitions/feat_issue_workflow.py`
2. `workflow/runtime/transition_resolver.py`
3. `workflow/runtime/human_gate_manager.py`
4. `workflow/runtime/workflow_runtime.py`

### Phase 5. Infrastructure 이동

**목표**: storage/ → infrastructure/ 경로 이동

1. DynamoDB store 이동
2. Memory store 이동
3. Queue publisher 이동
4. `infrastructure/github/github_client.py` 신규 (issue_creator 대체)

### Phase 6. Entrypoint 교체

**목표**: lambda_worker.py + controller/handler/slash.py → app/handlers/

1. `app/handlers/step_worker_handler.py`
2. `app/handlers/slack_interaction_handler.py`
3. `app/handlers/workflow_start_handler.py`
4. `src/local_server.py` 업데이트

### Phase 7. 기존 파일 제거

services/, agent/agent_info.py, agent/agent_factory.py, lambda_worker.py 제거.

---

## 현재 SQS 메시지 타입 → Workflow Event 매핑

| 현재 SQS type | 새 Workflow Event |
|---------------|-------------------|
| `pipeline_start` | workflow 시작 → `find_relevant_bc` step enqueue |
| `accept` | `wait_issue_confirmation` step resume → `create_github_issue` step |
| `reject` | `wait_issue_confirmation` step resume → `regenerate_issue_draft` step |
| `drop_restart` | `wait_issue_confirmation` step resume → `regenerate_issue_draft` step (drop 정보 포함) |
| `bc_accept` (계획) | `wait_bc_confirmation` step resume → `generate_issue_draft` step |
| `bc_reject` (계획) | `wait_bc_confirmation` step resume → `find_relevant_bc` step (재탐색) |

---

## 주요 설계 결정

### 1. WorkflowInstance.workflow_id

기존 `PendingRecord.pk`는 Slack message_ts를 PK로 사용했으나, 메시지가 교체될 때마다 PK가 바뀌는 문제가 있었다. 새 구조에서는 `workflow_id`를 UUID로 생성하고, Slack message_ts는 별도 필드(`slack_message_ts`)로 관리한다.

### 2. Pending Action Token

승인/거부 대기 시 `pending_action_token`을 생성하여 저장한다. Slack 버튼의 `value`에 이 token을 포함하여, 인터랙션 수신 시 workflow를 정확히 조회한다. 기존 message_ts 기반 조회보다 명확하다.

### 3. Step 간 계약

Step은 raw agent output이 아닌 `StepResult.state_patch`를 통해 데이터를 전달한다. `WorkflowState`는 각 step이 완료된 후 `state_patch`로만 업데이트된다.

### 4. MCP lifecycle

현재는 `_process()` 진입/종료에 `connect()/disconnect()`가 묶여 있다. 새 구조에서는 `AgentExecutor`가 MCP lifecycle을 관리하며, step 실행 단위로 격리된다.

---

## 테스트 전략

| 레이어 | 테스트 방식 |
|--------|-------------|
| Step | 각 step을 독립적으로 단위 테스트 (mock executor) |
| WorkflowRuntime | WorkflowDefinition + mock step 으로 transition 테스트 |
| Infrastructure | 기존 방식 유지 (moto, httpx mock) |
| E2E | local_server + 실제 agent 호출 (scripts/local_invoke.py) |
