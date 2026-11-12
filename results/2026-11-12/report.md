# ci-bench results: 2026-11-12

202 runs. Wall is dispatch to the last job done; queue is the longest job's GitHub queue time; run is the jobs' summed run time. Medians over the runs that passed (over all runs when none passed).

| Repo | Mode | GitHub wall | Zode wall | GitHub queue | Zode queue | GitHub run | Zode run | Passed (GitHub / Zode) |
|---|---|---|---|---|---|---|---|---|
| alpine | cold | 306.5s | 840.9s | 2s | 21.5s | 302s | 816.5s | 5/5 / 2/5 |
| alpine | warm | 317.4s | 673.8s | 2s | 20s | 313s | 652s | 5/5 / 1/5 |
| caddy | cold | 110.5s | 217.9s | 2s | 49s | 106s | 120s | 5/5 / 3/3 |
| caddy | warm | 112.7s | 296.5s | 2s | 88s | 109s | 137s | 5/5 / 3/3 |
| excalidraw | cold | 242.8s | 481s | 1s | 25s | 239s | 463s | 5/5 / 3/5 |
| excalidraw | warm | 245.2s | 921.5s | 2s | 34s | 241s | 902s | 5/5 / 0/5 |
| fzf | cold | 436.3s | 719.2s | 2s | 26s | 431.5s | 669.5s | 6/6 / 4/5 |
| fzf | warm | 391.2s | 604.8s | 2s | 22.5s | 387s | 580s | 5/5 / 2/5 |
| helm | cold | 406.7s | 809.5s | 2s | 23s | 401s | 700s | 5/5 / 0/5 |
| helm | warm | 155.6s | 688.8s | 2s | 26s | 151s | 660s | 5/5 / 0/5 |
| httpx | cold | 47.1s | 259s | 3s | 161s | 189s | 705s | 0/5 / 0/3 |
| httpx | warm | 45.6s | 147.8s | 3s | 81s | 171s | 536s | 0/5 / 0/3 |
| jquery | cold | 60.5s | 354.1s | 2s | 230s | 176s | 461.5s | 5/5 / 2/3 |
| jquery | warm | 59.4s | 429.3s | 2s | 260s | 168s | 509s | 5/5 / 3/3 |
| nginx-proxy | cold | 701.8s | 811.6s | 2s | 27s | 1379s | 1204s | 5/5 / 0/5 |
| nginx-proxy | warm | 710.9s | 1504.8s | 2s | 26s | 1386s | 2860s | 5/5 / 0/5 |
| petclinic | cold | 111.4s | 297.9s | 2s | 109s | 105s | 234s | 5/5 / 3/3 |
| petclinic | warm | 93.9s | 222.2s | 2s | 28s | 87s | 192s | 5/5 / 3/3 |
| saleor | cold | 1018.1s | 2599.8s | 2s | 24.5s | 1015s | 2569.5s | 5/5 / 2/5 |
| saleor | warm | 988.4s | 2310.7s | 2s | 280s | 985s | 2028.5s | 5/5 / 2/5 |
| starlette | cold | 61.3s | 203.5s | 3s | 65s | 203s | 573.5s | 5/5 / 0/4 |
| starlette | warm | 68.8s | 220.7s | 3s | 93s | 179s | 633s | 5/5 / 0/3 |

## Zode phases (median ms over every job that ran)

| Mode | Jobs | webhook | dispatch | sandbox | runner_boot | assign | setup | steps | queue (p50 / p95) |
|---|---|---|---|---|---|---|---|---|---|
| cold | 92 | 3150.5 | 8 | 11793.5 | 12840.5 | 930.5 | 3000 | 128000 | 41000 / 465000 |
| warm | 86 | 3240 | 6 | 10530.5 | 12125 | 892 | 3000 | 161000 | 28000 / 348000 |

GitHub-hosted queue (created to started): cold median 2s, p95 3s over 121 jobs, warm median 2s, p95 5s over 120 jobs

REQ-050 check: 123 Zode jobs with every phase; 123 add up to GitHub's created-to-completed within 1 s (worst 0.004 s); 55 missing a phase; negative phases {'assign': 5}.
