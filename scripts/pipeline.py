
import argparse
import json
import sys

from request_parser import build_request
from profile_resolver import resolve_profile
from prompt_generator import generate_prompts, PromptGenerationError


def run_pipeline(args: argparse.Namespace) -> dict:
    """Parse request, resolve profile, and generate prompts."""

    # 1. Parse and validate the user request.
    request = build_request(args)

    # 2. Resolve checkpoint, LoRAs, resolution, and other settings.
    profile = resolve_profile(request)

    # 3. Generate positive and negative prompts from the description.
    prompts = generate_prompts(request["description"])

    # 4. Combine everything into one result.
    return {
        **profile,
        **prompts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a complete image-generation request."
    )

    parser.add_argument("description", help="Description of the desired image")
    parser.add_argument(
        "--type",
        choices=["2d", "3d", "photorealism"],
        required=True,
    )
    parser.add_argument("--style", required=True)
    parser.add_argument(
        "--detail",
        choices=["simple", "balanced", "high"],
        default="balanced",
    )
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--nsfw", action="store_true")
    parser.add_argument(
        "--nsfw-type",
        choices=["adult_profile_a", "adult_profile_b", "adult_profile_c"],
        default=None,
    )

    args = parser.parse_args()

    try:
        result = run_pipeline(args)
    except (
        ValueError,
        argparse.ArgumentError,
        argparse.ArgumentTypeError,
        PromptGenerationError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        # Includes profile-resolution errors derived from RuntimeError.
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
