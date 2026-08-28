from __future__ import annotations

import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PLUGIN_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from agentic_backlog_kit.benchmark import main  # noqa: E402


raise SystemExit(main())
