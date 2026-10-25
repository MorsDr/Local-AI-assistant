
import argparse
import json
import re
import sys


IMAGE_TYPES = {"2d", "3d", "photorealism"}

STYLE_PROFILES = {
    "2d": {
        "anime",
        "western_cartoon",
        "painterly",
        "comic",
        "storybook",
    },
    "3d": {
        "cartoon_3d",
        "anime_3d",
        "realistic_cgi",
        "low_poly",
        "clay",
    },
    "photorealism": {
        "default",
    },
}

DETAIL_LEVELS = {"simple", "balanced", "high"}

# Temporary IDs for manually selected specialized content profiles.
# Later, each profile can reference actual LoRA files and weights.
NSFW_PROFILES = {
    "adult_profile_a",
    "adult_profile_b",
    "adult_profile_c",
}


def parse_resolution(value: str) -> dict:
    """Convert WIDTHxHEIGHT into a validated resolution."""
    match = re.fullmatch(r"(\d{3,4})[xX](\d{3,4})", value.strip())

    if not match:
        raise argparse.ArgumentTypeError(
            "Resolution must look like 1024x1024."
        )

    width, height = map(int, match.groups())

    if not (256 <= width <= 2048):
        raise argparse.ArgumentTypeError(
            "Width must be between 256 and 2048."
        )

    if not (256 <= height <= 2048):
        raise argparse.ArgumentTypeError(
            "Height must be between 256 and 2048."
        )

    return {
        "width": width,
        "height": height,
    }


def build_request(args: argparse.Namespace) -> dict:
    """Validate settings and return a normalized request."""
    description = args.description.strip()

    if not description:
        raise ValueError("Description must not be empty.")

    image_type = args.type
    style = args.style

    if style not in STYLE_PROFILES[image_type]:
        allowed = ", ".join(sorted(STYLE_PROFILES[image_type]))
        raise ValueError(
            f"Style '{style}' is not valid for type '{image_type}'. "
            f"Available styles: {allowed}"
        )

    # Validate manual NSFW selection.
    if args.nsfw:
        if not args.nsfw_type:
            raise ValueError(
                "--nsfw-type is required when --nsfw is enabled."
            )

        if args.nsfw_type not in NSFW_PROFILES:
            allowed = ", ".join(sorted(NSFW_PROFILES))
            raise ValueError(
                f"Unknown NSFW type '{args.nsfw_type}'. "
                f"Available types: {allowed}"
            )

        nsfw_type = args.nsfw_type
    else:
        if args.nsfw_type is not None:
            raise ValueError(
                "--nsfw-type cannot be used without --nsfw."
            )

        nsfw_type = None

    return {
        "description": description,
        "settings": {
            "type": image_type,
            "style": style,
            "detail": args.detail,
            "resolution": parse_resolution(args.size),
        },
        "content": {
            "nsfw": args.nsfw,
            "nsfw_type": nsfw_type,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse and validate an image generation request."
    )

    parser.add_argument(
        "description",
        help="Description of the image to generate.",
    )

    parser.add_argument(
        "--type",
        choices=sorted(IMAGE_TYPES),
        required=True,
        help="Image type: 2d, 3d, or photorealism.",
    )

    parser.add_argument(
        "--style",
        required=True,
        help="Style profile for the selected image type.",
    )

    parser.add_argument(
        "--detail",
        choices=sorted(DETAIL_LEVELS),
        default="balanced",
        help="Detail level (default: balanced).",
    )

    parser.add_argument(
        "--size",
        default="1024x1024",
        help="Image resolution (default: 1024x1024).",
    )

    parser.add_argument(
        "--nsfw",
        action="store_true",
        help="Enable the manually selected 18+ content profile.",
    )

    parser.add_argument(
        "--nsfw-type",
        choices=sorted(NSFW_PROFILES),
        default=None,
        help="Specialized 18+ profile ID; requires --nsfw.",
    )

    args = parser.parse_args()

    try:
        request_data = build_request(args)
    except (ValueError, argparse.ArgumentTypeError) as error:
        parser.error(str(error))

    json.dump(
        request_data,
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
