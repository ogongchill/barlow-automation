# 세션 관리 모듈 구현

`src/session/` 패키지를 새로 생성한다. 기존 코드에는 세션 관리가 없다.

## 목표 구조

```
src/session/
├── __init__.py
├── manager.py    # SessionManager (인터페이스 + 구현)
└── models.py     # Session 데이터 구조
```

## 구현 지침

### models.py
```python
from dataclasses import dataclass, field
from enum import Enum

class SessionStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"

@dataclass
class Session:
    key: str           # "{channel_id}:{user_id}"
    status: SessionStatus = SessionStatus.IDLE
```

### manager.py
- `SessionManager` 클래스: `asyncio.Lock` 기반으로 동시성 제어
- 핵심 메서드:
  - `try_acquire(key: str) -> bool` — 세션 획득 시도, 이미 RUNNING이면 False
  - `release(key: str) -> None` — 세션 해제
  - `is_running(key: str) -> bool` — 현재 상태 조회
- 세션은 `dict[str, Session]`으로 인메모리 관리
- 동일 사용자 동시 요청: **기존 작업 우선, 새 요청 무시**

### 동시성 패턴
```python
async def try_acquire(self, key: str) -> bool:
    async with self._lock:
        session = self._sessions.get(key)
        if session and session.status == SessionStatus.RUNNING:
            return False
        self._sessions[key] = Session(key=key, status=SessionStatus.RUNNING)
        return True
```

### 공통 원칙 적용
- `session/` 패키지는 외부 패키지(`agent`, `slack`)에 의존하지 않는다
- `SessionManager`를 인터페이스로 추상화하여 추후 Redis 기반으로 교체 가능하도록 설계
- `app.py` 또는 `main.py`에서 인스턴스를 생성하여 의존성 주입
