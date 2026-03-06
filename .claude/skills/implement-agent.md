# Agent 관리 모듈 구현

`src/agent/` 구조를 읽고 readme.md의 요구사항에 맞게 확장한다.

## 현재 상태
- `base.py`: `IAgent` 인터페이스 (name, provider, run)
- `runner/claude.py`: Claude Agent SDK 구현 (추정)
- `agents/github.py`: GitHub-capable Claude Agent 팩토리

## 목표 구조

```
src/agent/
├── base.py            # IAgent 인터페이스 (유지)
├── usage.py           # 토큰/비용 추적 (유지)
├── tools.py           # MCP 서버 빌더 (유지)
├── agents/            # 역할별 Agent 팩토리
│   ├── github.py      # GitHub 분석 Agent (기존)
│   ├── planner.py     # Planner Agent (신규)
│   ├── spec.py        # Spec Generator Agent (신규)
│   └── reviewer.py    # Reviewer Agent (신규)
└── runner/
    ├── models.py      # 모델 레지스트리 (유지)
    ├── claude.py      # Claude runner (유지)
    └── openai.py      # OpenAI runner (신규)
```

## 구현 지침

### IAgent 확장 (base.py)
현재 `run(message: str) -> tuple[str, RequestUsage]` 시그니처 유지.
필요 시 `stream()` 메서드 추가 검토 (인터페이스 변경이므로 사용자 확인 후).

### 역할별 Agent 팩토리 (agents/)
각 파일은 `create() -> IAgent` 함수만 export.
- `planner.py`: 요청 분류 및 작업 계획 수립 (기능추가/버그수정/리팩터링)
- `spec.py`: API Spec, 변경 파일 목록, 요구사항 명세 작성
- `reviewer.py`: 생성된 티켓 검토 및 수정 반영

각 Agent의 system prompt는 해당 파일 최상단 `SYSTEM_PROMPT` 상수로 정의.

### 티켓 발급 동작
- 사용자가 accept하기 전까지 이전 버전 내역을 tool로 저장
- 저장 tool은 `tools.py`에 구현, LLM에게 호출 권한 위임
- 버전 이력: `list[TicketVersion]` (dataclass) 형태로 관리

### OpenAI runner (runner/openai.py)
- `IAgent`를 구현하는 `OpenAIAgent` 클래스
- `ClaudeAgent`와 동일한 인터페이스, `RequestUsage` 반환 구조 동일
- `runner/models.py`의 `Model.GPT` 사용

### 비용 추적
- 작업 완료 후 `RequestUsage.format()` 결과를 Slack 응답에 포함
- 기존 `usage.py` 구조 유지

### 공통 원칙 적용
- `agents/`는 `runner/`의 구체 클래스를 직접 import 가능 (팩토리 역할)
- `slack/`, `session/` 등 상위 모듈은 `IAgent`만 참조
- 각 runner는 독립적으로 테스트 가능해야 한다
