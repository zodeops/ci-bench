#!/usr/bin/env python3
"""Summarise a ci-bench results directory.

  scripts/report.py results/<date>     writes summary.json and report.md there

Per repository, provider and mode: runs, successes, median wall time
(dispatch to last job done), median longest job queue, median summed job
run time. For Zode jobs, the median of every REQ-050 phase, and the check
that the stored phases add up to GitHub's own queue plus run time.
"""
import json
import os
import statistics
import sys
from collections import defaultdict

PHASES = ["webhook", "dispatch", "sandbox", "runner_boot", "assign", "setup", "steps"]


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def p95(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return round(xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))], 1)


def fmt(x, unit="s"):
    return "n/a" if x is None else ("%g%s" % (x, unit))


def secs(a, b):
    from datetime import datetime
    if not a or not b:
        return None
    pa = datetime.fromisoformat(a.replace("Z", "+00:00"))
    pb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return (pb - pa).total_seconds()


def main(d):
    recs = [json.loads(l) for l in open(os.path.join(d, "runs.jsonl")) if l.strip()]
    groups = defaultdict(list)
    for r in recs:
        groups[(r["repo"], r["provider"], r["mode"])].append(r)
    rows = []
    for (repo, prov, mode), all_rs in sorted(groups.items()):
        rs = [r for r in all_rs if r["conclusion"] == "success"] or all_rs
        rows.append({
            "repo": repo, "provider": prov, "runner": rs[0]["runner"], "mode": mode, "runs": len(all_rs),
            "success": sum(1 for r in all_rs if r["conclusion"] == "success"),
            "wall_s_median": med([r["wall_s"] for r in rs]),
            "queue_s_max_median": med([r["queue_s_max"] for r in rs]),
            "run_s_sum_median": med([r["run_s_sum"] for r in rs]),
        })
    # Zode phases, per mode, over every job that ran
    zjobs = defaultdict(list)
    gq = defaultdict(list)
    for r in recs:
        for j in r["jobs"]:
            if j["conclusion"] == "skipped" or not j["started_at"]:
                continue
            if r["provider"] == "zode" and j.get("zode"):
                zjobs[r["mode"]].append(j)
            if r["provider"] == "github":
                gq[r["mode"]].append(j["queue_s"])
    phases = {}
    for mode, js in sorted(zjobs.items()):
        ph = {p: med([(j["zode"]["phase_ms"] or {}).get(p) for j in js]) for p in PHASES + ["queue", "total"]}
        ph["queue_p95"] = p95([(j["zode"]["phase_ms"] or {}).get("queue") for j in js])
        ph["jobs"] = len(js)
        phases[mode] = ph
    gh_queue = {m: {"median_s": med(q), "p95_s": p95(q), "jobs": len(q)} for m, q in gq.items()}
    # REQ-050: stored phases add up to GitHub's queue plus run time within 1 s
    checked = ok = incomplete = 0
    worst = 0.0
    negatives = defaultdict(int)
    for js in zjobs.values():
        for j in js:
            pm = j["zode"]["phase_ms"] or {}
            if any(pm.get(p) is None for p in PHASES):
                incomplete += 1
                continue
            for p in PHASES:
                if pm[p] < 0:
                    negatives[p] += 1
            checked += 1
            github_total = secs(j["created_at"], j["completed_at"])
            diff = abs(sum(pm[p] for p in PHASES) / 1000.0 - github_total)
            worst = max(worst, diff)
            ok += diff <= 1.0
    check = {"jobs_checked": checked, "within_1s": ok, "worst_diff_s": round(worst, 3),
             "jobs_missing_a_phase": incomplete, "negative_phases": dict(negatives)}
    summary = {"results": d, "records": len(recs), "rows": rows, "zode_phases_ms_median": phases,
               "github_queue": gh_queue, "req050_check": check}
    json.dump(summary, open(os.path.join(d, "summary.json"), "w"), indent=1)

    out = ["# ci-bench results: %s" % os.path.basename(os.path.normpath(d)), "",
           "%d runs. Wall is dispatch to the last job done; queue is the longest job's GitHub queue time; "
           "run is the jobs' summed run time. Medians over the runs that passed (over all runs when none "
           "passed)." % len(recs), "",
           "| Repo | Mode | GitHub wall | Zode wall | GitHub queue | Zode queue | GitHub run | Zode run | Passed (GitHub / Zode) |",
           "|---|---|---|---|---|---|---|---|---|"]
    by = {(r["repo"], r["provider"], r["mode"]): r for r in rows}
    for repo in sorted({r["repo"] for r in rows}):
        for mode in ("cold", "warm"):
            g, z = by.get((repo, "github", mode)), by.get((repo, "zode", mode))
            if not g and not z:
                continue
            gv = lambda r, k: fmt(r[k]) if r else "n/a"
            out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s / %s |" % (
                repo, mode, gv(g, "wall_s_median"), gv(z, "wall_s_median"), gv(g, "queue_s_max_median"),
                gv(z, "queue_s_max_median"), gv(g, "run_s_sum_median"), gv(z, "run_s_sum_median"),
                "%d/%d" % (g["success"], g["runs"]) if g else "n/a", "%d/%d" % (z["success"], z["runs"]) if z else "n/a"))
    out += ["", "## Zode phases (median ms over every job that ran)", "",
            "| Mode | Jobs | webhook | dispatch | sandbox | runner_boot | assign | setup | steps | queue (p50 / p95) |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for mode, ph in phases.items():
        out.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s / %s |" % (
            mode, ph["jobs"], *[fmt(ph[p], "") for p in PHASES], fmt(ph["queue"], ""), fmt(ph["queue_p95"], "")))
    out += ["", "GitHub-hosted queue (created to started): " + ", ".join(
        "%s median %s, p95 %s over %d jobs" % (m, fmt(v["median_s"]), fmt(v["p95_s"]), v["jobs"])
        for m, v in sorted(gh_queue.items())), "",
            "REQ-050 check: %d Zode jobs with every phase; %d add up to GitHub's created-to-completed within 1 s "
            "(worst %.3f s); %d missing a phase; negative phases %s." % (
                checked, ok, worst, incomplete, dict(negatives) or "none")]
    open(os.path.join(d, "report.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
