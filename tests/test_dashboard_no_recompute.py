"""Guard for the rule 'the dashboard must never recalculate MAE/RMSE in JavaScript'.

Set DASHBOARD_SRC to Module 3's source directory (e.g. in CI) to scan it; skipped otherwise.
"""
import os
import re
from pathlib import Path

import pytest

FORBIDDEN = [r"Math\.sqrt", r"Math\.abs\([^)]*(forecast|actual|error)", r"\bmae\s*=", r"\brmse\s*=", r"\bmbe\s*=",
             r"reduce\([^)]*(forecast|actual)"]


def test_dashboard_source_contains_no_metric_calculations():
    src = os.environ.get("DASHBOARD_SRC")
    if not src or not Path(src).is_dir():
        return  # nothing to scan in this environment
    hits = []
    for f in Path(src).rglob("*"):
        if f.suffix in {".js", ".jsx", ".ts", ".tsx"} and "node_modules" not in f.parts:
            text = f.read_text(errors="ignore")
            hits += [f"{f}: {p}" for p in FORBIDDEN if re.search(p, text, re.IGNORECASE)]
    assert not hits, "Metric logic found in dashboard code:\n" + "\n".join(hits)
