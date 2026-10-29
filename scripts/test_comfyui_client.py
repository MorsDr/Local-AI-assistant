
from comfyui_client import generate_image

config = {
    "checkpoint": "samaritan3dCartoon_v40SDXL.safetensors",
    "positive_prompt": (
        "A cute small red panda inventor wearing goggles, "
        "holding a silver wrench, high-quality 3D cartoon."
    ),
    "negative_prompt": (
        "blurry, low resolution, extra limbs, distorted anatomy, watermark"
    ),
    "resolution": {
        "width": 1024,
        "height": 1024,
    },
}

try:
    result = generate_image(config)
    print(result)
except Exception as error:
    print(f"Generation failed: {error}")
