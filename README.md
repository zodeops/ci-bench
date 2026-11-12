# ci-bench

The repeatable benchmark every Zode CI speed task is measured against (PRD
REQ-050, task 35; the public page of REQ-062 grows from it). The same
workflow at the same commit runs on GitHub-hosted `ubuntu-latest` and on Zode
`zode-<size>`, cold and warm, 5 runs each, and every run is written as JSON.

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
- every other workflow file is removed, so nothing else runs.

Nothing else in the workflow changes. `git show HEAD` in a mirror is the
whole difference from upstream. Branches `main`, `bench-github` and
`bench-zode` point at the same commit. Each provider runs on its own branch,
so its Actions caches and concurrency group never meet the other provider's.

## Running it

```sh
scripts/bench.py                              # every repo, ubuntu-latest and zode-4x8, cold and warm, 5 runs
scripts/bench.py --repos helm,fzf --runs 1    # a quick check
scripts/report.py results/<date>              # summary.json and report.md
```

`cold` deletes the branch's Actions caches before the run; `warm` runs right
after, with what the cold run saved. Both providers run side by side for each
repository, iteration and mode. `--zode-jobs` (default 8) caps the Zode jobs
the harness keeps running at once, so real CI keeps room.

Zode runs need a Zode API token of the workspace that owns the zodeops GitHub
installation, in `$ZODE_TOKEN` or `~/.config/zode/ci-bench-token`; the
harness reads the job's phase timings from `GET /v1/ci/jobs`
(zoded `docs/ci-contract.md`, "Phases"). It never prints the token.

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

- `ubuntu-latest` on a public repository is 4 vCPUs and 16 GB; `zode-4x8` is
  4 vCPUs and 8 GB.
- Zode runs share the region with real CI. A full region shows up as the
  `dispatch` phase (waiting for room), not as runner time.
- No Zode warm snapshot exists yet (task 37), so on Zode warm differs from
  cold only by the Actions cache, as on GitHub.
