"""仅在本机开放的静态网页与计算任务接口。"""

from __future__ import annotations

import json
import queue
import secrets
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from engine.data import ROOT, published
from engine.solve import known_existence, validate_number

WEB = ROOT / "web"
FILES = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
         "/style.css": ("style.css", "text/css")}


class Job:
    def __init__(self, number: str, mode: str, allow_multiple: bool, target: int,
                 budget: int, existence: str, basis: str) -> None:
        self.id = uuid.uuid4().hex
        self.number = number
        self.mode = mode
        self.allow_multiple = allow_multiple
        self.target = target
        self.budget = budget
        self.existence = existence
        self.basis = basis
        self.state = "complete" if existence == "no" else "running"
        self.solutions: list[dict] = []
        self.message = ""
        self.started = time.monotonic()
        self.process: subprocess.Popen | None = None
        self.outbox: queue.Queue = queue.Queue()
        if existence != "no":
            # Windows 的 multiprocessing.Queue 需要命名管道；文本流便于隔离、取消和调试。
            args = ([sys.executable, "--worker"] if getattr(sys, "frozen", False)
                    else [sys.executable, "-u", "-m", "app.worker"])
            self.process = subprocess.Popen(
                [*args, number, mode, "1" if allow_multiple else "0", str(target)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self) -> None:
        assert self.process and self.process.stdout
        with self.process.stdout:
            for line in self.process.stdout:
                try:
                    self.outbox.put(json.loads(line))
                except json.JSONDecodeError:
                    self.outbox.put({"kind": "error", "message": "计算进程返回了错误格式的数据。"})

    def update(self) -> None:
        if self.state != "running" or self.process is None:
            return
        while True:
            try:
                event = self.outbox.get_nowait()
            except queue.Empty:
                break
            if event["kind"] == "solution":
                if event["record"]["expression"] not in {s["expression"] for s in self.solutions}:
                    self.solutions.append(event["record"])
                    self.existence = "yes"
                    self.basis = "已验证方案"
            elif event["kind"] == "done":
                self.state = "complete" if event["reason"] != "incomplete" else "incomplete"
                if self.existence == "unknown" and event["reason"] == "complete" and not self.solutions:
                    self.existence, self.basis = "no", "已完成当前规则的精确枚举"
                self.process.wait(timeout=1)
                return
            elif event["kind"] == "error":
                self.state = "error"
                self.message = event["message"]
                return
        if time.monotonic() - self.started > self.budget:
            self.process.terminate()
            self.process.wait(timeout=1)
            self.state = "limit"
            self.message = "已达到本次搜索时限；可以延长时间再试。"
        elif self.process.poll() is not None and self.outbox.empty():
            # 进程异常退出且无最终消息，数学判定保持原依据。
            self.state = "error"
            self.message = "计算进程提前结束。"

    def cancel(self) -> None:
        if self.state == "running" and self.process:
            self.process.terminate()
            self.process.wait(timeout=1)
            self.state = "cancelled"
            self.message = "搜索已取消，已验证的方案仍可使用。"

    def as_dict(self) -> dict:
        self.update()
        return {
            "id": self.id, "number": self.number, "mode": self.mode,
            "allow_multiple": self.allow_multiple, "target": self.target,
            "existence": self.existence, "basis": self.basis,
            "state": self.state, "solutions": self.solutions,
            "message": self.message, "elapsed_seconds": round(time.monotonic() - self.started, 1),
        }


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.token = secrets.token_urlsafe(32)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.RLock()

    def server_close(self) -> None:
        with self.lock:
            for job in self.jobs.values():
                job.cancel()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server: AppServer

    def log_message(self, format: str, *args) -> None:
        # 不把用户输入的数字串写入控制台日志。
        pass

    def _send(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")

    def _trusted(self, api: bool = False) -> bool:
        host = self.headers.get("Host", "")
        expected = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        if host != expected or (origin and origin != f"http://{expected}"):
            return False
        return not api or self.headers.get("X-Local-Token") == self.server.token

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            if not self._trusted(api=True):
                self._json(HTTPStatus.FORBIDDEN, {"error": "请求未经授权"})
                return
            if path == "/api/info":
                self._json(HTTPStatus.OK, {"max_digits": 256, "default_target": 5,
                                            "upstream_generated_utc": published().manifest["generated_utc"]})
                return
            if path.startswith("/api/jobs/"):
                job_id = path.removeprefix("/api/jobs/")
                with self.server.lock:
                    job = self.server.jobs.get(job_id)
                    if job:
                        self._json(HTTPStatus.OK, job.as_dict())
                        return
            self._json(HTTPStatus.NOT_FOUND, {"error": "任务不存在"})
            return
        if not self._trusted() or path not in FILES:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
            return
        filename, content_type = FILES[path]
        data = (WEB / filename).read_bytes()
        if filename == "index.html":
            data = data.replace(b"__LOCAL_TOKEN__", self.server.token.encode("ascii"))
        self._send(HTTPStatus.OK, data, content_type)

    def do_POST(self) -> None:
        if not self._trusted(api=True):
            self._json(HTTPStatus.FORBIDDEN, {"error": "请求未经授权"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 4096 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self._json(HTTPStatus.BAD_REQUEST, {"error": "请求格式错误"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "JSON 格式错误"})
            return
        if not isinstance(payload, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "请求格式错误"})
            return
        path = urlsplit(self.path).path
        if path == "/api/jobs":
            try:
                number = validate_number(payload.get("number"))
                mode = payload.get("mode")
                if mode not in {"strict", "segment"}:
                    raise ValueError("请选择有效规则")
                allow_multiple = payload.get("allow_multiple")
                if type(allow_multiple) is not bool:
                    raise ValueError("等号设置无效")
                target = payload.get("target")
                if type(target) is not int or not 1 <= target <= 20:
                    raise ValueError("方案数量应为 1–20")
                budget = payload.get("budget", 30)
                if type(budget) is not int or budget not in {30, 90}:
                    raise ValueError("搜索时限设置无效")
                existence, basis = known_existence(number, mode, allow_multiple)
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            with self.server.lock:
                for old in self.server.jobs.values():
                    if old.state == "running":
                        old.cancel()
                try:
                    job = Job(number, mode, allow_multiple, target, budget, existence, basis)
                except OSError:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE,
                               {"error": "无法启动计算进程，请检查 Python 环境。"})
                    return
                self.server.jobs[job.id] = job
                self._json(HTTPStatus.CREATED, job.as_dict())
            return
        if path.startswith("/api/jobs/") and path.endswith("/cancel"):
            job_id = path[len("/api/jobs/"):-len("/cancel")]
            with self.server.lock:
                job = self.server.jobs.get(job_id)
                if job:
                    job.cancel()
                    self._json(HTTPStatus.OK, job.as_dict())
                    return
        self._json(HTTPStatus.NOT_FOUND, {"error": "任务不存在"})


def main(open_browser: bool = True) -> None:
    published()  # 启动前验证数据，以免网页打开后才出现校验失败。
    server = AppServer()
    address = f"http://127.0.0.1:{server.server_port}/"
    print(f"整数平衡化工具已启动：{address}", flush=True)
    print("按 Ctrl+C 关闭。", flush=True)
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
