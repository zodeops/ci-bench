#!/usr/bin/env python3
"""Per repository and job: the first Zode run (no snapshot) against every
later run whose runner started warm, for steps that install dependencies,
set up tools or pull images. Usage: scripts/warm-summary.py <out dir>"""
import json, re, sys, collections
STEP = re.compile(r"install|set ?up|setup|npm|yarn|pip|gems|bundle|mod download|pull|docker|maven|initialize containers", re.I)
SKIP = re.compile(r"^(Set up job|Set up runner|Post |Complete job)", re.I)
runs = [json.loads(l) for l in open(sys.argv[1] + "/runs.jsonl") if json.loads(l)["provider"] == "zode"]
runs.sort(key=lambda r: r["dispatched_at"])
by = collections.defaultdict(list)
for r in runs:
    for j in r["jobs"]:
        by[(r["repo"], j["name"])].append((r, j))
hits = total = 0
for (repo, job), rs in sorted(by.items()):
    first = rs[0][1]
    steps0 = {s["name"]: s["s"] for s in first["steps"]}
    later = [(r, j) for r, j in rs[1:] if j.get("started_at")]
    total += len(later)
    warm = [(r, j) for r, j in later if (j.get("zode") or {}).get("cache_hit")]
    hits += len(warm)
    print("## %s / %s: %d later runs, %d warm" % (repo, job, len(later), len(warm)))
    for r, j in warm:
        c = j["zode"]["cache"]
        print("   run %s (%s #%d) age %ss size %.1f GB" % (r["run_id"], r["mode"], r["iteration"], (c.get("age_ms") or 0)//1000, (c.get("size_bytes") or 0)/1e9))
        for s in j["steps"]:
            a = steps0.get(s["name"]); b = s["s"]
            if a is None or b is None or SKIP.match(s["name"]) or not STEP.search(s["name"]) or a < 3:
                continue
            print("     %-45s %6.0fs -> %4.0fs  %s" % (s["name"][:45], a, b, ("%.1fx" % (a / b)) if b else ">%dx" % a))
print("warm second-and-later runs: %d of %d" % (hits, total))
