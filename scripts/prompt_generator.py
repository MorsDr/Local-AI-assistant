import json
import urllib.error
import urllib.request


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3.5-4b"

SYSTEM_PROMPT = """
You write concise, detailed prompts for AI image generation.

Return only a valid JSON object with exactly two non-empty string fields:
"positive_prompt" and "negative_prompt".

Rules:
- Preserve the user's subject, requested details, style, mood, and composition.
- Respect all restrictions, especially "only", "without", and specified quantities.
- Do not invent additional people, objects, accessories, or scenery.
- Add relevant visual detail based on the request:
  * Photorealism: natural textures, realistic lighting, shadows, and perspective.
  * 3D: clear volume, material definition, coherent lighting, and contact shadows.
  * Illustration or cartoon: consistent style, clear shapes, suitable colors, and shading.
  * Materials: describe relevant properties such as fur, fabric, wood, metal, glass, or ceramic.
  * High detail: add meaningful surface detail, not unrelated objects.
- Improve composition and color harmony when the user asks for a beautiful or polished image.
- Do not add generic tags such as "8k", "masterpiece", or "best quality" without a reason.
- Write the positive prompt as a clear visual description.
- Write a short, scene-specific negative prompt for plausible defects and unwanted elements.
- Do not contradict the user's request.
- Return no markdown, explanations, or text outside the JSON object.
"""

class PromptGenerationError(RuntimeError):
    """Raised when prompt generation fails."""


def generate_prompts(request: str) -> dict[str, str]:
    """Generate positive and negative image prompts from a user request."""
    if not isinstance(request, str) or not request.strip():
        raise ValueError("Request must be a non-empty string.")

    # payload = {
    #     "model": MODEL_NAME,
    #     "system": SYSTEM_PROMPT,
    #     "prompt": request.strip(),
    #     "stream": False,
    #     "format": "json",
    #     "think": True,
    #     "options": {
    #         "temperature": 0.3
    #     }
    # }
    payload = {
        "model": MODEL_NAME,
        "stream": False,
        "format": "json",
        "think": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.strip()},
        ],
    }
    http_request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(http_request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as error:
        raise PromptGenerationError(
            f"Could not connect to Ollama: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise PromptGenerationError(
            "Ollama returned an invalid JSON response."
        ) from error

    try:
        content = result["message"]["content"]
        prompts = json.loads(content)
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise PromptGenerationError(
            "The model did not return valid prompt JSON."
            f"Raw content: {content!r}"
        ) from error

    required_keys = {"positive_prompt", "negative_prompt"}

    if not isinstance(prompts, dict) or set(prompts) != required_keys:
        raise PromptGenerationError(
            "Expected exactly positive_prompt and negative_prompt."
        )

    if not all(
        isinstance(prompts[key], str) and prompts[key].strip()
        for key in required_keys
    ):
        raise PromptGenerationError(
            "Both prompts must be non-empty strings."
        )

    return prompts
