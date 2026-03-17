#!/usr/bin/env python3
"""로컬 Lambda invoke 시뮬레이터.

실제 OpenAI Agent를 호출하여 프롬프트 성능과 출력을 검증한다.
Lambda Worker의 SQS 처리 흐름을 로컬에서 재현하며,
DynamoDB/SQS는 인메모리로, Slack은 캡처 출력으로 대체한다.

사용법:
    python scripts/local_invoke.py pipeline-start -s feat -m "Redis 캐싱 추가"
    python scripts/local_invoke.py accept --message-ts <ts>
    python scripts/local_invoke.py reject --message-ts <ts> [-a "추가요구사항"]
    python scripts/local_invoke.py drop-restart --message-ts <ts> --drop-ids id1

    python scripts/local_invoke.py state
    python scripts/local_invoke.py clear
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Windows 터미널 인코딩을 UTF-8로 강제 설정
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / "default.env")

# ── 환경변수 정규화 (로컬 실행 시 config 로딩 오류 방지) ─────────────────────

# SQS_QUEUE_URL은 lambda_worker에서 AsyncWebClient 초기화에만 쓰이며
# local_invoke는 캡처 클라이언트로 대체하므로 더미값으로 충분하다
os.environ.setdefault("SQS_QUEUE_URL", "local://dummy-sqs")

# lambda_worker import 시점에 boto3가 region/credentials를 요구하므로 더미값 주입
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-northeast-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")

# TARGET_REPO가 전체 URL 형식이면 owner/repo 형식으로 변환한다
_raw_repo = os.environ.get("TARGET_REPO", "")
if _raw_repo.startswith("https://github.com/"):
    os.environ["TARGET_REPO"] = _raw_repo.removeprefix(
        "https://github.com/"
    )


# ── 상태 파일 ─────────────────────────────────────────────────────────────────

_STATE_FILE = Path(__file__).parent / ".local_state.json"


def _load_state() -> dict:
    """로컬 상태 파일에서 PendingRecord 딕셔너리 로드."""
    if not _STATE_FILE.exists():
        return {}
    try:
        from src.domain.pending import PendingRecord

        raw = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        result = {}
        for ts, data in raw.items():
            try:
                result[ts] = PendingRecord.from_item(data)
            except Exception:
                pass
        return result
    except Exception:
        return {}


def _save_state(store: dict) -> None:
    """PendingRecord 딕셔너리를 로컬 상태 파일에 저장."""
    raw = {}
    for ts, record in store.items():
        try:
            raw[ts] = record.to_item()
        except Exception:
            pass
    _STATE_FILE.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 인메모리 저장소 ───────────────────────────────────────────────────────────


class _MemoryPendingRepo:
    """DynamoPendingRepository 대체 - 인메모리 + 파일 영속화."""

    def __init__(self, store: dict) -> None:
        self._store = store

    async def save(self, record) -> None:
        self._store[record.pk] = record
        _save_state(self._store)

    async def get(self, ts: str):
        return self._store.get(ts)

    async def delete(self, ts: str) -> None:
        self._store.pop(ts, None)
        _save_state(self._store)

    async def save_new_and_delete_old(self, new_record, old_ts: str) -> None:
        self._store.pop(old_ts, None)
        self._store[new_record.pk] = new_record
        _save_state(self._store)


class _MemoryIdempotencyRepo:
    """DynamoIdempotencyRepository 대체 - 인메모리."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    async def try_acquire(self, key: str) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    async def mark_done(self, key: str) -> None:
        pass


# ── Slack 캡처 클라이언트 ─────────────────────────────────────────────────────

_SEP = "─" * 64


def _header(title: str) -> None:
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")


def _section(title: str) -> None:
    print(f"\n{_SEP}")
    print(f"  {title}")
    print(_SEP)


def _print_blocks(blocks: list) -> None:
    """Slack Block Kit 블록에서 텍스트를 추출해 출력한다."""
    for block in blocks:
        btype = block.get("type", "")
        if btype == "section":
            text_obj = block.get("text", {})
            print(f"    {text_obj.get('text', '')}")
        elif btype == "header":
            text_obj = block.get("text", {})
            print(f"  ## {text_obj.get('text', '')}")
        elif btype == "divider":
            print(f"  {'─' * 40}")
        elif btype == "actions":
            elements = block.get("elements", [])
            labels = [e.get("text", {}).get("text", "?") for e in elements]
            print(f"  [버튼] {' | '.join(labels)}")


class _CapturingSlackClient:
    """Slack API 호출을 캡처하여 로컬 출력으로 전환하는 클라이언트."""

    def __init__(self) -> None:
        self._ts_counter = 0

    def _next_ts(self) -> str:
        self._ts_counter += 1
        return f"{int(time.time())}.{self._ts_counter:06d}"

    async def chat_postMessage(self, **kwargs) -> dict:
        ts = self._next_ts()
        _section(f"Slack: chat_postMessage  →  ts={ts}")
        if text := kwargs.get("text"):
            print(f"  text: {text}")
        if blocks := kwargs.get("blocks"):
            _print_blocks(blocks)
        return {
            "ts": ts,
            "ok": True,
            "channel": kwargs.get("channel", "C_LOCAL"),
        }

    async def chat_update(self, **kwargs) -> dict:
        ts = kwargs.get("ts", self._next_ts())
        _section(f"Slack: chat_update  →  ts={ts}")
        if text := kwargs.get("text"):
            print(f"  text: {text}")
        if blocks := kwargs.get("blocks"):
            _print_blocks(blocks)
        return {"ts": ts, "ok": True}

    async def views_open(self, **kwargs) -> dict:
        _section("Slack: views_open")
        return {"ok": True}

    async def auth_test(self) -> dict:
        return {
            "ok": True,
            "user_id": "U_LOCAL",
            "team_id": "T_LOCAL",
            "bot_id": "B_LOCAL",
        }


# ── 에이전트 출력 저장 ────────────────────────────────────────────────────────

_OUTPUTS_DIR = Path(__file__).parent / "outputs"


def _setup_output_dir(event_type: str) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = _OUTPUTS_DIR / f"{ts}_{event_type}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _make_agent_wrapper(out_dir: Path):
    """OpenAIAgent.run을 래핑하여 입출력을 파일로 저장한다."""
    from src.agent.openai import OpenAIAgent

    original_run = OpenAIAgent.run
    counter = {"n": 0}

    async def wrapper(self, message: str):
        counter["n"] += 1
        n = counter["n"]

        result = await original_run(self, message)

        prefix = f"{n:02d}_{self.name}"
        (out_dir / f"{prefix}_input.txt").write_text(
            message, encoding="utf-8"
        )

        output_data: dict = {
            "output": result.output,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        }
        if result.typed_output is not None:
            try:
                output_data["typed_output"] = result.typed_output.model_dump()
            except Exception:
                output_data["typed_output"] = str(result.typed_output)

        (out_dir / f"{prefix}_output.json").write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        _section(
            f"Agent: {self.name}"
            f"  ({result.usage.input_tokens}in"
            f" / {result.usage.output_tokens}out)"
        )
        print(f"  saved -> {out_dir.name}/{prefix}_output.json")

        return result

    return wrapper


# ── invoke 실행 ───────────────────────────────────────────────────────────────


_MODAL_INPUT_CLS = {
    "feat": "src.controller.modal_templates.feat_modal_input.FeatModalInput",
    "refactor": (
        "src.controller.modal_templates"
        ".refactor_modal_input.RefactorModalInput"
    ),
    "fix": "src.controller.modal_templates.fix_modal_input.FixModalInput",
}


def _resolve_user_message(body: dict) -> dict:
    """modal_input 필드가 있으면 to_prompt()로 변환하여 user_message에 주입한다."""
    if "modal_input" not in body:
        return body
    subcommand = body.get("subcommand", "")
    cls_path = _MODAL_INPUT_CLS.get(subcommand)
    if not cls_path:
        return body
    module_path, cls_name = cls_path.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    modal_cls = getattr(mod, cls_name)
    modal = modal_cls(**body["modal_input"])
    body = {k: v for k, v in body.items() if k != "modal_input"}
    body["user_message"] = modal.to_prompt()
    return body


async def _invoke(body: dict) -> None:
    """_process()를 인메모리 저장소 + 캡처 Slack 클라이언트로 실행."""
    body = _resolve_user_message(body)
    store = _load_state()
    pending_repo = _MemoryPendingRepo(store)
    idempotency_repo = _MemoryIdempotencyRepo()
    slack_client = _CapturingSlackClient()

    out_dir = _setup_output_dir(body.get("type", "unknown"))
    print(f"  outputs -> {out_dir}")

    from src.agent.openai import OpenAIAgent
    import src.lambda_worker as worker

    with (
        patch.object(OpenAIAgent, "run", _make_agent_wrapper(out_dir)),
        patch.object(worker, "_pending_repo", pending_repo),
        patch.object(worker, "_idempotency_repo", idempotency_repo),
        patch("src.lambda_worker.AsyncWebClient", return_value=slack_client),
    ):
        start = time.perf_counter()
        await worker._process(json.dumps(body, ensure_ascii=False))
        elapsed = time.perf_counter() - start

    _section(f"완료  ({elapsed:.1f}s)")

    # pipeline_start 후 저장된 message_ts 안내
    if body.get("type") == "pipeline_start" and store:
        latest_ts = max(store.keys())
        print(f"\n  📌 message_ts: {latest_ts}")
        print("  다음 단계:")
        cmd = "python scripts/local_invoke.py"
        print(f"    {cmd} accept --message-ts {latest_ts}")
        print(f"    {cmd} reject --message-ts {latest_ts}")


# ── 서브커맨드 핸들러 ─────────────────────────────────────────────────────────


async def cmd_pipeline_start(args: argparse.Namespace) -> None:
    _header(f"pipeline_start  /  subcommand={args.subcommand}")
    print(f"  message: {args.message}")
    body = {
        "type": "pipeline_start",
        "subcommand": args.subcommand,
        "user_id": args.user_id,
        "channel_id": args.channel_id,
        "user_message": args.message,
        "dedup_id": f"local-{int(time.time())}",
    }
    await _invoke(body)


async def cmd_accept(args: argparse.Namespace) -> None:
    _header(f"accept  /  message_ts={args.message_ts}")
    body = {
        "type": "accept",
        "message_ts": args.message_ts,
        "channel_id": args.channel_id,
        "dedup_id": f"local-accept-{int(time.time())}",
    }
    await _invoke(body)


async def cmd_reject(args: argparse.Namespace) -> None:
    _header(f"reject  /  message_ts={args.message_ts}")
    if args.additional:
        print(f"  additional_requirements: {args.additional}")
    body = {
        "type": "reject",
        "message_ts": args.message_ts,
        "user_id": args.user_id,
        "channel_id": args.channel_id,
        "additional_requirements": args.additional,
        "dedup_id": f"local-reject-{int(time.time())}",
    }
    await _invoke(body)


async def cmd_drop_restart(args: argparse.Namespace) -> None:
    _header(f"drop_restart  /  message_ts={args.message_ts}")
    print(f"  dropped_ids: {args.drop_ids}")
    body = {
        "type": "drop_restart",
        "message_ts": args.message_ts,
        "user_id": args.user_id,
        "channel_id": args.channel_id,
        "dropped_ids": args.drop_ids,
        "dedup_id": f"local-drop-{int(time.time())}",
    }
    await _invoke(body)


async def cmd_draft(args: argparse.Namespace) -> None:
    """Slack 드래프트 모달을 터미널에서 인터랙티브하게 시뮬레이션한다."""
    from src.controller.issue_drop import droppable_items

    store = _load_state()
    if not store:
        print("  (empty - pipeline-start를 먼저 실행하세요)")
        return

    # message_ts 결정
    if args.message_ts:
        ts = args.message_ts
    else:
        candidates = sorted(store.keys())
        if len(candidates) == 1:
            ts = candidates[0]
        else:
            print("  저장된 draft:")
            for i, t in enumerate(candidates):
                rec = store[t]
                preview = rec.user_message[:60]
                print(f"    [{i}] {t}  ({rec.subcommand})  {preview}")
            idx = input("  선택 번호: ").strip()
            ts = candidates[int(idx)]

    record = store.get(ts)
    if not record:
        print(f"  message_ts={ts} 를 찾을 수 없습니다.")
        return

    _header(f"draft  /  message_ts={ts}  ({record.subcommand})")

    if not record.typed_output:
        print("  typed_output 없음 (pipeline-start 결과가 없습니다)")
        return

    items = droppable_items(record.typed_output)

    import questionary

    choices = [
        questionary.Choice(
            title=f"[{item.section}] {item.text}",
            value=item.id,
        )
        for item in items
    ]
    selected = questionary.checkbox(
        "드롭할 항목 선택 (Space=토글, Enter=확정):",
        choices=choices,
    ).ask()
    dropped_ids: list[str] = selected or []
    if dropped_ids:
        print(f"  dropped: {dropped_ids}")

    print()
    action = input("  [a]ccept / [r]eject / [d]rop-restart : ").strip().lower()

    if action == "a":
        body = {
            "type": "accept",
            "message_ts": ts,
            "user_id": args.user_id,
            "channel_id": args.channel_id,
            "dedup_id": f"local-accept-{int(time.time())}",
        }
        _header("-> accept")
        await _invoke(body)

    elif action == "r":
        additional = input("  추가 요구사항 (없으면 Enter): ").strip() or None
        body = {
            "type": "reject",
            "message_ts": ts,
            "user_id": args.user_id,
            "channel_id": args.channel_id,
            "additional_requirements": additional,
            "dedup_id": f"local-reject-{int(time.time())}",
        }
        _header("-> reject")
        await _invoke(body)

    elif action == "d":
        if not dropped_ids:
            print("  드롭할 항목을 선택하지 않았습니다.")
            return
        body = {
            "type": "drop_restart",
            "message_ts": ts,
            "user_id": args.user_id,
            "channel_id": args.channel_id,
            "dropped_ids": dropped_ids,
            "dedup_id": f"local-drop-{int(time.time())}",
        }
        _header("-> drop_restart")
        await _invoke(body)

    else:
        print("  취소.")


def cmd_state(_args: argparse.Namespace) -> None:
    """현재 저장된 PendingRecord 목록을 출력한다."""
    _header("Local State")
    store = _load_state()
    if not store:
        print("  (empty - pipeline-start를 먼저 실행하세요)")
        return
    for ts, record in sorted(store.items()):
        print(f"\n  ts:         {ts}")
        print(f"  subcommand: {record.subcommand}")
        print(f"  user:       {record.user_id}  channel: {record.channel_id}")
        preview = record.user_message[:80]
        ellipsis = "..." if len(record.user_message) > 80 else ""
        print(f"  message:    {preview}{ellipsis}")
        if record.typed_output:
            tname = type(record.typed_output).__name__
            print(f"  template ({tname}):")
            print(
                json.dumps(
                    record.typed_output.model_dump(),
                    ensure_ascii=False,
                    indent=4,
                )
            )


def cmd_clear(_args: argparse.Namespace) -> None:
    """로컬 상태 파일을 초기화한다."""
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()
        print("  State cleared.")
    else:
        print("  (already empty)")


# ── CLI ──────────────────────────────────────────────────────────────────────


def _add_actor_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--user-id", default="U_LOCAL", metavar="UID")
    parser.add_argument("--channel-id", default="C_LOCAL", metavar="CID")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Barlow Lambda 로컬 invoke - 실제 Agent 호출 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--input", "-i",
        metavar="FILE",
        help="SQS body JSON 파일 경로 (서브커맨드 없이 직접 invoke)",
    )
    sub = p.add_subparsers(dest="cmd")

    # pipeline-start
    ps = sub.add_parser(
        "pipeline-start",
        help="read_planner + issue_generator 파이프라인 실행",
    )
    ps.add_argument(
        "--subcommand", "-s",
        choices=["feat", "refactor", "fix"],
        required=True,
    )
    ps.add_argument("--message", "-m", required=True, help="사용자 요청 메시지")
    _add_actor_args(ps)

    # accept
    ac = sub.add_parser("accept", help="issue_creator 실행 (GitHub 이슈 생성)")
    ac.add_argument(
        "--message-ts",
        required=True,
        help="pipeline-start 결과 message_ts",
    )
    _add_actor_args(ac)

    # reject
    rj = sub.add_parser("reject", help="re_issue_generator 실행 (이슈 재생성)")
    rj.add_argument("--message-ts", required=True)
    rj.add_argument(
        "--additional", "-a",
        default=None,
        metavar="REQ",
        help="추가 요구사항",
    )
    _add_actor_args(rj)

    # drop-restart
    dr = sub.add_parser(
        "drop-restart",
        help="항목 제거 후 re_issue_generator 실행",
    )
    dr.add_argument("--message-ts", required=True)
    dr.add_argument(
        "--drop-ids",
        nargs="+",
        default=[],
        metavar="ID",
        help="제거할 항목 ID 목록",
    )
    _add_actor_args(dr)

    # draft
    dft = sub.add_parser(
        "draft",
        help="Slack 드래프트 모달 인터랙티브 시뮬레이션 (accept/reject/drop-restart)",
    )
    dft.add_argument(
        "--message-ts", default=None, help="대상 message_ts (생략 시 자동 선택)"
    )
    _add_actor_args(dft)

    # state
    sub.add_parser("state", help="저장된 PendingRecord 조회")

    # clear
    sub.add_parser("clear", help="로컬 상태 초기화")

    return p


_SYNC_CMDS = {"state": cmd_state, "clear": cmd_clear}
_ASYNC_CMDS = {
    "pipeline-start": cmd_pipeline_start,
    "accept": cmd_accept,
    "reject": cmd_reject,
    "drop-restart": cmd_drop_restart,
    "draft": cmd_draft,
}


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"Error: file not found - {args.input}", file=sys.stderr)
            sys.exit(1)
        body = json.loads(path.read_text(encoding="utf-8"))
        _header(f"invoke (JSON)  /  type={body.get('type', '?')}")
        print(f"  file: {path}")
        if "modal_input" in body:
            _section("Modal Input → to_prompt()")
            resolved = _resolve_user_message(dict(body))
            print(resolved.get("user_message", ""))
        import anyio
        anyio.run(_invoke, body)
        return

    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    if args.cmd in _SYNC_CMDS:
        _SYNC_CMDS[args.cmd](args)
    else:
        import anyio
        anyio.run(_ASYNC_CMDS[args.cmd], args)


if __name__ == "__main__":
    main()
