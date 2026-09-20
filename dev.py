#!/usr/bin/env python3
"""Start the existing local development services (macOS/Linux)."""

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="一键启动后端、用户端和管理后台；Ctrl+C 统一停止。")
    parser.add_argument("--skip-infra", action="store_true", help="不启动 Docker 基础设施（已自行启动时使用）")
    args = parser.parse_args()
    processes = []

    def stop_requested(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_requested)

    def start(name, command, cwd):
        print(f"[启动] {name}", flush=True)
        # Each service owns a process group so reload workers also stop on exit.
        process = subprocess.Popen(command, cwd=cwd, start_new_session=True)
        processes.append((name, process))
        return process

    try:
        for executable in ["uv", "npm"] + ([] if args.skip_infra else ["docker"]):
            if shutil.which(executable) is None:
                raise RuntimeError(f"找不到 {executable}，请先按 README 安装。")
        for relative in ["backend/.env", "backend/.venv", "frontend/node_modules", "admin-frontend/node_modules"]:
            if not (ROOT / relative).exists():
                raise RuntimeError(f"缺少 {relative}，请先完成 README 中的首次配置。")
        for port in (8000, 5178, 5179):
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError as exc:
                    raise RuntimeError(f"端口 {port} 不可用，请先停止占用它的服务。") from exc

        if not args.skip_infra:
            infrastructure = start("数据库和邮件服务", ["docker", "compose", "up", "-d", "--wait", "postgres", "mailpit"], ROOT)
            if infrastructure.wait() != 0:
                raise RuntimeError("基础设施启动失败，请检查 Docker 是否运行。")
            processes.clear()

        start("后端", ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"], ROOT / "backend")
        start("用户端", ["npm", "run", "dev"], ROOT / "frontend")
        start("管理后台", ["npm", "run", "dev"], ROOT / "admin-frontend")
        print("\n访问地址（就绪状态见各服务日志）：\n"
              "  用户端：http://127.0.0.1:5178\n"
              "  管理后台：http://127.0.0.1:5179\n"
              "  后端：http://127.0.0.1:8000/api/v1/health\n"
              "  邮件：http://127.0.0.1:8025\n"
              "按 Ctrl+C 停止三个应用；Docker 基础设施继续运行。\n", flush=True)
        while True:
            for name, process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} 已退出（退出码 {process.returncode}），正在停止其他应用。")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在停止应用……", flush=True)
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        for _, process in processes:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 8
        for _, process in processes:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for _, process in processes:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


if __name__ == "__main__":
    sys.exit(main())
