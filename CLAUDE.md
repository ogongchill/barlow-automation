# Barlow Automation - 개발 원칙

## 목적
Slack 기반 AI 티켓 자동화 시스템.
개발자가 Slack에서 자연어로 요청하면 AI가 GitHub 코드를 분석하여 개발 티켓을 자동 생성한다.

---

## 공통 원칙 (모든 모듈에 적용)

### 패키지 설계
- 패키지 간 의존성은 인터페이스(ABC, Protocol)를 통해서만 이루어진다
- 하나의 `.py` 파일은 cohesion이 높아야 하며, 파일명만으로 내용을 예상 가능해야 한다
- agent 동작 수정 및 출력 형식 변경에 열린 구조여야 한다 (OCP)

### 코드 스타일
- 가독성 최우선 — 변수명, 함수명으로 의도를 드러낸다
- Python 관용 구조 사용: `dataclass`, `ABC`, `Protocol`, `Enum`, `TypeAlias`
- 객체지향 설계: 역할별 클래스 분리, 단일 책임 원칙
- 데이터 구조는 `dataclass` 또는 `Pydantic`으로 명확히 정의
- 모든 함수/메서드에 type hint 필수 (return type 포함)
- 모듈 최상단에 한 줄 docstring으로 파일 역할 명시

### 금지 사항
- 패키지 간 구체 클래스 직접 import (인터페이스만 노출)
- 타입 없는 dict를 데이터 전달 수단으로 사용
- 전역 상태 공유 (singleton 제외, config/logger는 허용)

---

## 프로젝트 구조 (목표)

```
src/
├── config.py              # 환경 변수 기반 설정
├── logging_config.py      # 로깅 초기화
├── main.py                # 진입점
│
├── slack/                 # 1. Slack 통신 모듈
│   ├── app.py             # AsyncApp 팩토리
│   ├── event_router.py    # 이벤트 분기 (Router)
│   └── handlers/
│       ├── mention_handler.py
│       ├── slash_handler.py
│       └── message_handler.py
│
├── session/               # 2. 세션 관리 모듈
│   ├── manager.py         # SessionManager
│   └── models.py          # Session 데이터 구조
│
├── agent/                 # 3. Agent 관리 모듈
│   ├── base.py            # IAgent 인터페이스
│   ├── usage.py           # 토큰/비용 추적
│   ├── tools.py           # MCP 서버 빌더
│   ├── agents/            # 역할별 Agent 팩토리
│   │   └── github.py
│   └── runner/            # LLM 제공자별 구현
│       ├── models.py      # 모델 레지스트리
│       ├── claude.py      # Claude Agent SDK
│       └── openai.py      # OpenAI Agent SDK
│
└── logging/               # 4. 로그 모듈
    ├── agent_logger.py    # Agent 전용 파일 로거
    └── models.py          # 로그 데이터 구조
```

---

## 기술 스택
- Python 3.12+
- Slack Bolt (Socket Mode, Async)
- Claude Agent SDK (`claude_agent_sdk`)
- OpenAI Agent SDK
- GitHub MCP (`@modelcontextprotocol/server-github`)
