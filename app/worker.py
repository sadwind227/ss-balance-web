"""独立计算进程：每行写出一个 JSON 事件，便于主服务中断长搜索。"""

from __future__ import annotations

import json
import sys

from engine.solve import generate


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def main(args: list[str] | None = None) -> None:
    number, mode, multiple, target = args if args is not None else sys.argv[1:]
    try:
        reason = generate(number, mode, multiple == "1", int(target),
                          lambda record: emit({"kind": "solution", "record": record}))
        emit({"kind": "done", "reason": reason})
    except Exception as exc:
        emit({"kind": "error", "message": f"计算失败：{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
