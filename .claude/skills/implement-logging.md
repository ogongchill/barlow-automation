# 로그 모듈 구현

`src/logging/` 패키지를 새로 생성한다. 기존 `src/logging_config.py`는 시스템 로그 초기화 전용으로 유지.

## 목표 구조

```
src/logging/
├── __init__.py
├── agent_logger.py    # Agent 전용 파일 로거
└── models.py          # 로그 데이터 구조
```

## 로그 파일 구조 (분리 저장)

각 요청은 `trace_id` (UUID)로 연결. 파일은 날짜별 디렉토리로 관리.

```
logs/
├── agent_info/        # Agent 정보 (system prompt 등)
│   └── YYYY-MM-DD/
│       └── {trace_id}.json
├── interactions/      # 사용자 입력 + Agent 출력
│   └── YYYY-MM-DD/
│       └── {trace_id}.json
└── usage/             # 토큰 사용량 + 비용
    └── YYYY-MM-DD/
        └── {trace_id}.json
```

## 구현 지침

### models.py
```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AgentInfo:
    trace_id: str
    agent_name: str
    provider: str
    model: str
    system_prompt: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class InteractionLog:
    trace_id: str
    user_id: str
    channel_id: str
    user_input: str
    agent_output: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class UsageLog:
    trace_id: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    actual_cost_usd: float | None
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

### agent_logger.py
- `AgentLogger` 클래스
- `log(agent_info, interaction, usage)` — 세 파일에 각각 JSON으로 저장
- `trace_id`는 요청 시작 시 생성 (`uuid.uuid4().hex`)
- 파일 쓰기는 비동기 (`aiofiles` 또는 `asyncio.to_thread`)

### 연동 방식
- `IAgent.run()` 호출 전후에 `AgentLogger`가 로그 기록
- `AgentLogger`는 핸들러 레벨에서 주입받는다 (DI)
- `AgentLogger`는 `agent/`, `slack/` 패키지에 의존하지 않는다

### 공통 원칙 적용
- `logging/` 패키지는 외부 패키지에 의존하지 않는다 (stdlib + aiofiles만 사용)
- `trace_id`로 세 로그 파일을 cross-reference 가능
- 로그 실패는 시스템 로거(`logging`)에 warning으로 기록하고 요청 처리는 계속
