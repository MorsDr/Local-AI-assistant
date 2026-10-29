
import json
import time
import urllib.error
import urllib.request
import uuid


COMFYUI_URL = "http://127.0.0.1:8188"


class ComfyUIError(RuntimeError):
    """Raised when ComfyUI generation fails."""


def _post_json(endpoint: str, payload: dict) -> dict:
    url = f"{COMFYUI_URL}{endpoint}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ComfyUIError(
            f"ComfyUI request failed at {endpoint}: {error}"
        ) from error


def build_workflow(config: dict) -> dict:
    """Build a basic SDXL text-to-image workflow."""

    required = (
        "checkpoint",
        "positive_prompt",
        "negative_prompt",
        "resolution",
    )
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing config fields: {', '.join(missing)}")

    resolution = config["resolution"]
    width = resolution["width"]
    height = resolution["height"]

    if not all(isinstance(v, int) and v > 0 for v in (width, height)):
        raise ValueError("Resolution width and height must be positive integers.")

    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": config["checkpoint"],
            },
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": config["positive_prompt"],
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": config["negative_prompt"],
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(time.time_ns() % (2**32)),
                "steps": 25,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
            },
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ai_helper",
                "images": ["6", 0],
            },
        },
    }


def generate_image(config: dict, timeout: int = 600) -> dict:
    """Submit a workflow, wait for completion, and return image metadata."""

    workflow = build_workflow(config)
    client_id = str(uuid.uuid4())

    result = _post_json(
        "/prompt",
        {
            "prompt": workflow,
            "client_id": client_id,
        },
    )

    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise ComfyUIError(f"ComfyUI did not return prompt_id: {result}")

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"{COMFYUI_URL}/history/{prompt_id}",
                timeout=15,
            ) as response:
                history = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ComfyUIError(f"Could not read generation history: {error}") from error

        job = history.get(prompt_id)
        if job:
            status = job.get("status", {})
            if status.get("status_str") == "error" or status.get("completed") is False:
                if any(
                    item.get("node") == "execution_error"
                    for item in status.get("messages", [])
                    if isinstance(item, dict)
                ):
                    raise ComfyUIError(f"Generation failed: {status}")

            outputs = job.get("outputs", {})
            images = [
                {
                    **image,
                    "url": (
                        f"{COMFYUI_URL}/view?"
                        f"filename={image['filename']}"
                        f"&subfolder={image.get('subfolder', '')}"
                        f"&type={image.get('type', 'output')}"
                    ),
                }
                for node in outputs.values()
                for image in node.get("images", [])
            ]

            if images:
                return {
                    "prompt_id": prompt_id,
                    "images": images,
                }

        time.sleep(1)

    raise ComfyUIError(
        f"Generation timed out after {timeout} seconds. "
        f"ComfyUI prompt_id: {prompt_id}"
    )
