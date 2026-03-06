# Slack 통신 모듈 구현

현재 `src/slack/` 구조를 읽고 readme.md의 요구사항에 맞게 리팩터링한다.

## 목표 구조

```
src/slack/
├── app.py             # AsyncApp 팩토리 (기존 유지)
├── event_router.py    # 이벤트 → 핸들러 라우팅
└── handlers/
    ├── __init__.py
    ├── mention_handler.py   # @mention 이벤트
    ├── slash_handler.py     # slash command 이벤트
    └── message_handler.py   # DM 이벤트
```

## 구현 지침

### event_router.py
- `register_routes(app: AsyncApp, ...)` 함수로 모든 핸들러를 app에 등록
- 각 이벤트 타입을 해당 핸들러로 위임
- `app.py`는 `event_router.py`만 호출한다 (`handlers/` 직접 참조 금지)

### handlers/
- 각 핸들러 파일은 단일 이벤트 타입만 처리
- `ack()` 즉시 호출 → background task로 실제 처리 (Socket Mode 패턴)
- 세션 관리는 `session.manager.SessionManager` 인터페이스를 통해 처리
- agent 호출은 `agent.base.IAgent` 인터페이스만 사용

### 세션 연동 패턴
```python
session_key = f"{channel_id}:{user_id}"
if not session_manager.try_acquire(session_key):
    await say("이미 처리 중인 요청이 있습니다.")
    return
try:
    response, usage = await agent.run(message)
finally:
    session_manager.release(session_key)
```

### 공통 원칙 적용
- `handlers/`는 `IAgent`, `SessionManager` 인터페이스만 import
- 핸들러 함수 시그니처에 type hint 필수
- 에러는 핸들러 내에서 처리, 사용자에게 안내 메시지 반환

## 기존 코드 참고
- `src/slack/handlers.py` — `_build_reply()` 유틸 함수 재사용 가능
- `src/slack/app.py` — `create_app()` 구조 유지, `register_handlers` → `register_routes`로 교체
