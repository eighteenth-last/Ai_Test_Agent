from __future__ import annotations

from typing import Optional


def next_engine(current_engine: str) -> Optional[str]:
    if current_engine == "dom":
        return "vision"
    if current_engine == "vision":
        return "dom"
    return None


def should_retry(failure_code: str, attempt: int) -> bool:
    if attempt >= 1:
        return False
    return failure_code in {
        "target_not_found",
        "locator_unstable",
        "click_no_effect",
        "vision_not_supported",
    }
