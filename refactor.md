# 계층형 구조 리팩토링 계획 (MVC 기반)

---

## 현재 문제점

| 문제 | 위치 | 설명 |
|------|------|------|
| 단일 핸들러 과부하 | `slash_handler.py` | 이벤트 수신 + 파이프라인 실행 + 상태 관리를 한 파일이 담당 |
| 역할 불분명한 패키지명 | `slack/` | 프레젠테이션 레이어인데 네트워크 라이브러리명으로 표현됨 |
| 중첩 서브패키지 | `agent/agents/` | `agent` 안에 `agents`가 있어 탐색이 직관적이지 않음 |
| 데드코드 | `claude.py`, `claude_agents.py`, `tools.py` | 실제로 사용되지 않는 파일 3개 |
| 반복 코드 | `agent_factory.py` | 동일한 패턴 8회 반복, `_build` 공통 메서드로 추출 가능 |
| View 로직 분산 | `_reply.py`, `slash_handler.py` | `_build_reject_modal_blocks`가 핸들러 파일에 있음 |
| 도메인 모델 위치 | `agent/agents/issue_templates.py` | 도메인 모델이 agent 인프라 패키지 안에 위치 |

---

## 목표 레이어 구조

```
┌──────────────────────────────────┐
│  presentation/                   │  ← Controller + View
│  handler/ (이벤트 수신 + ack)    │
│  view/    (Block Kit 응답 빌더)  │
├──────────────────────────────────┤
│  service/                        │  ← 비즈니스 로직
│  (파이프라인 실행 오케스트레이션) │
├──────────────────────────────────┤
│  domain/                         │  ← 도메인 모델
│  (IssueTemplate, IssueContext)   │
├──────────────────────────────────┤
│  infra/          agent/          │  ← 인프라
│  (session)       (AI 실행)       │
└──────────────────────────────────┘
```

---

## 현재 → 목표 구조

```
src/                                       src/
├── config.py              ──────────────► ├── config.py              # 변경 없음
├── logging_config.py      ──────────────► ├── logging_config.py      # 변경 없음
├── main.py                ──────────────► ├── main.py                # import 경로만 수정
│
├── slack/                                 ├── presentation/          # RENAME: slack/ → presentation/
│   ├── app.py             ──────────────► │   ├── app.py             # 변경 없음
│   ├── event_router.py    ──────────────► │   ├── router.py          # RENAME: event_router → router
│   └── handlers/                          │   ├── view/              # NEW: View 서브패키지
│       ├── _reply.py      ──────────────► │   │   ├── blocks.py      # RENAME + _build_reject_modal_blocks 흡수
│       └── slash_modal_templates.py ────► │   │   └── modals.py      # RENAME
│       └── handler/                       │   └── handler/           # RENAME: handlers/ → handler/
│           ├── slash_handler.py ────────► │       ├── slash.py       # RENAME + 파이프라인 로직 제거
│           ├── mention_handler.py ──────► │       ├── mention.py     # RENAME
│           └── message_handler.py ──────► │       └── message.py     # RENAME
│
│                                          ├── service/               # NEW
│                                          │   └── issue_pipeline.py  # slash_handler에서 추출
│
│                                          ├── domain/                # NEW
├── agent/agents/issue_templates.py ─────► │   └── issue.py           # MOVE + RENAME
│
├── session/               ──────────────► ├── infra/                 # RENAME: session/ → infra/
│   ├── manager.py         ──────────────► │   └── session.py         # 두 파일 통합
│   └── models.py                          │
│
└── agent/                                 └── agent/
    ├── base.py            ──────────────►     ├── base.py            # 변경 없음
    ├── usage.py           ──────────────►     ├── usage.py           # 변경 없음
    ├── tools.py           → 삭제              ├── registry.py        # RENAME: agent_info.py
    ├── agents/                                ├── factory.py         # FLATTEN + 대폭 간소화
    │   ├── agent_info.py  ──────────────►     ├── mcp.py             # FLATTEN: agents/github.py
    │   ├── agent_factory.py ────────────►     └── runner/
    │   ├── github.py                              ├── models.py      # 변경 없음
    │   ├── issue_templates.py → domain/           └── openai.py      # 변경 없음
    │   └── claude_agents.py → 삭제
    └── runner/
        ├── models.py
        ├── openai.py
        └── claude.py → 삭제
```

---

## 파일별 변경 상세

### 삭제 (데드코드)

| 파일 | 이유 |
|------|------|
| `src/agent/tools.py` | `claude_agent_sdk` 기반, 미사용 |
| `src/agent/runner/claude.py` | `claude_agent_sdk` 기반, 미사용 |
| `src/agent/agents/claude_agents.py` | 미사용 |

### 이동 + 이름 변경

| 현재 | 목표 | 비고 |
|------|------|------|
| `slack/app.py` | `presentation/app.py` | import 경로 수정 |
| `slack/event_router.py` | `presentation/router.py` | 함수명 유지 |
| `slack/handlers/_reply.py` | `presentation/view/blocks.py` | `_build_reject_modal_blocks` 흡수 |
| `slack/handlers/slash_modal_templates.py` | `presentation/view/modals.py` | 변경 없음 |
| `slack/handlers/slash_handler.py` | `presentation/handler/slash.py` | 파이프라인 로직 제거 |
| `slack/handlers/mention_handler.py` | `presentation/handler/mention.py` | 변경 없음 |
| `slack/handlers/message_handler.py` | `presentation/handler/message.py` | 변경 없음 |
| `agent/agents/issue_templates.py` | `domain/issue.py` | 변경 없음 |
| `agent/agents/agent_info.py` | `agent/registry.py` | `agents/` 서브패키지 해소 |
| `agent/agents/agent_factory.py` | `agent/factory.py` | 대폭 간소화 |
| `agent/agents/github.py` | `agent/mcp.py` | `agents/` 서브패키지 해소 |
| `session/manager.py` + `session/models.py` | `infra/session.py` | 두 파일 통합 |

### 신규

| 파일 | 내용 |
|------|------|
| `service/issue_pipeline.py` | `_IssueContext`, `_execute_pipeline`, `handle_reject`, `handle_drop` |

---

## 핵심 변경 — `agent/factory.py` 간소화

현재 `agent_factory.py`는 동일한 패턴을 8회 반복한다.

```python
# 현재: 8개 메서드 각각 5줄 반복
@staticmethod
def feat_issue_gen() -> OpenAIAgent:
    info = AvailableAgents.FEAT_ISSUE_GEN.value
    return OpenAIAgent(agent_name=info.name, sdk_agent=Agent(
        name=info.name, instructions=info.sys_prompt,
        model=Model.GPT.GPT_5_MINI.name,
        mcp_servers=[GitHubMCPFactory.readProject()],
        output_type=info.output_format,
    ))
# ... 동일 패턴 7회 반복
```

```python
# 목표: _build 공통 메서드로 추출
class AgentFactory:

    @staticmethod
    def _build(key: AvailableAgents, mcp_server) -> OpenAIAgent:
        info = key.value
        return OpenAIAgent(
            agent_name=info.name,
            sdk_agent=Agent(
                name=info.name,
                instructions=info.sys_prompt,
                model=Model.GPT.GPT_5_MINI.name,
                mcp_servers=[mcp_server],
                output_type=info.output_format,
            ),
        )

    @staticmethod
    def inspector() -> OpenAIAgent:
        return AgentFactory._build(AvailableAgents.READ_TARGET_INSPECTOR, GitHubMCPFactory.readProjectTree())

    @staticmethod
    def issue_gen(subcommand: str) -> OpenAIAgent:
        key = {
            "feat": AvailableAgents.FEAT_ISSUE_GEN,
            "refactor": AvailableAgents.REFACTOR_ISSUE_GEN,
            "fix": AvailableAgents.FIX_ISSUE_GEN,
        }[subcommand]
        return AgentFactory._build(key, GitHubMCPFactory.readProject())

    @staticmethod
    def reissue_gen(subcommand: str) -> OpenAIAgent:
        key = {
            "feat": AvailableAgents.FEAT_REISSUE_GEN,
            "refactor": AvailableAgents.REFACTOR_REISSUE_GEN,
            "fix": AvailableAgents.FIX_REISSUE_GEN,
        }[subcommand]
        return AgentFactory._build(key, GitHubMCPFactory.readProject())
```

8개 메서드 → 3개 메서드, 팩토리 코드 70% 감소.

---

## 핵심 변경 — `slash.py` 책임 분리

```
현재 slash_handler.py                   리팩토링 후
──────────────────────                  ────────────────────────────────
_IssueContext          ──────────────►  service/issue_pipeline.py
_pending dict          ──────────────►  service/issue_pipeline.py
_issue_agent()         ──────────────►  service/issue_pipeline.py (AgentFactory.issue_gen으로 대체)
_reissue_agent()       ──────────────►  service/issue_pipeline.py (AgentFactory.reissue_gen으로 대체)
_build_reject_modal_blocks() ────────►  presentation/view/blocks.py
_execute_pipeline()    ──────────────►  service/issue_pipeline.py
_run_issue_pipeline()  ──────────────►  service/issue_pipeline.py
handle_feat/refactor/fix ────────────►  presentation/handler/slash.py (ack + views_open만)
handle_feat/refactor/fix_submit ─────►  presentation/handler/slash.py (ack + pipeline 호출)
handle_accept()        ──────────────►  presentation/handler/slash.py
handle_reject()        ──────────────►  presentation/handler/slash.py (ack + views_open만)
handle_reject_modal()  ──────────────►  presentation/handler/slash.py (ack + pipeline 호출)
handle_drop()          ──────────────►  presentation/handler/slash.py
```

---

## 단계별 실행 순서

각 단계는 독립적으로 커밋 가능하다.

### Step 1 — 데드코드 삭제
- `src/agent/tools.py` 삭제
- `src/agent/runner/claude.py` 삭제
- `src/agent/agents/claude_agents.py` 삭제

### Step 2 — domain/ 생성
- `src/agent/agents/issue_templates.py` → `src/domain/issue.py`
- import 경로 전체 수정

### Step 3 — agent/ 플랫화
- `src/agent/agents/agent_info.py` → `src/agent/registry.py`
- `src/agent/agents/github.py` → `src/agent/mcp.py`
- `src/agent/agents/agent_factory.py` → `src/agent/factory.py` (간소화 포함)
- `src/agent/agents/` 디렉토리 삭제

### Step 4 — session/ 삭제
- `src/session/` 패키지 전체 삭제
- `ISessionManager` 참조 제거 (slash_handler, mention_handler, event_router, main.py)

### Step 5 — service/ 생성
- `slash_handler.py`의 `_IssueContext`, `_execute_pipeline`, `_run_issue_pipeline`, `handle_reject_modal` 로직 → `src/service/issue_pipeline.py`

### Step 6 — presentation/ 생성
- `src/slack/` → `src/presentation/`
- `handlers/` → `handler/`
- `_reply.py` → `view/blocks.py` (`_build_reject_modal_blocks` 흡수)
- `slash_modal_templates.py` → `view/modals.py`
- `slash_handler.py` → `handler/slash.py` (경량화 버전)
- `event_router.py` → `router.py`

### Step 7 — main.py import 경로 정리

---

## 최종 구조

```
src/
├── config.py
├── logging_config.py
├── main.py
│
├── presentation/
│   ├── app.py
│   ├── router.py
│   ├── view/
│   │   ├── blocks.py       # build_issue_blocks, build_reject_modal_blocks
│   │   └── modals.py       # FeatModalInput, RefactorModalInput, FixModalInput
│   └── handler/
│       ├── slash.py        # ack + views_open + service 호출
│       ├── mention.py
│       └── message.py
│
├── service/
│   └── issue_pipeline.py   # IssueContext, execute_pipeline, handle_reject, handle_drop
│
├── domain/
│   └── issue.py            # BaseIssueTemplate, FeatTemplate, RefactorTemplate, FixTemplate
│
└── agent/
    ├── base.py
    ├── usage.py
    ├── registry.py         # AvailableAgents, AgentInfo
    ├── factory.py          # AgentFactory (_build 공통화)
    ├── mcp.py              # GitHubMCPFactory
    └── runner/
        ├── models.py
        └── openai.py
```
