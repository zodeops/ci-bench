#!/usr/bin/env python3
"""Warm snapshot proof (zoded task 37, REQ-052): for each repository, the
first Zode run (no snapshot) against the next one (forked from the snapshot
the first one saved), step by step, from <out>/runs.jsonl.

  scripts/warm-report.py results/2026-11-12-warm [--steps install,pull]

Steps whose name matches a dependency install or an image pull are the ones
REQ-052 asks to be 5x faster; every step is listed so nothing is hidden.
"""
import json, re, sys, collections

INSTALL = re.compile(r"install|setup|set up|dependenc|npm|yarn|pip|uv |uv$|go mod|download|bundle|maven|mvn|cache|restore|build image|pull|docker|initialize containers", re.I)

def main(out):
    runs = [json.loads(l) for l in open(out + "/runs.jsonl")]
    by = collections.defaultdict(list)
    for r in runs:
        if r["provider"] == "zode":
            by[r["repo"]].append(r)
    for repo, rs in sorted(by.items()):
        rs.sort(key=lambda r: r["dispatched_at"])
        if len(rs) < 2:
            print("##", repo, "only", len(rs), "run(s)"); continue
        a, b = rs[0], rs[1]
        print("## %s  first %s (%s, wall %ss)  second %s (%s, wall %ss)" % (repo, a["run_id"], a["conclusion"], a["wall_s"],
              b["run_id"], b["conclusion"], b["wall_s"]))
        ja = {j["name"]: j for j in a["jobs"]}
        for jb in b["jobs"]:
            j0 = ja.get(jb["name"])
            if not j0:
                continue
            zc = (jb.get("zode") or {}).get("cache") or {}
            za = (j0.get("zode") or {}).get("cache") or {}
            print("  job %-40s first cache_hit=%s  second cache_hit=%s age_ms=%s size=%s  save(first)=%s" % (
                jb["name"][:40], (j0.get("zode") or {}).get("cache_hit"), (jb.get("zode") or {}).get("cache_hit"),
                zc.get("age_ms"), zc.get("size_bytes"), (za.get("save") or {}).get("status")))
            sa = {s["name"]: s for s in j0["steps"]}
            for s in jb["steps"]:
                s0 = sa.get(s["name"])
                if not s0 or s0["s"] is None or s["s"] is None:
                    continue
                mark = "*" if INSTALL.search(s["name"]) else " "
                x = (s0["s"] / s["s"]) if s["s"] else float("inf")
                print("   %s %-50s %7.1fs -> %7.1fs  %5.1fx" % (mark, s["name"][:50], s0["s"], s["s"], x))

if __name__ == "__main__":
    main(sys.argv[1])
