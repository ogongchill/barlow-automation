# Domain Feature-First 리팩토링 계획

## 목표

현재 `domain/workflow/` (수평 분리) 구조를 **feature-first 수직 분리** 구조로 전환한다.

---

## 목표 구조

```
domain/
  common/                          # 모든 워크플로우 공통 계약
    models/
      lifecycle.py                 # WorkflowStatus
      step_result.py               # StepResult
      workflow_instance.py         # WorkflowInstance, IWorkflowInstanceRepository
    ports/
      idempotency.py               # IIdempotencyRepository
    steps/
      base.py                      # Step Protocol

  feat/                            # feat 워크플로우 전용 도메인
    models/
      state.py                     # FeatIssueWorkflowState
      issue.py                     # FeatTemplate + to_github_body()
    steps/
      find_relevant_bc.py
      generate_issue_draft.py
      wait_confirmation.py
      regenerate_issue_draft.py
      create_github_issue.py
    agents/
      relevant_bc_finder/          # prompt.py, schema.py, adapter.py
      issue_generator/             # prompt.py, schema.py, adapter.py
      issue_regenerator/           # prompt.py, schema.py, adapter.py
    executor.py                    # feat 전용 FeatAgentKey + FeatAgentExecutor
    definition.py                  # step 그래프 + FIRST_STEP + RESUME_MAP

  refactor/
    models/
      issue.py                     # RefactorTemplate + to_github_body()
    agents/
      issue_generator/
      issue_regenerator/
    executor.py
    definition.py

  fix/
    models/
      issue.py                     # FixTemplate + to_github_body()
    agents/
      issue_generator/
      issue_regenerator/
    executor.py
    definition.py
```

---

## Phase 1: domain/common/ 생성

| 현재 | 목표 |
|------|------|
| `domain/workflow/models/lifecycle.py` | `domain/common/models/lifecycle.py` |
| `domain/workflow/models/step_result.py` | `domain/common/models/step_result.py` |
| `domain/workflow/models/workflow_instance.py` | `domain/common/models/workflow_instance.py` |
| `domain/idempotency.py` | `domain/common/ports/idempotency.py` |

신규: `domain/common/steps/base.py` (Step Protocol)

import 수정:
- `infrastructure/storage/dynamodb/pending_action_store.py`
- `infrastructure/storage/memory/pending_action_store.py`
- `infrastructure/storage/dynamodb/workflow_instance_store.py`
- `infrastructure/storage/memory/workflow_instance_store.py`
- `app/workflow_runtime.py`
- `app/handlers/step_worker_handler.py`
- `controller/handler/slash.py`

---

## Phase 2: domain/feat/ 생성

| 현재 | 목표 |
|------|------|
| `domain/workflow/models/workflow_state.py` | `domain/feat/models/state.py` |
| `domain/issue/entities.py` (FeatTemplate) + rendering | `domain/feat/models/issue.py` |
| `domain/workflow/agents/relevant_bc_finder/` | `domain/feat/agents/relevant_bc_finder/` |
| `domain/workflow/agents/feat_issue_generator/` | `domain/feat/agents/issue_generator/` |
| `domain/workflow/agents/feat_issue_regenerator/` | `domain/feat/agents/issue_regenerator/` |
| `domain/workflow/steps/feat_issue/find_relevant_bc_step.py` | `domain/feat/steps/find_relevant_bc.py` |
| `domain/workflow/steps/feat_issue/generate_issue_draft_step.py` | `domain/feat/steps/generate_issue_draft.py` |
| `domain/workflow/steps/common/wait_issue_confirmation_step.py` | `domain/feat/steps/wait_confirmation.py` |
| `domain/workflow/steps/feat_issue/regenerate_issue_draft_step.py` | `domain/feat/steps/regenerate_issue_draft.py` |
| `domain/workflow/steps/feat_issue/create_github_issue_step.py` | `domain/feat/steps/create_github_issue.py` |
| `domain/workflow/executors/agent_executor.py` (feat 부분) | `domain/feat/executor.py` |

신규: `domain/feat/definition.py` (StepNode, GRAPH, FIRST_STEP, RESUME_MAP)

---

## Phase 3: domain/refactor/, domain/fix/ 생성

| 현재 | 목표 |
|------|------|
| `domain/issue/entities.py` (RefactorTemplate) + rendering | `domain/refactor/models/issue.py` |
| `domain/issue/entities.py` (FixTemplate) + rendering | `domain/fix/models/issue.py` |
| `agent_info.py` REFACTOR_* prompts | `domain/refactor/agents/*/prompt.py` |
| `agent_info.py` FIX_* prompts | `domain/fix/agents/*/prompt.py` |

---

## Phase 4: app/workflow_runtime.py 갱신

`WorkflowRuntime._build_step()` 및 `_NEXT_STEP`, `_RESUME_STEP` dict를
각 feature `definition.py`의 GRAPH 참조로 교체.

```python
_DEFINITIONS = {
    "feat_issue":     feat_definition,
    "refactor_issue": refactor_definition,
    "fix_issue":      fix_definition,
}
```

---

## Phase 5: 구 패키지 삭제

- `domain/workflow/` 전체
- `domain/issue/` 전체
- `domain/idempotency.py`

---

## 설계 원칙

| 원칙 | 적용 |
|------|------|
| feature-first | feat/refactor/fix 각자 models/steps/agents/executor/definition 보유 |
| 공통 계약은 common/ | WorkflowInstance, StepResult, IWorkflowInstanceRepository |
| AgentExecutor 분리 | 각 feature executor.py가 자신의 agent만 빌드 |
| 렌더링 응집 | to_github_body()를 Template 클래스 메서드로 통합 |
| Step 인터페이스 | domain/common/steps/base.py의 Step Protocol |
