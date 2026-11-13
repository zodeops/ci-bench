#!/usr/bin/env python3
"""CI pilot readout (zoded task 47, PRD gate GCI).

Reads only the public Zode API with the workspace's token ($ZODE_TOKEN or
~/.config/zode/ci-bench-token; never printed) and prints a markdown readout
for a time window and a list of repositories:

- jobs by repository and conclusion;
- P1 candidates: jobs Zode failed or refused, and jobs Zode marked failed
  while GitHub never started them;
- stranded jobs: queued, provisioning or waiting for more than 30 min, or
  failed with no end;
- would-be misses (Shadow) and real misses (the miss ledger);
- background full runs and their results;
- clean Shadow runs toward the 200 Enforce needs, per repository;
- CI machines in use at once at peak (from job runner intervals) and the
  workspace's CI limit.

GET /v1/ci/jobs answers the newest 200 jobs only, so a 14-day window needs
the job rows collected as they happen: --collect FILE appends new and
changed rows (by id) to a JSON-lines file, and --jobs FILE reads them back.
.github/workflows/pilot.yml collects every 15 minutes into
results/pilot/jobs.jsonl.

  scripts/pilot-readout.py --collect results/pilot/jobs.jsonl
  scripts/pilot-readout.py --since 2026-11-13 --until 2026-11-27 \\
      --jobs results/pilot/jobs.jsonl --repos zodeops/zoded,zodeops/zode
"""

import argparse
import collections
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("ZODE_API", "https://api.zode.dev")
PILOT = ["zodeops/zoded", "zodeops/zode", "zodeops/docs", "zodeops/ci-bench", "zodeops/runner-images"]
STRANDED_AFTER = dt.timedelta(minutes=30)


def token():
    t = os.environ.get("ZODE_TOKEN")
    if not t:
        with open(os.path.expanduser("~/.config/zode/ci-bench-token")) as f:
            t = f.read().strip()
    return t


def get(path, tok):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + tok})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
    return {}


def ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    t = dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def when(s):
    t = ts(s if "T" in s else s + "T00:00:00Z")
    return t


def load_jobs(path):
    rows = {}
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    j = json.loads(line)
                    rows[j["id"]] = j  # last line for an id wins
    return rows


def collect(path, tok):
    have = load_jobs(path)
    fresh = get("/v1/ci/jobs?limit=200", tok)["jobs"]
    # This file is public: no branch, workflow, job name or link (private
    # repositories' rows are in it too). The job id finds the rest in the
    # console or GET /v1/ci/jobs/{id}.
    keep = ("id", "github_job_id", "repo", "size", "status", "conclusion", "reason", "sandbox_id",
            "queued_at", "started_at", "completed_at", "phases", "runner_source")
    n = 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as f:
        for j in reversed(fresh):
            row = {k: j.get(k) for k in keep}
            if have.get(j["id"]) != row:
                f.write(json.dumps(row, sort_keys=True) + "\n")
                n += 1
    oldest = fresh[-1]["queued_at"] if fresh else None
    print(f"collected {n} new or changed rows; the API window starts at {oldest}", file=sys.stderr)


def machine_interval(j, now):
    p = j.get("phases") or {}
    start = min([t for t in (ts(p.get("runner_requested_at")), ts(p.get("sandbox_ready_at")),
                             ts(p.get("picked_up_at")), ts(j.get("started_at"))) if t] or [None]) \
        if any(p.get(k) for k in ("runner_requested_at", "sandbox_ready_at", "picked_up_at")) or j.get("started_at") \
        else None
    if not start:
        return None
    end = ts(j.get("completed_at")) or (now if j["status"] in ("running", "waiting", "provisioning") else start)
    return start, end


def peak(intervals):
    ev = []
    for s, e in intervals:
        ev.append((s, 1))
        ev.append((e, -1))
    ev.sort(key=lambda x: (x[0], x[1]))
    cur = best = 0
    at = None
    for t, d in ev:
        cur += d
        if cur > best:
            best, at = cur, t
    return best, at


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="2026-11-13")
    ap.add_argument("--until", default="2026-11-27T23:59:59Z")
    ap.add_argument("--repos", default=",".join(PILOT))
    ap.add_argument("--jobs", default="results/pilot/jobs.jsonl", help="collected job rows (JSON lines)")
    ap.add_argument("--collect", metavar="FILE", help="append the API's newest job rows to FILE and stop")
    a = ap.parse_args()
    tok = token()
    if a.collect:
        collect(a.collect, tok)
        return
    since, until = when(a.since), when(a.until)
    now = dt.datetime.now(dt.timezone.utc)
    repos = [r.strip() for r in a.repos.split(",") if r.strip()]

    rows = load_jobs(a.jobs)
    for j in get("/v1/ci/jobs?limit=200", tok)["jobs"]:  # newest state wins
        rows[j["id"]] = j
    win = [j for j in rows.values() if since <= ts(j["queued_at"]) <= until]
    mine = [j for j in win if j["repo"] in repos]
    first = min((ts(j["queued_at"]) for j in win), default=None)

    out = []
    w = out.append
    w(f"# CI pilot readout, {since:%Y-%m-%d %H:%M} to {min(until, now):%Y-%m-%d %H:%M} UTC\n")
    w(f"Repositories: {', '.join(repos)}. Read {now:%Y-%m-%d %H:%M} UTC from {API}.")
    w(f"Job rows in the window: {len(win)} for the workspace, {len(mine)} for these repositories"
      f" (oldest row held: {first:%Y-%m-%d %H:%M} UTC)." if first else "No job rows in the window.")
    w("")

    w("## Jobs by repository and conclusion\n")
    w("| Repository | Jobs | " + " | ".join(["success", "failure", "cancelled", "skipped", "other", "Zode failed", "refused", "open"]) + " |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for r in repos:
        js = [j for j in mine if j["repo"] == r]
        c = collections.Counter()
        for j in js:
            if j["status"] == "completed":
                k = j.get("conclusion") or "other"
                c[k if k in ("success", "failure", "cancelled", "skipped") else "other"] += 1
            elif j["status"] == "failed":
                c["Zode failed"] += 1
            elif j["status"] == "refused":
                c["refused"] += 1
            else:
                c["open"] += 1
        w(f"| {r} | {len(js)} | " + " | ".join(str(c[k]) for k in ["success", "failure", "cancelled", "skipped", "other", "Zode failed", "refused", "open"]) + " |")
    w("")

    w("## P1 candidates\n")
    p1 = [j for j in mine if j["status"] in ("failed", "refused")]
    if not p1:
        w("None: no job Zode failed or refused.\n")
    else:
        w("| Job | Repository | Status | Started by GitHub | Reason |")
        w("|---|---|---|---|---|")
        for j in sorted(p1, key=lambda j: j["queued_at"]):
            w(f"| {j['id']} | {j['repo']} | {j['status']} | {'yes' if j.get('started_at') else 'no'} | {(j.get('reason') or '').replace('|', '/')[:140]} |")
        w("")
        w("Each needs a cause: a refusal by the workspace's own cap is not a P1; a job Zode failed while GitHub never started it is.\n")

    w("## Stranded jobs\n")
    stranded = [j for j in mine if (j["status"] in ("queued", "provisioning", "waiting") and now - ts(j["queued_at"]) > STRANDED_AFTER)
                or (j["status"] == "failed" and not j.get("completed_at") and not j.get("started_at"))]
    if not stranded:
        w("None: no job queued, starting or waiting for more than 30 min, and no failed job left without an end.\n")
    else:
        w("| Job | Repository | Status | Queued | Reason |")
        w("|---|---|---|---|---|")
        for j in stranded:
            w(f"| {j['id']} | {j['repo']} | {j['status']} | {j['queued_at']} | {(j.get('reason') or '').replace('|', '/')[:140]} |")
        w("")

    w("## Selection: Shadow runs and misses\n")
    sel = get("/v1/ci/selection", tok)
    modes = {r["repo"]: r for r in sel.get("repos", [])}
    runs = collections.defaultdict(list)
    for r in repos:
        for s in get("/v1/ci/selection-runs?repo=" + r + "&limit=200", tok).get("runs", []):
            if since <= ts(s["created_at"]) <= until:
                runs[r].append(s)
    misses = [m for m in get("/v1/ci/selection-misses?limit=200", tok).get("misses", []) if since <= ts(m["created_at"]) <= until]
    w("| Repository | Mode | Selection runs (newest 200) | Full runs | Would-be misses | Real misses | Clean Shadow runs toward 200 |")
    w("|---|---|---|---|---|---|---|")
    for r in repos:
        m = modes.get(r, {})
        rs = runs[r]
        w(f"| {r} | {m.get('mode', sel.get('default_mode', 'shadow'))} | {len(rs)} | {sum(1 for s in rs if s.get('full'))} | "
          f"{sum((s.get('outcome') or {}).get('would_miss', 0) for s in rs)} | {sum(1 for x in misses if x['repo'] == r)} | "
          f"{m.get('clean_shadow_runs', 0)} of {sel.get('runs_needed', 200)} |")
    w("")
    other = [x for x in misses if x["repo"] not in repos]
    if misses:
        w("Miss ledger in the window (every repository of the workspace):\n")
        for x in misses:
            w(f"- {x['created_at']} {x['repo']} {x['test']}: skipped because \"{x.get('skip_reason')}\" ({x.get('branch')}, {x['commit'][:10]})")
        w("")
    if other:
        w(f"{len(other)} of these misses are on repositories outside the pilot list (the Enforce proof repository is one).\n")

    w("## Background full runs\n")
    bg = [b for b in get("/v1/ci/background-runs?limit=200", tok).get("runs", [])]
    bgw = [b for b in bg if since <= ts(b.get("created_at") or b.get("started_at") or "1970-01-01T00:00:00Z") <= until]
    if not bgw:
        w("None in the window.\n")
    else:
        c = collections.Counter((b["repo"], b["status"]) for b in bgw)
        for (r, st), n in sorted(c.items()):
            w(f"- {r}: {n} {st}")
        w("")

    w("## CI machines at peak\n")
    ints = {}
    for j in win:
        iv = machine_interval(j, now)
        if iv:
            ints[j.get("sandbox_id") or j["id"]] = iv  # one machine per sandbox
    pk, at = peak(ints.values())
    pkm, atm = peak([machine_interval(j, now) for j in mine if machine_interval(j, now)])
    ci = get("/v1/ci", tok)
    lim = ci.get("limit") or {}
    w(f"Workspace: {pk} runner machines at once at peak ({at:%Y-%m-%d %H:%M} UTC)." if at else "Workspace: no runner intervals.")
    w(f"Pilot repositories alone: {pkm} at once ({atm:%Y-%m-%d %H:%M} UTC)." if atm else "Pilot repositories alone: none.")
    w(f"Limit now: plan {lim.get('plan')}, {lim.get('max_machines')} machines"
      f"{' (provisional)' if lim.get('provisional') else ''}; {lim.get('running')} running, {lim.get('waiting')} waiting.")
    w("Shard workers and background runs are not in the job rows and are not counted here.\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
