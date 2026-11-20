import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


COMFY_DIR = Path("/mnt/data/@data/ai_helper/generator_model_comfy/ComfyUI")
COMFY_URL = "http://127.0.0.1:8188"
LOG_FILE = Path("comfyui.log")

_process: subprocess.Popen | None = None  # set only if WE started it
_last_used = time.monotonic()


class ComfyManagerError(RuntimeError):
    """Raised when ComfyUI cannot be started or stopped."""


def is_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=2):
            return True
    except OSError:
        return False


def start(extra_args: list[str] | None = None) -> None:
    global _process
    if is_ready():
        return  # already running, possibly started by the user

    command = ["bash", "-c", 'echo 1000 > /proc/self/oom_score_adj; exec "$@"', "comfy" "uv", "run", "python", "main.py", *(extra_args or [])]
    with LOG_FILE.open("ab") as log:
        # New session: lets us stop uv together with its python child.
        _process = subprocess.Popen(
            command,
            cwd=COMFY_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def wait_ready(timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _process is not None and _process.poll() is not None:
            raise ComfyManagerError(
                f"ComfyUI exited with code {_process.returncode}. "
                f"See {LOG_FILE}."
            )
        if is_ready():
            return
        time.sleep(1)
    raise ComfyManagerError(f"ComfyUI was not ready after {timeout} s.")


def ensure_running(
    extra_args: list[str] | None = None, timeout: int = 180
) -> None:
    start(extra_args)
    wait_ready(timeout)


def touch() -> None:
    """Mark ComfyUI as used just now (resets the idle timer)."""
    global _last_used
    _last_used = time.monotonic()


def stop(timeout: int = 30) -> bool:
    """Stop ComfyUI, but only if this module started it."""
    global _process
    if _process is None:
        return False

    try:
        group = os.getpgid(_process.pid)
        os.killpg(group, signal.SIGTERM)
        try:
            _process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(group, signal.SIGKILL)
            _process.wait()
    except ProcessLookupError:
        pass  # already gone

    _process = None
    return True


def stop_if_idle(idle_seconds: int = 300) -> bool:
    if _process is not None and time.monotonic() - _last_used >= idle_seconds:
        return stop()
    return False

def is_owned() -> bool:
    return _process is not None

def kill() -> bool:
    """HARD-STOP ComfyUI (SIGKILL)"""
    global _process
    if _process is None:
        return False
    try:
        os.killpg(os.getpgid(_process.pid), signal.SIGKILL)
        _process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass
    _process=None
    return True
