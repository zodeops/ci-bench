#!/usr/bin/env python3
"""Build the data behind the CI benchmark on zode.dev from a results directory.

  scripts/site-data.py results/<date> [--out site/ci.json]

For every repository, provider and mode it picks the median run by wall time
(the lower of the two middle runs when the count is even) and reports that
run's own numbers, so every number on the page is one real run with a link.
Runs that passed are preferred; when none passed, the failed runs are used and
the cell says so. Prices: Zode's is what the run was billed (the jobs'
cost_micros from the Zode API). GitHub-hosted jobs on a public repository are
free, so GitHub's is the list price of the same 4 vCPU, 16 GB machine for a
private repository (the 4-core larger runner), each job rounded up to the
minute as GitHub bills it.

Full-suite and selected runs are kept apart: every run here is a full suite.
Selected runs need Enforce (task 43); until then the selected column is
pending, and so are shards (task 41) on the benchmark set.
"""
import argparse
import datetime as dt
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GitHub's list price, https://docs.github.com/en/billing/reference/actions-runner-pricing
# (read 13 Nov 2026): Linux x64 4-core larger runner, per minute.
GITHUB_4CORE_USD_PER_MIN = 0.012
# Zode's list price for zode-4x8, https://zode.dev/#pricing (src/lib/pricing.ts in zodeops/zode).
ZODE_4X8_USD_PER_HOUR = 0.045

PROVIDERS = {
    "github": {
        "label": "GitHub-hosted",
        "hardware": "4 vCPU, 16 GB RAM, 14 GB SSD (ubuntu-24.04 on a public repository)",
        "price": "List price of the same machine on a private repository: the Linux 4-core larger "
                 "runner at $0.012 a minute, each job rounded up to the minute. Public repositories "
                 "run free.",
        "price_source": "https://docs.github.com/en/billing/reference/actions-runner-pricing",
        "hardware_source": "https://docs.github.com/en/actions/reference/runners/github-hosted-runners",
    },
    "zode": {
        "label": "Zode",
        "hardware": "4 vCPU, 8 GB RAM (zode-4x8) in a microVM on a GCE n2-standard-16 node in "
                    "europe-west1, nested virtualisation, shared with real CI",
        "price": "What the run was billed: each job's runner compute from creation to deletion, "
                 "per second, from the Zode API, at $0.045 an hour for zode-4x8. When a job ran on a "
                 "runner started for another run, its bill sits on that run, so the price shown is "
                 "an estimate: the jobs' run time at the list price.",
        "price_source": "https://zode.dev/#pricing",
        "hardware_source": "https://docs.zode.dev/ci/benchmark",
    },
}

PENDING = {
    "selected": "Every run on this page runs the full suite. Test selection is in Shadow on Zode: it runs "
                "everything and records what it would have skipped. Selected runs need Enforce, which "
                "opens per repository after 200 clean Shadow runs. This column fills then.",
    "shards": "zode-ci test --shards splits a suite across forks of the job's machine. The benchmark "
              "workflows run unchanged, without the wrapper, so their numbers here are single-machine. "
              "Sharded numbers follow once the shard proof on saleor is published.",
}


def parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def median_run(runs):
    """The run whose wall time is the median (lower middle when even)."""
    rs = sorted((r for r in runs if r.get("wall_s") is not None), key=lambda r: r["wall_s"])
    if not rs:
        return None
    return rs[(len(rs) - 1) // 2]


def github_price(run):
    """List price of a run's jobs on the 4-core larger runner, per job rounded up to a minute."""
    total = 0.0
    for j in run["jobs"]:
        if j.get("run_s") is None or j.get("conclusion") == "skipped":
            continue
        total += math.ceil(j["run_s"] / 60.0) * GITHUB_4CORE_USD_PER_MIN
    return round(total, 4)


def zode_price(run):
    """What Zode billed the run's jobs. A job that ran on a runner Zode started
    for a job of another run carries no cost of its own (its runner's bill sits
    on that other job), so such a run gets the list price of its jobs' run
    time instead, marked as an estimate."""
    ran = [j for j in run["jobs"] if j.get("started_at") and j.get("conclusion") != "skipped"]
    micros = [(j.get("zode") or {}).get("cost_micros") for j in ran]
    if ran and all(m for m in micros):
        final = all((j.get("zode") or {}).get("cost_final") for j in ran)
        return round(sum(micros) / 1e6, 4), "billed" if final else "billed_so_far"
    secs_ = sum(j["run_s"] for j in ran if j.get("run_s") is not None)
    return round(secs_ / 3600.0 * ZODE_4X8_USD_PER_HOUR, 4), "estimate"


def cell(runs):
    if not runs:
        return None
    passed = [r for r in runs if r["conclusion"] == "success"]
    pool = passed or runs
    r = median_run(pool)
    if r is None:
        return None
    c = {
        "runs": len(runs),
        "passed": len(passed),
        "failed_runs_only": not passed,
        "wall_s": round(r["wall_s"], 1),
        "queue_s": None if r.get("queue_s_max") is None else round(r["queue_s_max"], 1),
        "run_s": round(r["run_s_sum"], 1),
        "run_id": r["run_id"],
        "run_url": r["run_url"],
        "conclusion": r["conclusion"],
        "dispatched_at": r["dispatched_at"],
        "runner": r["runner"],
    }
    if r["provider"] == "zode":
        c["price_usd"], c["price_kind"] = zode_price(r)
    else:
        c["price_usd"], c["price_kind"] = github_price(r), "list"
    return c


def verdict(gh, zo):
    """How Zode did against GitHub on wall time for one repository and mode."""
    if not gh or not zo:
        return None
    ratio = gh["wall_s"] / zo["wall_s"] if zo["wall_s"] else None
    if ratio is None:
        return None
    if ratio >= 1.05:
        word = "faster"
    elif ratio <= 1 / 1.05:
        word = "slower"
    else:
        word = "even"
    return {
        "ratio": round(ratio, 2),
        "result": {"faster": "win", "slower": "loss", "even": "even"}[word],
        "words": ("%.1fx faster" % ratio) if word == "faster" else
                 ("%.1fx slower" % (1 / ratio)) if word == "slower" else "within 5%",
        "both_passed": gh["passed"] > 0 and zo["passed"] > 0,
    }


def git_head():
    try:
        return subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def build(results_dir, repos_meta):
    recs = [json.loads(l) for l in open(os.path.join(results_dir, "runs.jsonl")) if l.strip()]
    by = {}
    for r in recs:
        by.setdefault((r["repo"], r["provider"], r["mode"]), []).append(r)
    modes = ["cold", "warm"]
    rows = []
    tally = {m: {"win": 0, "loss": 0, "even": 0, "compared": 0} for m in modes}
    for meta in repos_meta:
        name = meta["name"]
        if not any(k[0] == name for k in by):
            continue
        row = {
            "name": name, "upstream": meta["upstream"], "commit": meta["commit"],
            "workflow": meta["workflow"], "lang": meta.get("lang"), "jobs": meta.get("jobs", 1),
            "mirror": meta.get("mirror") or "zodeops/bench-" + name,
            "full": {}, "verdict": {},
        }
        for mode in modes:
            gh = cell(by.get((name, "github", mode), []))
            zo = cell(by.get((name, "zode", mode), []))
            row["full"][mode] = {"github": gh, "zode": zo}
            v = verdict(gh, zo)
            row["verdict"][mode] = v
            if v:
                tally[mode]["compared"] += 1
                tally[mode][v["result"]] += 1
        rows.append(row)
    times = [parse(r["dispatched_at"]) for r in recs if r.get("dispatched_at")]
    ends = [parse(r["completed_at"]) for r in recs if r.get("completed_at")]
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": os.path.relpath(os.path.abspath(results_dir), HERE),
        "harness_commit": git_head(),
        "source": "https://github.com/zodeops/ci-bench",
        "window": {"from": min(times).strftime("%Y-%m-%dT%H:%M:%SZ") if times else None,
                   "to": max(ends).strftime("%Y-%m-%dT%H:%M:%SZ") if ends else None},
        "runs": len(recs),
        "providers": PROVIDERS,
        "tally": tally,
        "pending": PENDING,
        "repos": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--out", default=None, help="also write here (site/ci.json)")
    a = ap.parse_args()
    meta = json.load(open(os.path.join(HERE, "repos.json")))["repos"]
    data = build(a.results, meta)
    body = json.dumps(data, indent=1) + "\n"
    with open(os.path.join(a.results, "site.json"), "w") as f:
        f.write(body)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w") as f:
            f.write(body)
    t = data["tally"]
    print("%d runs, %d repositories; cold: Zode %d wins %d losses; warm: %d wins %d losses" % (
        data["runs"], len(data["repos"]), t["cold"]["win"], t["cold"]["loss"], t["warm"]["win"],
        t["warm"]["loss"]), file=sys.stderr)


if __name__ == "__main__":
    main()
