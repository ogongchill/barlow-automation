# Barlow Automation — 동작 요약

Slack 슬래시 커맨드로 개발자가 기능/리팩토링/버그 요청을 입력하면, AI가 GitHub 코드를 분석해 GitHub 이슈 초안을 자동 생성하는 시스템.

---

## 전체 흐름

```
개발자 (Slack)
    │
    ├─ /feat | /refactor | /fix
    │         │
    │    [Modal 오픈]
    │    구조화된 입력 폼 (FeatModalInput 등)
    │         │
    │    [Modal 제출]
    │         │
    │    to_prompt() → 텍스트 직렬화
    │         │
    ├── Inspector Agent (READ_TARGET_INSPECTOR)
    │   GitHub MCP: get_repository_tree, get_file_contents
    │   → request_summary + searchTarget[] (found_dir)
    │         │
    ├── Issue Gen Agent (FEAT/REFACTOR/FIX_ISSUE_GEN)
    │   GitHub MCP: get_file_contents, search_code
    │   → 구조화된 이슈 초안 (FeatTemplate 등)
    │         │
    │   [Slack 메시지: 수락 / 재요청 / 드롭 후 재탐색]
    │
    ├─ 수락 → 세션 해제, 완료
    │
    ├─ 재요청 → [Modal: 체크박스로 제외 항목 선택 + 추가 요구사항]
    │               │
    │          without(dropped_ids) → 코드 레벨 항목 제거
    │               │
    │          Reissue Agent (FEAT/REFACTOR/FIX_REISSUE_GEN)
    │          입력: [Inspector Context] + [Current Issue Draft] + Additional requirements
    │               │
    │          [Slack 메시지: 수락 / 재요청 / 드롭 후 재탐색]
    │
    └─ 드롭 후 재탐색 → Inspector부터 전체 파이프라인 재실행
```

---

## 모듈별 역할

### `src/main.py`
- 진입점. GitHub MCP 서버 연결 → Slack Socket Mode 시작 → 종료 시 MCP 해제.

### `src/slack/`
| 파일 | 역할 |
|------|------|
| `app.py` | `AsyncApp` + `SocketModeHandler` 생성 |
| `event_router.py` | 핸들러 등록 라우터 (`mention`, `slash`, `message`) |
| `handlers/slash_handler.py` | 슬래시 커맨드 + 버튼 액션 + Modal 처리 |
| `handlers/slash_modal_templates.py` | Modal 입력 폼 스키마 (`FeatModalInput`, `RefactorModalInput`, `FixModalInput`) |
| `handlers/_reply.py` | Block Kit 응답 빌더 (수락/재요청/드롭 버튼 포함) |

### `src/session/`
- `InMemorySessionManager`: `(channel:user)` 키로 중복 요청 방지. `try_acquire` / `release` 기반 락.

### `src/agent/`
| 파일 | 역할 |
|------|------|
| `agents/agent_info.py` | Agent 이름 + 시스템 프롬프트 + 출력 스키마 레지스트리 (`AvailableAgents` enum) |
| `agents/agent_factory.py` | `OpenAIAgent` 인스턴스 생성 팩토리 |
| `agents/issue_templates.py` | 이슈 출력 스키마 (`FeatTemplate`, `RefactorTemplate`, `FixTemplate`) + `droppable_items()` / `without()` |
| `agents/github.py` | GitHub MCP 서버 팩토리 (`readProjectTree`, `readProject`) |
| `runner/openai.py` | OpenAI Agent SDK `Runner.run()` 래퍼 → `AgentResult` 반환 |

---

## Agent 파이프라인 상세

### 1단계 — Inspector (`READ_TARGET_INSPECTOR`)
- **도구**: `get_repository_tree`, `get_file_contents`
- **입력**: 사용자 요청 텍스트 (Modal `to_prompt()` 결과)
- **출력**: `{ request_summary, searchTarget[{ id, description, found_dir }] }`
- 실제 관찰된 경로만 포함 (추측 금지)

### 2단계 — Issue Gen (`FEAT/REFACTOR/FIX_ISSUE_GEN`)
- **도구**: `get_file_contents`, `search_code`
- **입력**: Inspector 출력 전체 (JSON 문자열)
- **출력**: `FeatTemplate` / `RefactorTemplate` / `FixTemplate`

### 재생성 — Reissue Agent (`FEAT/REFACTOR/FIX_REISSUE_GEN`)
- **도구**: `get_file_contents`, `search_code`
- **입력**:
  ```
  [Inspector Context]
  {inspector_output}

  [Current Issue Draft]
  {filtered_draft}          ← without(dropped_ids) 결과

  ---
  Additional requirements: {사용자 추가 요구사항}  ← 있을 때만
  ```
- 초안 항목은 코드가 제거하고, 추가/수정은 LLM이 담당

---

## 슬래시 커맨드 Modal 입력 스키마

| 커맨드 | CALLBACK_ID | 필수 필드 | 선택 필드 |
|--------|-------------|----------|----------|
| `/feat` | `feat_submit` | 기능 이름, 배경, 기능 목록, 제약 조건 | 설계 요구사항 |
| `/refactor` | `refactor_submit` | 리팩토링 대상, 배경, AS-IS, TO-BE | 제약 조건 |
| `/fix` | `fix_submit` | 버그 제목, 증상, 재현 조건, 예상 동작 | 관련 영역 |

---

## 이슈 템플릿 구조

### FeatTemplate
- `issue_title`, `about`, `new_features[]`, `domain_rules[]`, `domain_constraints[]`

### RefactorTemplate
- `issue_title`, `about`, `goals[{ as_is[], to_be[] }]`, `domain_rules[]`, `domain_constraints[]`

### FixTemplate
- `issue_title`, `about`, `problems[{ issue, suggestion }]`, `implementation[{ step, todo }]`, `domain_rules[]`, `domain_constraints[]`

---

## 세션 관리

- 슬래시 커맨드 실행 시 `(channel:user)` 세션 획득
- 이슈 **수락** 시 세션 해제
- 오류 발생 시 즉시 세션 해제
- **재요청/드롭**은 세션을 유지한 채 처리 (완료 후 수락으로 해제)
- 세션 중 동일 사용자의 중복 요청 차단

---

## GitHub MCP 서버

- Remote endpoint: `https://api.githubcopilot.com/mcp/`
- 앱 시작 시 연결, 종료 시 해제 (`GitHubMCPFactory.connect/disconnect`)
- `readProjectTree`: 트리 탐색용 (`READ_TREE` toolset)
- `readProject`: 파일 읽기용 (`READ_FILES` toolset)
- 모두 read-only (`X-MCP-Readonly: true`)
