#!/usr/bin/env python3
"""Start-time load for Zode CI (PRD REQ-051, zoded task 36).

Dispatches zodeops/ci-start's `start` workflow (one job per matrix entry,
each job only prints its runner) again and again on one runner size, waits
for each run to finish, then waits --gap seconds so the repository's standby
runners can refill, and records every job's REQ-050 phases from Zode's
`GET /v1/ci/jobs/{id}` as one JSON line. scripts/start-report.py turns the
lines into p50/p95 per size.

  scripts/start-load.py --runner zode-2x4 --width 4 --jobs 500 --gap 25

Needs gh (for the dispatch) and a Zode token of the workspace that owns the
zodeops installation ($ZODE_TOKEN or ~/.config/zode/ci-bench-token). The
token is never printed. ZODE_API overrides https://api.zode.dev.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ZODE_API = os.environ.get("ZODE_API", "https://api.zode.dev")


def log(*a):
    print(dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


def token():
    t = os.environ.get("ZODE_TOKEN")
    if not t:
        with open(os.path.expanduser("~/.config/zode/ci-bench-token")) as f:
            t = f.read().strip()
    return t


def zode(path, tok):
    req = urllib.request.Request(ZODE_API + path, headers={"Authorization": "Bearer " + tok})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 4:
                raise
            log("zode api retry", path, e)
            time.sleep(2 + attempt * 3)


def dispatch(repo, runner, width, io=False):
    """Dispatch the workflow; GitHub returns the run id (return_run_details)."""
    body = json.dumps({"ref": "main", "return_run_details": True,
                       "inputs": {"runner": runner, "matrix": json.dumps(list(range(1, width + 1))),
                                  **({"io": "1"} if io else {})}})
    out = subprocess.run(["gh", "api", "-X", "POST", f"repos/{repo}/actions/workflows/start.yml/dispatches",
                          "--input", "-"], input=body, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("dispatch: " + (out.stderr or out.stdout).strip()[:300])
    return json.loads(out.stdout)["workflow_run_id"]


def run_jobs(tok, run_id):
    """Zode's rows of this run (newest 200 jobs of the workspace)."""
    rows = zode("/v1/ci/jobs?limit=200", tok)["jobs"]
    return [j for j in rows if j["run_id"] == run_id]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default="zodeops/ci-start")
    ap.add_argument("--runner", required=True, help="zode-2x4, zode-4x8, ...")
    ap.add_argument("--width", type=int, default=1, help="jobs per run")
    ap.add_argument("--jobs", type=int, default=500, help="stop after this many jobs")
    ap.add_argument("--gap", type=float, default=25, help="seconds between a run finishing and the next dispatch")
    ap.add_argument("--timeout", type=float, default=900, help="give up on a run after this many seconds")
    ap.add_argument("--out", required=True, help="JSON lines file (appended)")
    ap.add_argument("--label", default="active", help="free-form tag written on every line")
    ap.add_argument("--io", action="store_true", help="each job also writes 1 GB (first heavy I/O)")
    a = ap.parse_args()
    tok = token()
    done = 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "a") as out:
        while done < a.jobs:
            width = min(a.width, a.jobs - done)
            t0 = time.time()
            try:
                run_id = dispatch(a.repo, a.runner, width, a.io)
            except Exception as e:  # noqa: BLE001 - log and try again
                log("dispatch failed:", e)
                time.sleep(30)
                continue
            final = []
            while time.time() - t0 < a.timeout:
                time.sleep(4)
                try:
                    rows = run_jobs(tok, run_id)
                except Exception as e:  # noqa: BLE001
                    log("read failed:", e)
                    continue
                if len(rows) >= width and all(r["status"] in ("completed", "refused", "failed") for r in rows):
                    final = rows
                    break
            if not final:
                log(f"run {run_id} did not finish in {a.timeout}s; skipped")
            for r in final:
                detail = zode("/v1/ci/jobs/" + r["id"], tok)
                rec = {"schema": 1, "label": a.label, "repo": a.repo, "runner": a.runner, "width": width,
                       "run_id": run_id, "github_job_id": r["github_job_id"], "zode_id": r["id"],
                       "status": r["status"], "conclusion": r["conclusion"], "reason": r["reason"],
                       "runner_source": r.get("runner_source"), "cost_micros": r["cost_micros"],
                       "phases": r["phases"], "phase_ms": r["phase_ms"],
                       "steps": [{k: s[k] for k in ("number", "name", "started_at", "completed_at")}
                                 for s in detail.get("steps", [])]}
                out.write(json.dumps(rec) + "\n")
                done += 1
            out.flush()
            qs = [((r["phase_ms"]["queue"] or 0) + (r["phase_ms"]["setup"] or 0)) / 1000 for r in final]
            log(f"run {run_id}: {len(final)} jobs, queued->first step {qs}, sources "
                f"{[r.get('runner_source') for r in final]}; {done}/{a.jobs}")
            time.sleep(a.gap)


if __name__ == "__main__":
    main()
