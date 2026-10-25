
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PROFILE_FILE = BASE_DIR / "configs" / "comfy_profiles.json"


class ProfileError(ValueError):
    """Raised when a request cannot be resolved to a profile."""


def load_profiles() -> dict:
    if not PROFILE_FILE.is_file():
        raise ProfileError(
            f"Profile catalog not found: {PROFILE_FILE}"
        )

    try:
        with PROFILE_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ProfileError(
            f"Invalid profile JSON: {error}"
        ) from error


def resolve_profile(request: dict) -> dict:
    """Resolve a parsed request into model and LoRA settings."""
    catalog = load_profiles()

    try:
        settings = request["settings"]
        content = request["content"]

        image_type = settings["type"]
        style = settings["style"]
        detail = settings["detail"]
        resolution = settings["resolution"]

        nsfw = content["nsfw"]
        nsfw_type = content["nsfw_type"]
    except (KeyError, TypeError) as error:
        raise ProfileError(
            f"Request is missing a required field: {error}"
        ) from error

    if image_type not in catalog["image_types"]:
        raise ProfileError(
            f"No model configuration for type '{image_type}'."
        )

    type_profile = catalog["image_types"][image_type]
    styles = type_profile.get("styles", {})

    if style not in styles:
        raise ProfileError(
            f"No style profile '{style}' for '{image_type}'."
        )

    checkpoint = type_profile.get("checkpoint")

    if not checkpoint or checkpoint.startswith("REPLACE_WITH_"):
        raise ProfileError(
            f"Checkpoint for '{image_type}' has not been configured."
        )

    style_loras = styles[style].get("loras", [])

    selected_loras = list(style_loras)

    if nsfw:
        if not nsfw_type:
            raise ProfileError(
                "NSFW is enabled but no NSFW profile was selected."
            )

        nsfw_profiles = catalog.get("nsfw_profiles", {})

        if nsfw_type not in nsfw_profiles:
            raise ProfileError(
                f"Unknown NSFW profile '{nsfw_type}'."
            )

        nsfw_loras = nsfw_profiles[nsfw_type].get("loras", [])

        selected_loras.extend(nsfw_loras)
    elif nsfw_type is not None:
        raise ProfileError(
            "NSFW profile supplied while NSFW is disabled."
        )

    return {
        "checkpoint": checkpoint,
        "loras": selected_loras,
        "detail": detail,
        "resolution": resolution,
        "content": {
            "nsfw": nsfw,
            "nsfw_type": nsfw_type
        }
    }


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Resolve a parsed image request."
    )
    parser.add_argument(
        "request_json",
        help="Path to the JSON file produced by request_parser.py."
    )
    args = parser.parse_args()

    try:
        with open(args.request_json, "r", encoding="utf-8") as file:
            request = json.load(file)

        result = resolve_profile(request)

        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()

    except (OSError, json.JSONDecodeError, ProfileError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
