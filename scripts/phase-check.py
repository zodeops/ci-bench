#!/usr/bin/env python3
"""REQ-050 check: Zode's stored phases add up to GitHub's own queue plus run time.

  scripts/phase-check.py [--since 2026-11-12T10:50:00Z] [--out file.json]

Reads the workspace's completed CI jobs from the Zode API (GET /v1/ci/jobs,
newest 200), fetches each job from GitHub's API, and compares the sum of the
seven phases (webhook .. steps) with GitHub's created_at to completed_at.
Token as in bench.py. Prints a summary; --out keeps every row.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import ZODE_API, gh, parse, zode_token  # noqa: E402

PHASES = ["webhook", "dispatch", "sandbox", "runner_boot", "assign", "setup", "steps"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    tok = zode_token()
    req = urllib.request.Request(ZODE_API + "/v1/ci/jobs?limit=200", headers={"Authorization": "Bearer " + tok})
    jobs = json.load(urllib.request.urlopen(req, timeout=30))["jobs"]
    rows, missing = [], {}
    for j in jobs:
        if j["status"] != "completed" or j["conclusion"] in ("cancelled", "skipped") or not j["started_at"]:
            continue
        if a.since and j["queued_at"] < a.since:
            continue
        pm = j["phase_ms"]
        gaps = [p for p in PHASES if pm.get(p) is None]
        if gaps:
            for p in gaps:
                missing[p] = missing.get(p, 0) + 1
            rows.append({"id": j["id"], "repo": j["repo"], "complete": False, "missing": gaps})
            continue
        g = gh("repos/%s/actions/jobs/%d" % (j["repo"], j["github_job_id"]))
        github_s = (parse(g["completed_at"]) - parse(g["created_at"])).total_seconds()
        zode_s = sum(pm[p] for p in PHASES) / 1000.0
        rows.append({"id": j["id"], "repo": j["repo"], "complete": True, "github_total_s": github_s,
                     "zode_phase_sum_s": zode_s, "diff_s": round(zode_s - github_s, 3),
                     "negative": [p for p in PHASES if pm[p] < 0], "phase_ms": pm})
    full = [r for r in rows if r["complete"]]
    ok = [r for r in full if abs(r["diff_s"]) <= 1.0]
    print("completed jobs: %d; with every phase: %d; phases add up to GitHub's created-to-completed within 1 s: %d"
          % (len(rows), len(full), len(ok)))
    if full:
        print("worst difference: %.3f s" % max(abs(r["diff_s"]) for r in full))
    print("missing phases: %s" % (missing or "none"))
    neg = {}
    for r in full:
        for p in r["negative"]:
            neg[p] = neg.get(p, 0) + 1
    print("negative phases: %s" % (neg or "none"))
    if a.out:
        json.dump(rows, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
