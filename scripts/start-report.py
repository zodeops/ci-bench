#!/usr/bin/env python3
"""Summarise start-load.py lines: queued to first step (REQ-051) per runner
size, label and runner source, with the REQ-050 phase medians.

  scripts/start-report.py results/2026-11-13/start/*.jsonl [--md]

queued to first step is phase_ms.queue + phase_ms.setup (GitHub created the
job to its first step started). Jobs that never ran a step are counted apart.
"""

import argparse
import json
import math
from collections import defaultdict


def pct(v, p):
    if not v:
        return None
    v = sorted(v)
    k = max(0, math.ceil(p / 100 * len(v)) - 1)  # nearest rank
    return v[k]


def fmt(x):
    return "-" if x is None else (f"{x / 1000:.1f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--md", action="store_true", help="Markdown table")
    a = ap.parse_args()
    rows = []
    for f in a.files:
        with open(f) as fh:
            rows += [json.loads(line) for line in fh if line.strip()]
    groups = defaultdict(list)
    for r in rows:
        groups[(r["runner"], r["label"])].append(r)
    phases = ["webhook", "dispatch", "sandbox", "runner_boot", "assign", "setup"]
    out = []
    for (runner, label), rs in sorted(groups.items()):
        ok = [r for r in rs if r["phase_ms"]["queue"] is not None and r["phase_ms"]["setup"] is not None]
        start = [r["phase_ms"]["queue"] + r["phase_ms"]["setup"] for r in ok]
        src = defaultdict(int)
        for r in rs:
            src[r.get("runner_source") or "none"] += 1
        by_src = {}
        for s in src:
            v = [r["phase_ms"]["queue"] + r["phase_ms"]["setup"] for r in ok if (r.get("runner_source") or "none") == s]
            by_src[s] = (len(v), pct(v, 50), pct(v, 95))
        med = {p: pct([r["phase_ms"][p] for r in rs if r["phase_ms"][p] is not None], 50) for p in phases}
        out.append({"runner": runner, "label": label, "jobs": len(rs), "started": len(ok),
                     "p50_ms": pct(start, 50), "p95_ms": pct(start, 95), "max_ms": max(start) if start else None,
                     "within_5s": sum(1 for x in start if x <= 5000), "within_10s": sum(1 for x in start if x <= 10000),
                     "by_source": by_src, "phase_p50_ms": med})
    if not a.md:
        print(json.dumps(out, indent=1))
        return
    print("| Size | Load | Jobs (ran) | p50 | p95 | max | <= 5 s | <= 10 s | By runner source (jobs, p50, p95) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for o in out:
        src = "; ".join(f"{s} {n}, {fmt(p50)}, {fmt(p95)}" for s, (n, p50, p95) in sorted(o["by_source"].items()))
        print(f"| {o['runner']} | {o['label']} | {o['jobs']} ({o['started']}) | {fmt(o['p50_ms'])} | {fmt(o['p95_ms'])} | "
              f"{fmt(o['max_ms'])} | {o['within_5s']} | {o['within_10s']} | {src} |")
    print()
    print("| Size | Load | " + " | ".join(phases) + " |")
    print("|---|---|" + "---|" * len(phases))
    for o in out:
        print(f"| {o['runner']} | {o['label']} | " + " | ".join(fmt(o["phase_p50_ms"][p]) for p in phases) + " |")


if __name__ == "__main__":
    main()
