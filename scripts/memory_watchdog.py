import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from get_system_info import get_memory_status

import comfy_manager
from comfyui_client import ComfyUIError

GB = 1024**3
SOFT_FREE_VRAM = 1.5 * GB
HARD_FREE_VRAM = 0.8 * GB
HARD_FREE_RAM = 1.5 * GB
POLL_SECONDS = 0.25
GRACE_SECONDS = 3.0

last_abort: str | None = None

def _interrupt() -> None:
    request = urllib.request.Request(
        f"{comfy_manager.COMFY_URL}/interrupt", data=b"", method="POST"
    )
    try:
        urllib.request.urlopen(request, timeout=3).close()
    except OSError:
        pass


def _watch(stop_event: threading.Event) -> None:
    global last_abort
    soft_since: float | None = None

    while not stop_event.wait(POLL_SECONDS):
        free_vram = None
        if files:
            free_vram = int(files[1].read_text()) - int(files[0].read_text())
        free_ram = _free_ram()

        reason = None
        if free_vram is not None and free_vram < HARD_FREE_VRAM:
            reason = f"free VRAM {free_vram / GB:.1f} GB"
        elif free_ram < HARD_FREE_RAM:
            reason = f"free RAM {free_ram / GB:.1f} GB"
        elif free_vram is not None and free_vram < SOFT_FREE_VRAM:
            now = time.monotonic()
            if soft_since is None:
                soft_since = now
                _interrupt()
            elif now - soft_since >= GRACE_SECONDS:
                reason = f"free VRAM stayed at {free_vram / GB:.1f} GB"
        else:
            soft_since = None

        if reason and comfy_manager.is_owned():
            last_abort = reason
            comfy_manager.kill()
            return


@contextmanager
def guard():
    """Watch memory while a generation runs; abort before the system fails."""
    global last_abort
    last_abort = None
    stop_event = threading.Event()
    thread = threading.Thread(target=_watch, args=(stop_event,), daemon=True)
    thread.start()
    try:
        yield
    except ComfyUIError as error:
        if last_abort:
            raise ComfyUIError(
                f"Generation aborted, low memory: {last_abort}"
            ) from error
        raise
    finally:
        stop_event.set()
        thread.join()
