"""Tests for scripts/site-data.py. ci-bench's own CI runs these on Zode with
the sample workflow from the docs (.github/workflows/test.yml)."""
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("site_data", os.path.join(HERE, "scripts", "site-data.py"))
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)


def run(provider, wall, conclusion="success", jobs=None, run_id=1):
    return {"repo": "x", "provider": provider, "runner": "zode-4x8" if provider == "zode" else "ubuntu-24.04",
            "mode": "cold", "iteration": run_id, "run_id": run_id, "run_url": "https://example/%d" % run_id,
            "conclusion": conclusion, "dispatched_at": "2026-11-15T02:00:00.000Z",
            "completed_at": "2026-11-15T02:10:00.000Z", "wall_s": wall, "queue_s_max": 2.0,
            "run_s_sum": wall - 2, "jobs": jobs or [{"run_s": wall - 2, "started_at": "t", "conclusion": conclusion,
                                                    "zode": None}]}


def test_median_run_is_a_real_run_lower_middle_when_even():
    rs = [run("github", w, run_id=i) for i, w in enumerate([50, 10, 40, 20])]
    assert sd.median_run(rs)["wall_s"] == 20


def test_cell_prefers_passed_runs_and_says_when_none_passed():
    rs = [run("github", 10, "failure", run_id=1), run("github", 30, run_id=2), run("github", 50, run_id=3)]
    c = sd.cell(rs)
    assert (c["passed"], c["runs"], c["failed_runs_only"]) == (2, 3, False)
    assert c["run_id"] == 2 and c["wall_s"] == 30
    c = sd.cell([run("github", 10, "failure")])
    assert c["failed_runs_only"] is True


def test_github_list_price_rounds_each_job_up_to_a_minute():
    r = run("github", 100, jobs=[{"run_s": 61, "started_at": "t", "conclusion": "success"},
                                 {"run_s": 5, "started_at": "t", "conclusion": "success"},
                                 {"run_s": None, "started_at": None, "conclusion": "skipped"}])
    assert sd.github_price(r) == round(3 * 0.012, 4)


def test_zode_price_is_billed_or_marked_estimate():
    billed = run("zode", 100, jobs=[{"run_s": 90, "started_at": "t", "conclusion": "success",
                                     "zode": {"cost_micros": 1500, "cost_final": True}}])
    assert sd.zode_price(billed) == (0.0015, "billed")
    sibling = run("zode", 100, jobs=[{"run_s": 3600, "started_at": "t", "conclusion": "success",
                                      "zode": {"cost_micros": 0, "cost_final": True}}])
    assert sd.zode_price(sibling) == (0.045, "estimate")


def test_verdict_names_losses():
    gh, zo = {"wall_s": 100, "passed": 1}, {"wall_s": 250, "passed": 1}
    v = sd.verdict(gh, zo)
    assert v["result"] == "loss" and v["words"] == "2.5x slower"
    v = sd.verdict({"wall_s": 300, "passed": 1}, {"wall_s": 100, "passed": 0})
    assert v["result"] == "win" and v["both_passed"] is False
    assert sd.verdict({"wall_s": 100, "passed": 1}, {"wall_s": 102, "passed": 1})["result"] == "even"


def test_published_data_matches_its_runs():
    """site/ci.json regenerates from the results it names."""
    path = os.path.join(HERE, "site", "ci.json")
    if not os.path.exists(path):
        return
    pub = json.load(open(path))
    meta = json.load(open(os.path.join(HERE, "repos.json")))["repos"]
    fresh = sd.build(os.path.join(HERE, pub["results"]), meta)
    for a, b in zip(pub["repos"], fresh["repos"]):
        assert a["full"] == b["full"], a["name"]
    assert pub["tally"] == fresh["tally"]
