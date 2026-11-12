#!/usr/bin/env python3
"""Build results/2026-11-12/runs.jsonl, the 12 Nov 2026 baseline set, from the raw runs.

The raw directories keep every run. The baseline drops:
- fzf GitHub runs dispatched before the mirror got its release tag (10:21:09Z;
  `make` stopped at `git describe`, a mirror defect, not a runner one);
- Zode runs of jquery, starlette, httpx, petclinic and caddy before zoded #100
  went live (16:41:10Z): a full node failed their runners in about a minute
  (`zode_failed`), so they measured that bug, not CI. They stay in zode/ and
  zode-short/ and are counted in docs/ci-acceptance.md.
"""
import json
import os

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "2026-11-12")
FZF_TAGGED = "2026-11-12T10:21:09Z"
SHORT = {"jquery", "starlette", "httpx", "petclinic", "caddy"}


def load(sub):
    p = os.path.join(D, sub, "runs.jsonl")
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


out = [r for r in load("github") if not (r["repo"] == "fzf" and r["dispatched_at"] < FZF_TAGGED)]
out += load("fzf-rerun")
out += [r for r in load("zode") if r["repo"] not in SHORT]
out += load("zode-post")
with open(os.path.join(D, "runs.jsonl"), "w") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
print(len(out), "runs")
