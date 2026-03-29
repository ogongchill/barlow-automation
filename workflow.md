# Feat Request Workflow

슬래시 커맨드 `/feat` 입력부터 GitHub 이슈 생성까지의 전체 흐름.

---

```mermaid
sequenceDiagram
    actor User as 사용자 (Slack)

    box System
        participant Ack as Lambda<br/>barlow-slack-ack
        participant SQS as SQS<br/>barlow-queue
        participant Worker as Lambda<br/>barlow-automation-worker
        participant DB as DynamoDB
    end

    box Agent
        participant Agent as AI Agent<br/>(Claude / GPT)
        participant MCP as GitHub MCP
    end

    participant Slack as Slack API
    participant GH as GitHub API

    %% ── 1. 요청 진입 ──────────────────────────────────────────
    User->>Ack: /feat "요청 내용"
    Ack->>DB: active-session 중복 확인 (GetItem)
    alt 진행 중인 워크플로우 있음
        Ack->>Slack: "이미 진행 중인 요청이 있습니다"
    else 없음
        Ack->>DB: pending-action dedup 등록 (PutItem, TTL 1h)
        Ack->>DB: workflow 레코드 생성 (PutItem, TTL 24h)
        Ack->>DB: active-session 등록 (PutItem, TTL 24h)
        Ack->>SQS: 메시지 전송 (workflow_id, step=FIND_RELEVANT_BC)
        Ack->>User: "요청을 받았습니다" ack (3초 이내)
    end

    %% ── 2. Worker 실행 #1: 관련 BC 탐색 ──────────────────────
    SQS-->>Worker: 트리거 (batch_size=1)
    Worker->>DB: workflow 조회 (GetItem)
    Worker->>Slack: "관련 바운디드 컨텍스트를 찾고 있습니다..." 메시지

    rect rgb(230, 240, 255)
        Note over Agent,MCP: Agent 실행 — FIND_RELEVANT_BC
        Worker->>Agent: run(사용자 요청)
        Agent->>MCP: 코드베이스 구조 탐색
        MCP->>GH: 파일 목록 / 코드 조회
        GH-->>MCP: 코드 내용
        MCP-->>Agent: 탐색 결과
        Agent-->>Worker: 관련 BC 목록
    end

    Worker->>DB: 결과 저장 + step=FIND_RELEVANT_ISSUE (UpdateItem)
    Worker->>SQS: 다음 메시지 전송

    %% ── 3. Worker 실행 #2: 관련 이슈 탐색 ───────────────────
    SQS-->>Worker: 트리거
    Worker->>DB: workflow 조회
    Worker->>Slack: "기존 이슈를 확인하고 있습니다..." 메시지

    rect rgb(230, 240, 255)
        Note over Agent,MCP: Agent 실행 — FIND_RELEVANT_ISSUE
        Worker->>Agent: run(요청 + BC 목록)
        Agent->>MCP: GitHub Issues 목록 조회
        MCP->>GH: GET /repos/.../issues
        GH-->>MCP: 이슈 목록
        MCP-->>Agent: 이슈 목록
        Agent-->>Worker: 관련 이슈 + 중복 판정 (Decision)
    end

    Worker->>DB: 결과 저장 + step=WAIT_ISSUE_DECISION (UpdateItem)
    Worker->>Slack: 이슈 결정 모달 전송 (views.open)
    Note over Worker,Slack: EXTEND_EXISTING / BLOCK_EXISTING /<br/>REJECT_DUPLICATE / CREATE_NEW_INDEPENDENT

    %% ── WAIT: 사용자 결정 대기 ────────────────────────────────
    Note over User,DB: ── WAIT — Lambda 종료, DynamoDB가 상태 보존 ──

    %% ── 4. 사용자 결정 → Ack → SQS ──────────────────────────
    User->>Ack: 모달 선택 제출
    Ack->>DB: pending-action dedup 확인
    Ack->>DB: 결정 내용 저장 + step=GENERATE_ISSUE_DRAFT (UpdateItem)
    Ack->>SQS: 다음 메시지 전송
    Ack->>User: "선택을 받았습니다" ack

    %% ── 5. Worker 실행 #3: 이슈 초안 생성 ───────────────────
    SQS-->>Worker: 트리거
    Worker->>DB: workflow 조회 (결정 포함)
    Worker->>Slack: "이슈를 작성하고 있습니다..." 메시지

    rect rgb(230, 240, 255)
        Note over Agent,MCP: Agent 실행 — GENERATE_ISSUE_DRAFT
        Worker->>Agent: run(요청 + BC + 결정 + 기존이슈)
        Agent->>MCP: 관련 코드 상세 조회
        MCP->>GH: 파일 내용 조회
        GH-->>MCP: 코드 내용
        MCP-->>Agent: 상세 컨텍스트
        Agent-->>Worker: 이슈 초안 (title, body, labels)
    end

    Worker->>DB: 초안 저장 + step=WAIT_CONFIRMATION (UpdateItem)
    Worker->>Slack: 이슈 초안 미리보기 + 확인/취소 버튼 전송

    %% ── WAIT: 최종 확인 대기 ──────────────────────────────────
    Note over User,DB: ── WAIT — Lambda 종료, DynamoDB가 상태 보존 ──

    %% ── 6a. 확인 → GitHub 이슈 생성 ─────────────────────────
    alt 확인 (issue_confirm)
        User->>Ack: "확인" 버튼 클릭
        Ack->>DB: step=CREATE_GITHUB_ISSUE (UpdateItem)
        Ack->>SQS: 다음 메시지 전송
        Ack->>User: "이슈를 생성하고 있습니다" ack

        SQS-->>Worker: 트리거
        Worker->>DB: workflow 조회
        Worker->>GH: POST /repos/{owner}/{repo}/issues
        alt Decision == BLOCK_EXISTING
            Worker->>GH: POST /repos/.../issues/{anchor}/timeline
        else Decision == EXTEND_EXISTING
            Worker->>GH: POST /repos/.../issues/{parent}/sub_issues
        end
        Worker->>Slack: "이슈가 생성되었습니다 {url}"
        Worker->>DB: active-session 삭제 (DeleteItem)
        Worker->>DB: workflow TTL 단축 (UpdateItem)

    %% ── 6b. 취소 ─────────────────────────────────────────────
    else 취소 (issue_drop)
        User->>Ack: "취소" 버튼 클릭
        Ack->>DB: active-session 삭제 (DeleteItem)
        Ack->>DB: workflow 상태=CANCELLED (UpdateItem)
        Ack->>User: "요청이 취소되었습니다"
    end
```

---

## Lambda 실행 경계

| 실행 회차 | Step | 트리거 | Agent 호출 |
|-----------|------|--------|-----------|
| #1 | FIND_RELEVANT_BC | `/feat` 슬래시 커맨드 | O — 코드베이스 BC 탐색 |
| #2 | FIND_RELEVANT_ISSUE | SQS | O — 기존 이슈 분석 + Decision |
| WAIT | WAIT_ISSUE_DECISION | 사용자 모달 응답 대기 | — |
| #3 | GENERATE_ISSUE_DRAFT | 모달 제출 | O — 이슈 초안 생성 |
| WAIT | WAIT_CONFIRMATION | 사용자 확인 버튼 대기 | — |
| #4 | CREATE_GITHUB_ISSUE | 확인 버튼 클릭 | — (REST API 직접 호출) |

각 WAIT 구간에서 Lambda는 종료된다. DynamoDB가 상태를 보존하여 다음 실행에서 이어받는다.

## 역할 분리

| 구분 | 담당 |
|------|------|
| **System** | 이벤트 라우팅, dedup, 상태 저장/조회, Slack ack |
| **Agent** | 코드 분석, 이슈 탐색 및 판정, 이슈 초안 작성 |

Agent는 Worker Lambda 내부에서 호출되며, MCP를 통해서만 GitHub에 접근한다.
Agent 실행 결과는 Worker가 DynamoDB에 저장하여 다음 실행으로 전달한다.

## 멱등성 보장

- **pending-action**: Slack action_ts 기반 dedup (TTL 1h). 동일 버튼을 두 번 눌러도 한 번만 처리.
- **active-session**: channel+user 키로 동시 워크플로우 중복 차단 (TTL 24h).
- **SQS batch_size=1**: 동일 메시지가 두 Worker에게 동시 전달되지 않음.

---

## Step별 흐름 요약

> **Worker가 "무엇을 할지" 결정하는 방법**
> - **SQS 메시지의 `event_type`(action)** → `RESUME_MAP[action]`으로 다음 step 결정
> - **DynamoDB** → step 라우팅이 아닌 누적 상태(BC 목록·이슈 목록·초안 등) 컨텍스트 제공
> - Worker 한 실행 안에서 `WAIT` / `STOP` 신호가 나올 때까지 step을 연속 실행

```mermaid
flowchart TD
    S(["/feat 입력"]) --> S1

    subgraph SYS1["System — Ack Lambda"]
        S1["중복 세션 확인"]
        S1 -->|중복| DUP(["이미 진행 중 안내\n종료"])
        S1 -->|없음| S2["workflow / session 생성\nSQS: event_type=pipeline_start"]
    end

    S2 --> W1

    subgraph W1BOX["System — Worker #1  ·  event_type=pipeline_start"]
        W1SQS["SQS 수신\nevent_type → runtime.start()"]
        W1DB["DynamoDB 조회\n누적 상태 로드"]
        W1SQS --> W1DB

        W1DB --> A1
        subgraph A1["Agent — find_relevant_bc"]
            A1A["GitHub MCP 코드베이스 탐색"] --> A1B["관련 BC 목록"]
        end

        A1B --> W1CONT["CONTINUE\n→ next_step: find_relevant_issue"]
        W1CONT --> A2
        subgraph A2["Agent — find_relevant_issue"]
            A2A["GitHub Issues 조회\n중복 판정"] --> A2B["Decision 포함 결과"]
        end

        A2B --> W1WAIT["WAIT_FOR_USER\n상태 저장 후 Lambda 종료\n→ 이슈 결정 모달 전송"]
    end

    W1WAIT --> WAIT1(["⏸ WAIT\n사용자 모달 선택 대기"])

    WAIT1 -->|"사용자 선택\n(extend / block / reject / new)"| SYS2

    subgraph SYS2["System — Ack Lambda"]
        SYS2A["dedup 확인\nSQS: event_type=extend_existing 등"]
    end

    SYS2A --> W2

    subgraph W2BOX["System — Worker #2  ·  event_type=extend_existing|block_existing|…"]
        W2SQS["SQS 수신\nRESUME_MAP[action] → generate_issue_draft"]
        W2DB["DynamoDB 조회\n누적 상태 로드 (BC + Decision 포함)"]
        W2SQS --> W2DB

        W2DB --> A3
        subgraph A3["Agent — generate_issue_draft"]
            A3A["코드 상세 분석\n이슈 초안 작성"] --> A3B["초안 (title · body · labels)"]
        end

        A3B --> W2WAIT["WAIT_FOR_USER\n상태 저장 후 Lambda 종료\n→ 초안 미리보기 + 확인/취소 버튼 전송"]
    end

    W2WAIT --> WAIT2(["⏸ WAIT\n사용자 확인 대기"])

    WAIT2 -->|"확인\nevent_type=accept"| SYS3
    WAIT2 -->|"취소\nevent_type=drop_restart"| CANCEL

    subgraph SYS3["System — Ack Lambda"]
        SYS3A["dedup 확인\nSQS: event_type=accept"]
    end

    SYS3A --> W3

    subgraph W3BOX["System — Worker #3  ·  event_type=accept"]
        W3SQS["SQS 수신\nRESUME_MAP[accept] → create_github_issue"]
        W3DB["DynamoDB 조회\n누적 상태 로드 (초안 포함)"]
        W3SQS --> W3DB
        W3DB --> GH["GitHub REST API\nPOST /issues"]
        GH --> REL{"Decision?"}
        REL -->|BLOCK_EXISTING| BLK["blocking 관계 설정"]
        REL -->|EXTEND_EXISTING| SUB["sub_issues 등록"]
        REL -->|그 외| DONE
        BLK --> DONE
        SUB --> DONE
        DONE["STOP\nSlack 이슈 URL 전송\nactive-session 삭제"]
    end

    CANCEL["active-session 삭제\nworkflow CANCELLED"]

    DONE --> E([종료])
    CANCEL --> E

    style A1 fill:#dce8ff,stroke:#6699cc
    style A2 fill:#dce8ff,stroke:#6699cc
    style A3 fill:#dce8ff,stroke:#6699cc
    style WAIT1 fill:#fff3cd,stroke:#d4a000
    style WAIT2 fill:#fff3cd,stroke:#d4a000
    style CANCEL fill:#fde8e8,stroke:#cc4444
    style W1CONT fill:#e8f5e9,stroke:#4caf50
```

### step 연속 실행 구조 (Worker #1 예시)

Worker 한 번의 Lambda 실행 안에서 `_execute_until_wait()` 루프가 돌며 여러 step을 처리한다.

```
SQS: pipeline_start
  └─ runtime.start()
       └─ _execute_until_wait()
            ├─ find_relevant_bc  → CONTINUE → next_step 설정 후 계속
            ├─ find_relevant_issue → WAIT_FOR_USER → 저장 후 break
            └─ (Lambda 종료)
```

```
SQS: accept
  └─ runtime.resume(action="accept")
       └─ RESUME_MAP["accept"] = "create_github_issue"
       └─ _execute_until_wait()
            ├─ create_github_issue → STOP → 저장 후 break
            └─ (Lambda 종료)
```

---

## 상태 다이어그램

`WorkflowStatus` × `current_step` 기준. RUNNING 상태는 Lambda 실행 중, WAITING은 Lambda 종료 후 사용자 응답 대기.

```mermaid
stateDiagram-v2
    [*] --> RUNNING_find_relevant_bc : /feat 입력\n(pipeline_start)

    state "RUNNING" as RUNNING {
        state "find_relevant_bc" as s1
        state "find_relevant_issue" as s2
        state "generate_issue_draft" as s3
        state "regenerate_issue_draft" as s4
        state "create_github_issue" as s5
        state "reject_end" as s6

        s1 --> s2 : CONTINUE
        s2 --> WAITING_issue_decision : WAIT_FOR_USER
        s3 --> WAITING_confirmation : WAIT_FOR_USER
        s4 --> WAITING_confirmation : WAIT_FOR_USER
        s5 --> COMPLETED : STOP
        s6 --> COMPLETED : STOP
    }

    [*] --> s1

    state "WAITING" as WAITING {
        state "wait_issue_decision" as w1
        state "wait_confirmation" as w2
    }

    WAITING_issue_decision --> w1
    WAITING_confirmation --> w2

    w1 --> s3 : extend_existing\nblock_existing\ncreate_new_independent
    w1 --> s6 : reject_duplicate
    w1 --> CANCELLED : /drop

    w2 --> s5 : accept
    w2 --> s4 : reject / drop_restart
    w2 --> CANCELLED : /drop

    COMPLETED --> [*]
    CANCELLED --> [*]
    FAILED --> [*]
```

### 전이 요약

| 현재 상태 | 트리거 | 다음 상태 |
|---|---|---|
| `[시작]` | `/feat` | RUNNING · find_relevant_bc |
| find_relevant_bc | CONTINUE | find_relevant_issue |
| find_relevant_issue | CONTINUE → WAIT | WAITING · wait_issue_decision |
| wait_issue_decision | extend / block / create_new | RUNNING · generate_issue_draft |
| wait_issue_decision | reject_duplicate | RUNNING · reject_end → COMPLETED |
| wait_issue_decision | /drop | CANCELLED |
| generate_issue_draft | CONTINUE → WAIT | WAITING · wait_confirmation |
| wait_confirmation | accept | RUNNING · create_github_issue → COMPLETED |
| wait_confirmation | reject / drop_restart | RUNNING · regenerate_issue_draft → WAITING |
| wait_confirmation | /drop | CANCELLED |
