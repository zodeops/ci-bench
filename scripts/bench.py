#!/usr/bin/env python3
"""Run the ci-bench set on GitHub-hosted runners and on Zode, cold and warm.

  scripts/bench.py [--repos helm,fzf] [--runners ubuntu-24.04,zode-4x8]
                   [--runs 5] [--modes cold,warm] [--out results/<date>]

For every repository, iteration and mode, the providers run side by side at
the same commit, each on its own branch of the mirror (bench-github,
bench-zode), so their Actions caches and concurrency groups never meet.
`cold` deletes that branch's Actions caches first; `warm` runs right after,
with what the cold run saved. Every finished run appends one JSON record to
<out>/runs.jsonl (same shape for every provider; see README.md).

Needs `gh` signed in with access to zodeops, and for Zode runs a Zode API
token of the workspace that owns the zodeops GitHub installation in
$ZODE_TOKEN or ~/.config/zode/ci-bench-token. ZODE_API overrides
https://api.zode.dev. The token is never printed.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZODE_API = os.environ.get("ZODE_API", "https://api.zode.dev")
POLL_S = 60  # one shared GitHub user token: 5,000 calls an hour across every run
RUN_TIMEOUT_S = 90 * 60
_print_lock = threading.Lock()
_write_lock = threading.Lock()


def log(*a):
    with _print_lock:
        print(dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" if t else None


def parse(s):
    if not s:
        return None
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def secs(a, b):
    a, b = parse(a) if isinstance(a, str) else a, parse(b) if isinstance(b, str) else b
    if a is None or b is None:
        return None
    return round((b - a).total_seconds(), 3)


def gh(*args, method="GET", fields=None, paginate=False):
    cmd = ["gh", "api", "-X", method]
    if paginate:
        cmd.append("--paginate")
    for k, v in (fields or {}).items():
        cmd += ["-F" if isinstance(v, bool) else "-f", "%s=%s" % (k, str(v).lower() if isinstance(v, bool) else v)]
    cmd += list(args)
    for attempt in range(8):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            return json.loads(p.stdout) if p.stdout.strip() else None
        if attempt < 7 and "rate limit" in p.stderr.lower():
            wait_for_rate_limit()
            continue
        if attempt < 7 and ("HTTP 5" in p.stderr or "timeout" in p.stderr.lower()):
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError("gh api %s: %s" % (" ".join(args), p.stderr.strip()[:300]))


def wait_for_rate_limit():
    """Sleep until GitHub's core rate limit resets (the rate_limit call is free)."""
    p = subprocess.run(["gh", "api", "rate_limit", "-q", ".resources.core.reset"], capture_output=True, text=True)
    try:
        reset = int(p.stdout.strip())
    except ValueError:
        reset = int(time.time()) + 300
    log("GitHub API rate limit reached; waiting %d s" % max(0, reset - int(time.time())))
    time.sleep(max(30, reset - int(time.time()) + 5))


def zode_token():
    tok = os.environ.get("ZODE_TOKEN")
    if not tok:
        path = os.path.expanduser("~/.config/zode/ci-bench-token")
        if os.path.exists(path):
            tok = open(path).read().strip()
    return tok


def zode_jobs(tok):
    req = urllib.request.Request(ZODE_API + "/v1/ci/jobs?limit=200", headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=30) as r:
        return {j["github_job_id"]: j for j in json.load(r)["jobs"] if "github_job_id" in j}


def provider_of(runner):
    return "zode" if runner.startswith("zode") else "github"


class Budget:
    """Caps how many Zode jobs the harness keeps running at once."""

    def __init__(self, n):
        self.n, self.used, self.cv = n, 0, threading.Condition()

    def take(self, k):
        k = min(k, self.n)
        with self.cv:
            while self.used + k > self.n:
                self.cv.wait()
            self.used += k
        return k

    def give(self, k):
        with self.cv:
            self.used -= k
            self.cv.notify_all()


def delete_caches(mirror, branch):
    ref = "refs/heads/" + branch
    n = 0
    while True:
        res = gh("repos/%s/actions/caches?per_page=100&ref=%s" % (mirror, ref))
        caches = res.get("actions_caches", [])
        if not caches:
            return n
        for c in caches:
            gh("repos/%s/actions/caches/%d" % (mirror, c["id"]), method="DELETE")
            n += 1


def ensure_branch(mirror, base, branch):
    """Make branch point where base does (a per-iteration branch)."""
    sha = gh("repos/%s/git/ref/heads/%s" % (mirror, base))["object"]["sha"]
    try:
        gh("repos/%s/git/ref/heads/%s" % (mirror, branch))
    except RuntimeError:
        gh("repos/%s/git/refs" % mirror, method="POST", fields={"ref": "refs/heads/" + branch, "sha": sha})


def run_one(repo, runner, mode, iteration, out, tok, split=False):
    mirror = repo.get("mirror") or "zodeops/bench-" + repo["name"]
    own = repo.get("own_workflow", False)
    branch = "main" if own else "bench-" + provider_of(runner)
    if split and not own:
        # iterations run at once, each on its own branch: own caches,
        # own concurrency group
        base, branch = branch, "%s-i%d" % (branch, iteration)
        ensure_branch(mirror, base, branch)
    deleted = delete_caches(mirror, branch) if mode == "cold" else 0
    dispatched = now()
    res = gh("repos/%s/actions/workflows/%s/dispatches" % (mirror, repo["workflow"]), method="POST",
             fields={"ref": branch, "inputs[runner]": runner, "return_run_details": True})
    run_id = res["workflow_run_id"]
    log("%-11s %-13s %-4s #%d run %d" % (repo["name"], runner, mode, iteration, run_id))
    deadline = time.time() + RUN_TIMEOUT_S
    zode_failed = None
    while True:
        time.sleep(POLL_S)
        run = gh("repos/%s/actions/runs/%d" % (mirror, run_id))
        if run["status"] == "completed":
            break
        if provider_of(runner) == "zode" and tok and zode_failed is None:
            # A runner Zode could not start leaves GitHub's job queued for
            # hours; stop the run and record why.
            try:
                bad = [j for j in zode_jobs(tok).values() if j.get("run_id") == run_id and
                       j["status"] in ("failed", "refused")]
            except Exception:
                bad = []
            if bad:
                zode_failed = bad[0]["reason"]
                log("%s %s run %d: Zode %s (%s); cancelling" % (repo["name"], runner, run_id, bad[0]["status"],
                                                               zode_failed))
                gh("repos/%s/actions/runs/%d/cancel" % (mirror, run_id), method="POST")
        if time.time() > deadline:
            gh("repos/%s/actions/runs/%d/cancel" % (mirror, run_id), method="POST")
            log("%s %s run %d timed out; cancelled" % (repo["name"], runner, run_id))
            deadline = time.time() + 600
    jobs = gh("repos/%s/actions/runs/%d/jobs?per_page=100&filter=latest" % (mirror, run_id))["jobs"]
    zj = {}
    if provider_of(runner) == "zode" and tok:
        time.sleep(8)  # the completed webhook is handled in the background
        try:
            zj = zode_jobs(tok)
        except Exception as e:  # keep the GitHub side of the record
            log("zode api: %s" % e)
    rec_jobs = []
    for j in jobs:
        z = zj.get(j["id"])
        rec_jobs.append({
            "id": j["id"], "name": j["name"], "conclusion": j["conclusion"], "labels": j["labels"],
            "runner_name": j.get("runner_name"), "created_at": j["created_at"], "started_at": j["started_at"],
            "completed_at": j["completed_at"], "queue_s": secs(j["created_at"], j["started_at"]),
            "run_s": secs(j["started_at"], j["completed_at"]),
            "steps": [{"number": s["number"], "name": s["name"], "conclusion": s["conclusion"],
                       "started_at": s.get("started_at"), "completed_at": s.get("completed_at"),
                       "s": secs(s.get("started_at"), s.get("completed_at"))} for s in j.get("steps", [])],
            "zode": None if z is None else {k: z.get(k) for k in
                                            ("id", "size", "status", "cache_hit", "cost_micros", "cost_final",
                                             "phases", "phase_ms")},
        })
    ran = [j for j in rec_jobs if j["started_at"] and j["conclusion"] != "skipped"]
    first_created = min((parse(j["created_at"]) for j in rec_jobs), default=None)
    last_done = max((parse(j["completed_at"]) for j in rec_jobs if j["completed_at"]), default=None)
    rec = {
        "schema": 1, "repo": repo["name"], "upstream": repo["upstream"], "commit": repo["commit"],
        "mirror": mirror, "workflow": repo["workflow"], "branch": branch,
        "provider": provider_of(runner), "runner": runner, "mode": mode, "iteration": iteration,
        "caches_deleted": deleted, "zode_failed": zode_failed, "run_id": run_id, "run_url": run["html_url"], "conclusion": run["conclusion"],
        "dispatched_at": iso(dispatched), "first_job_created_at": iso(first_created), "completed_at": iso(last_done),
        "wall_s": secs(dispatched, last_done),
        "queue_s_max": max((j["queue_s"] for j in ran if j["queue_s"] is not None), default=None),
        "run_s_sum": round(sum(j["run_s"] for j in ran if j["run_s"] is not None), 3),
        "jobs": rec_jobs,
    }
    with _write_lock, open(os.path.join(out, "runs.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    log("%-11s %-13s %-4s #%d %s wall %ss" % (repo["name"], runner, mode, iteration, run["conclusion"], rec["wall_s"]))
    return rec


def done_runs(out):
    """(repo, runner, mode, iteration) already recorded in out/runs.jsonl."""
    path = os.path.join(out, "runs.jsonl")
    if not os.path.exists(path):
        return set()
    seen = set()
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            seen.add((r["repo"], r["runner"], r["mode"], r["iteration"]))
    return seen


def bench_iteration(repo, runners, modes, it, out, tok, budget, done, split):
    for mode in modes:
        todo = [r for r in runners if (repo["name"], r, mode, it) not in done]
        if not todo:
            continue
        zjobs = sum(repo.get("jobs", 1) for r in todo if provider_of(r) == "zode")
        took = budget.take(zjobs) if zjobs else 0
        try:
            with ThreadPoolExecutor(len(todo)) as ex:
                futs = [ex.submit(run_one, repo, r, mode, it, out, tok, split) for r in todo]
                for f in futs:
                    try:
                        f.result()
                    except Exception as e:
                        log("%s #%d %s failed: %s" % (repo["name"], it, mode, e))
        finally:
            if took:
                budget.give(took)


def bench_repo(repo, runners, modes, runs, out, tok, budget, start, done, split):
    its = range(start, start + runs)
    if not split:
        for it in its:
            bench_iteration(repo, runners, modes, it, out, tok, budget, done, False)
        return
    with ThreadPoolExecutor(len(its)) as ex:
        for f in [ex.submit(bench_iteration, repo, runners, modes, it, out, tok, budget, done, True) for it in its]:
            f.result()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default="all")
    ap.add_argument("--runners", default="ubuntu-24.04,zode-4x8")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--start", type=int, default=1, help="first iteration number (to resume)")
    ap.add_argument("--modes", default="cold,warm")
    ap.add_argument("--out", default=os.path.join(HERE, "results", now().strftime("%Y-%m-%d")))
    ap.add_argument("--parallel", type=int, default=4, help="repositories at once")
    ap.add_argument("--zode-jobs", type=int, default=8, help="Zode jobs at once, to leave room for real CI")
    ap.add_argument("--resume", action="store_true", help="skip runs already in <out>/runs.jsonl")
    ap.add_argument("--split", default="", help="repos whose iterations run at once, each on its own branch")
    a = ap.parse_args()
    repos = json.load(open(os.path.join(HERE, "repos.json")))["repos"]
    if a.repos != "all":
        want = a.repos.split(",")
        repos = [r for r in repos if r["name"] in want]
    runners = a.runners.split(",")
    tok = zode_token()
    if any(provider_of(r) == "zode" for r in runners) and not tok:
        sys.exit("no Zode token: set ZODE_TOKEN or write ~/.config/zode/ci-bench-token")
    os.makedirs(a.out, exist_ok=True)
    budget = Budget(a.zode_jobs)
    # longest first, so the long ones are not left for last
    order = {"saleor": 0, "nginx-proxy": 1, "fzf": 2, "alpine": 3, "helm": 4, "excalidraw": 5}
    repos.sort(key=lambda r: order.get(r["name"], 9))
    with ThreadPoolExecutor(a.parallel) as ex:
        done = done_runs(a.out) if a.resume else set()
        split = set(a.split.split(",")) - {""}
        for f in [ex.submit(bench_repo, r, runners, a.modes.split(","), a.runs, a.out, tok, budget, a.start, done,
                            r["name"] in split) for r in repos]:
            f.result()
    log("done: %s" % os.path.join(a.out, "runs.jsonl"))


if __name__ == "__main__":
    main()
