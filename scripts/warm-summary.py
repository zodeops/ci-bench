#!/usr/bin/env python3
"""Per repository and job: the first Zode run (no snapshot) against every
later run whose runner started warm, for steps that install dependencies,
set up tools or pull images. Usage: scripts/warm-summary.py <out dir> [<baseline dir>]

With a baseline dir, the clean reference is the first Zode run of each job
there (for a rerun whose repositories already had snapshots, so even its
first runs start warm), and every run of <out dir> counts."""
import json, re, sys, collections
STEP = re.compile(r"install|set ?up|setup|npm|yarn|pip|gems|bundle|mod download|pull|docker|maven|initialize containers", re.I)
SKIP = re.compile(r"^(Set up job|Set up runner|Post |Complete job)", re.I)
def load(d):
    rs = [json.loads(l) for l in open(d + "/runs.jsonl") if json.loads(l)["provider"] == "zode"]
    rs.sort(key=lambda r: r["dispatched_at"])
    by = collections.defaultdict(list)
    for r in rs:
        for j in r["jobs"] or []:
            by[(r["repo"], j["name"])].append((r, j))
    return by
by = load(sys.argv[1])
base = load(sys.argv[2]) if len(sys.argv) > 2 else None
hits = total = 0
for (repo, job), rs in sorted(by.items()):
    if base is not None:
        if not base.get((repo, job)):
            continue
        first, later = base[(repo, job)][0][1], [(r, j) for r, j in rs if j.get("started_at")]
    else:
        first, later = rs[0][1], [(r, j) for r, j in rs[1:] if j.get("started_at")]
    steps0 = {s["name"]: s["s"] for s in first["steps"]}
    total += len(later)
    warm = [(r, j) for r, j in later if (j.get("zode") or {}).get("cache_hit")]
    hits += len(warm)
    print("## %s / %s: %d %s runs, %d warm" % (repo, job, len(later), "measured" if base is not None else "later", len(warm)))
    for r, j in warm:
        c = j["zode"]["cache"]
        print("   run %s (%s #%d) age %ss size %.1f GB" % (r["run_id"], r["mode"], r["iteration"], (c.get("age_ms") or 0)//1000, (c.get("size_bytes") or 0)/1e9))
        for s in j["steps"]:
            a = steps0.get(s["name"]); b = s["s"]
            if a is None or b is None or SKIP.match(s["name"]) or not STEP.search(s["name"]) or a < 3:
                continue
            print("     %-45s %6.0fs -> %4.0fs  %s" % (s["name"][:45], a, b, ("%.1fx" % (a / b)) if b else ">%dx" % a))
print("warm %s runs: %d of %d" % ("measured" if base is not None else "second-and-later", hits, total))
