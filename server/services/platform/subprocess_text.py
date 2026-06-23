from __future__ import annotations

import subprocess
from typing import Any, Sequence

UTF8_TEXT_KWARGS: dict[str, Any] = {
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
}


def run_text(
    args: Sequence[str],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    options: dict[str, Any] = {
        "capture_output": True,
        "check": False,
        **UTF8_TEXT_KWARGS,
    }
    options.update(kwargs)
    return subprocess.run(args, **options)
