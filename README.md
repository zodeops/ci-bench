# ci-bench

The public, repeatable CI benchmark behind [zode.dev/benchmark](https://zode.dev/benchmark),
and the one every Zode CI speed task is measured against (PRD REQ-050,
REQ-062). The same
workflow at the same commit runs on GitHub-hosted `ubuntu-24.04` and on Zode
`zode-<size>`, cold and warm, 5 runs each, and every run is written as JSON.

GitHub's `ubuntu-latest` moved to Ubuntu 26.04 by 12 Nov 2026 (fzf's pinned
Ruby has no 26.04 build there), while Zode's CI image is `ci-ubuntu-24.04`, so
the GitHub side runs `ubuntu-24.04`: same OS on both sides.

## The set (pinned 12 Nov 2026)

| Name | Upstream @ commit | Workflow | Kind | Jobs | Why |
|---|---|---|---|---|---|
| excalidraw | excalidraw/excalidraw @ 701b901a0f1b | test.yml | TypeScript | 1 | Yarn monorepo install plus Vitest, no cache: pure cold install |
| alpine | alpinejs/alpine @ da60871ea404 | run-tests.yml | JavaScript | 1 | Cypress browser end-to-end tests: browser system libraries |
| jquery | jquery/jquery @ feaa9fcdb68c | node.js.yml | JavaScript | 4 | Node version matrix with the setup-node npm cache; short jobs |
| starlette | encode/starlette @ 271c277da0ff | main.yml | Python | 6 | pytest on five Pythons with uv and its cache; sub-minute jobs |
| httpx | encode/httpx @ b5addb64f016 | test-suite.yml | Python | 5 | Plain pip install on five Pythons, lint, docs build, coverage gate |
| saleor | saleor/saleor @ ea4a69fa6faa | tests.yaml | Python | 1 | The suite over 10 minutes (about 17): Django pytest in a `container:` job with Postgres and Valkey services |
| fzf | junegunn/fzf @ 4499615fe9c0 | linux.yml | Go | 1 | Go plus Ruby, apt packages and tmux integration tests |
| helm | helm/helm @ 6234f6228f31 | build-test.yml | Go | 1 | One Go job of about 5 minutes with the setup-go cache |
| nginx-proxy | nginx-proxy/nginx-proxy @ bff2cddfece8 | test.yml | Docker | 2 | Docker-heavy: image builds and docker compose tests, about 11 minutes |
| petclinic | spring-projects/spring-petclinic @ 500158f73241 | maven-build.yml | Java | 1 | Maven with the setup-java cache; Testcontainers needs Docker |
| caddy | caddyserver/caddy @ v2.8.4 | bench.yml (this repo) | Go | 1 | The first side-by-side build (50 s on zode-4x8, 82 s on ubuntu-latest, 12 Nov 2026) |

The full list with reasons is `repos.json`. Rejected on the way: caddy's own
`ci.yml` (its macOS and Windows legs would all land on Linux and collide on
artifact names), opentofu and netbox (every test job hangs off a
changed-files job and skips under a manual trigger), golang-migrate (a
Coveralls upload that fails on a mirror, and 6 of its last 8 runs failed).

## How a repository is mirrored

`scripts/mirror.sh <name>` makes `zodeops/bench-<name>` (public, so
GitHub-hosted minutes are free) with two commits: the upstream tree unchanged,
then the bench edit made by `scripts/benchify.py`:

- every `runs-on:` becomes `${{ inputs.runner }}`;
- the trigger becomes `workflow_dispatch` with a `runner` input;
- every other workflow file is removed, so nothing else runs;
- a build that runs `git describe` gets the upstream release tag on the
  unchanged tree (`tag` in `repos.json`; fzf).

Nothing else in the workflow changes. `git show HEAD` in a mirror is the
whole difference from upstream. Branches `main`, `bench-github` and
`bench-zode` point at the same commit. Each provider runs on its own branch,
so its Actions caches and concurrency group never meet the other provider's.

## Running it

```sh
scripts/bench.py                              # every repo, ubuntu-24.04 and zode-4x8, cold and warm, 5 runs
scripts/bench.py --repos helm,fzf --runs 1    # a quick check
scripts/bench.py --resume --split saleor      # skip recorded runs; saleor's iterations run at once
scripts/report.py results/<date>              # summary.json and report.md
scripts/phase-check.py --since <time>         # REQ-050: stored phases vs GitHub's own job times
```

`--split` runs a repository's iterations at the same time, each on its own
branch (`bench-zode-i3`), so a 17-minute suite does not take 3 hours. The
harness polls once a minute and waits out GitHub's API rate limit (one user
token, 5,000 calls an hour, shared with every other tool). When Zode marks a
job `failed` or `refused`, the harness cancels the GitHub run at once and
records `zode_failed` with Zode's reason.

`cold` deletes the branch's Actions caches before the run; `warm` runs right
after, with what the cold run saved. Both providers run side by side for each
repository, iteration and mode. `--zode-jobs` (default 8) caps the Zode jobs
the harness keeps running at once, so real CI keeps room.

Zode runs need a Zode API token of the workspace that owns the zodeops GitHub
installation, in `$ZODE_TOKEN` or `~/.config/zode/ci-bench-token`; the
harness reads the job's phase timings from `GET /v1/ci/jobs`
(zoded `docs/ci-contract.md`, "Phases"). It never prints the token.

## Every week

`.github/workflows/weekly.yml` runs the whole set every Sunday at 02:00 UTC
(and on demand: Actions, weekly, Run workflow), 3 runs per provider and mode,
one matrix job per repository, four repositories at a time and two Zode jobs
per repository, so the benchmark never holds more than eight Zode runners.
The last job concatenates the runs into `results/<date>/runs.jsonl`, writes
`report.md` and `summary.json` (`scripts/report.py`) and the page data
(`scripts/site-data.py`, into `results/<date>/site.json` and `site/ci.json`),
and commits them to `main`. zode.dev/benchmark reads `site/ci.json` from
this repository, so the page follows the newest week without a deploy.
`site/index.json` lists every published week.

`scripts/site-data.py` picks, for each repository, provider and mode, the
median run by wall time (the lower middle one when the count is even) and
shows that run's own wall, queue, run time and price with its link, so every
number on the page is one real run. Runs that passed come first; a cell with
no passed run says so. GitHub's price is the list price of the same machine
for a private repository (Linux 4-core larger runner, $0.012 a minute, each
job rounded up to the minute; public repositories run free). Zode's is what
the run was billed, from the Zode API; when a job ran on a runner started
for another run its bill sits there, and the cell shows an estimate from
run time at $0.045 an hour instead.

Selected-test runs and sharded runs are separate columns on the page and
stay pending until Enforce (task 43) and the shard proof (task 41) exist:
every run here is the full suite on one machine.

Secrets for the weekly job: `BENCH_GH_TOKEN` (a GitHub token with Actions
write and contents write on the `zodeops/bench-*` mirrors and this
repository) and `ZODE_TOKEN`.

`tests/` checks the page data against the runs it came from; it runs on Zode
with the sample workflow from the docs (`.github/workflows/test.yml`).

## Other providers

`PROVIDERS.md`: whose terms allow publishing, who is run, and every other
provider's own claims, cited as self-reported with links.

## Rerun one repository yourself

```sh
git clone https://github.com/zodeops/ci-bench && cd ci-bench
export BENCH_OWNER=<your GitHub account>
scripts/mirror.sh helm                      # your own public mirror, <you>/bench-helm
scripts/bench.py --repos helm --runners ubuntu-24.04 --runs 3 --out results/mine
scripts/site-data.py results/mine
```

GitHub-hosted runs need only `gh`. Zode runs need a Zode workspace with the
Zode GitHub App on the mirror and its token in `ZODE_TOKEN`. The published
median should land within 15% of yours.

## Output

`results/<date>/runs.jsonl`, one record per run, the same shape for every
provider:

```json
{"schema":1,"repo":"helm","upstream":"helm/helm","commit":"6234f622...","mirror":"zodeops/bench-helm",
 "workflow":"build-test.yml","branch":"bench-zode","provider":"zode","runner":"zode-4x8",
 "mode":"cold","iteration":1,"caches_deleted":3,"run_id":43196065314,"run_url":"...",
 "conclusion":"success","dispatched_at":"...","first_job_created_at":"...","completed_at":"...",
 "wall_s":301.2,"queue_s_max":14.0,"run_s_sum":280.0,
 "jobs":[{"id":131104910181,"name":"build","conclusion":"success","labels":["zode-4x8"],
   "runner_name":"zode-...","created_at":"...","started_at":"...","completed_at":"...",
   "queue_s":14.0,"run_s":280.0,
   "steps":[{"number":1,"name":"Set up job","conclusion":"success","started_at":"...","completed_at":"...","s":1.0}],
   "zode":{"id":"cij_...","size":"4x8","status":"completed","cache_hit":false,"cost_micros":5833,
     "cost_final":true,"phases":{"...":"..."},"phase_ms":{"...":"..."}}}]}
```

`zode` is null for GitHub-hosted jobs. `wall_s` is dispatch to the last job
done; `queue_s_max` is the longest job's GitHub queue time (created to
started); `run_s_sum` is the jobs' summed run time.

## Caveats

- `ubuntu-24.04` on a public repository is 4 vCPUs and 16 GB; `zode-4x8` is
  4 vCPUs and 8 GB.
- Zode runs share the region with real CI. A full region shows up as the
  `dispatch` phase (waiting for room), not as runner time.
- No Zode warm snapshot exists yet (task 37), so on Zode warm differs from
  cold only by the Actions cache, as on GitHub.
