"""The client and the counts have no Home Assistant import: load them straight from the integration's folder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "backlog_aihub"))
