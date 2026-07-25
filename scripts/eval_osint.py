#!/usr/bin/env python3
"""Evaluate OSINT ProfileAnalyzer against the synthetic golden set (fixture mode)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("OSINT_MODE", "fixture")
os.environ.setdefault("LLM_PROVIDER", "heuristic")


def main() -> int:
    from packages.osint.eval_runner import run_eval

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        type=Path,
        default=ROOT / "data" / "evals" / "osint_golden.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "output" / "osint_eval_latest.json",
    )
    args = parser.parse_args()

    report = asyncio.run(run_eval(args.golden))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"OSINT golden eval — {report['cases_passed']}/{report['n_cases']} cases passed")
    print(f"Case pass rate: {report['case_pass_rate']:.2%}")
    for name, m in report["metrics"].items():
        print(
            f"  {name}: P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
            f"(support={m['support']})"
        )
    print(f"Wrote {args.out}")
    print(report["disclaimer"])

    failed = [c["id"] for c in report["cases"] if not c["passed"]]
    if failed:
        print("Failed cases:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
