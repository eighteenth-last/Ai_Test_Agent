from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def ensure_browser_use_runtime_env() -> str:
    configured = str(os.getenv("BROWSER_USE_CONFIG_DIR", "")).strip()
    if configured:
        configured_path = Path(configured).expanduser()
        if _is_writable_dir(configured_path):
            return str(configured_path)
        logger.warning("[browser_use_runtime] configured BROWSER_USE_CONFIG_DIR is not writable: %s", configured_path)

    project_root = Path(__file__).resolve().parents[2]
    workspace_root = project_root.parent
    local_source_candidates = [
        workspace_root / "browser-use-0.11.1" / "browser-use-0.11.1",
        project_root / "browser-use-0.11.1" / "browser-use-0.11.1",
    ]
    for candidate in local_source_candidates:
        if candidate.exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            break

    runtime_root = project_root / ".runtime"
    config_dir = runtime_root / "browseruse"
    profiles_dir = config_dir / "profiles"
    extensions_dir = config_dir / "extensions"
    temp_root = runtime_root / "tmp"
    downloads_root = runtime_root / "downloads"

    for folder in (runtime_root, config_dir, profiles_dir, extensions_dir, temp_root, downloads_root):
        folder.mkdir(parents=True, exist_ok=True)

    os.environ["BROWSER_USE_CONFIG_DIR"] = str(config_dir)
    os.environ.setdefault("XDG_CONFIG_HOME", str(runtime_root))
    os.environ.setdefault("TMP", str(temp_root))
    os.environ.setdefault("TEMP", str(temp_root))
    os.environ.setdefault("TMPDIR", str(temp_root))
    os.environ.setdefault("BROWSER_USE_RUNTIME_DIR", str(runtime_root))
    os.environ.setdefault("BROWSER_USE_DOWNLOADS_DIR", str(downloads_root))
    os.environ.setdefault("BROWSER_USE_ENABLE_DEFAULT_EXTENSIONS", "false")
    return str(config_dir)
