#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render docker-compose release asset from template."
    )
    parser.add_argument(
        "--template",
        required=True,
        help="Path to docker-compose release template.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Rendered docker-compose output path.",
    )
    parser.add_argument(
        "--image-repo",
        required=True,
        help="Image repository, e.g. leike0813/skill-runner.",
    )
    parser.add_argument(
        "--image-tag",
        required=True,
        help="Image tag, must be non-empty.",
    )
    return parser


def render_release_compose(
    template_path: Path,
    output_path: Path,
    image_repo: str,
    image_tag: str,
) -> None:
    template_text = template_path.read_text(encoding="utf-8")
    rendered = template_text.replace("__IMAGE_REPO__", image_repo).replace(
        "__IMAGE_TAG__", image_tag
    )
    if "__IMAGE_REPO__" in rendered or "__IMAGE_TAG__" in rendered:
        raise RuntimeError("Template placeholders were not fully replaced")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    args = _build_parser().parse_args()
    template_path = Path(args.template)
    output_path = Path(args.output)
    image_repo = args.image_repo.strip()
    image_tag = args.image_tag.strip()
    if not image_repo:
        raise ValueError("--image-repo must be non-empty")
    if not image_tag:
        raise ValueError("--image-tag must be non-empty")
    render_release_compose(
        template_path=template_path,
        output_path=output_path,
        image_repo=image_repo,
        image_tag=image_tag,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
