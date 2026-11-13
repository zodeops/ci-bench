# ci-bench results: 2026-11-13

127 runs. Wall is dispatch to the last job done; queue is the longest job's GitHub queue time; run is the jobs' summed run time. Medians over the runs that passed (over all runs when none passed).

| Repo | Mode | GitHub wall | Zode wall | GitHub queue | Zode queue | GitHub run | Zode run | Passed (GitHub / Zode) |
|---|---|---|---|---|---|---|---|---|
| alpine | cold | 316s | 978.9s | 2s | 145s | 312s | 832s | 3/3 / 1/3 |
| alpine | warm | 326.3s | 961.3s | 2s | 69s | 323s | 829s | 3/3 / 3/3 |
| caddy | cold | 60s | 144.1s | 2s | 31s | 56s | 125s | 3/3 / 3/3 |
| caddy | warm | 83.4s | 143.4s | 3s | 2s | 79s | 120s | 3/3 / 3/3 |
| excalidraw | cold | 230.3s | 999.7s | 2s | 363s | 226s | 635s | 2/3 / 2/3 |
| excalidraw | warm | 295s | 751.2s | 2s | 138s | 291s | 666s | 3/3 / 3/3 |
| fzf | cold | 430.3s | 1079.5s | 2s | 383s | 426s | 694.5s | 3/3 / 2/3 |
| fzf | warm | 389.2s | 888.1s | 2s | 231.5s | 386s | 654.5s | 3/3 / 2/3 |
| helm | cold | 489.7s | 270.1s | 6s | 35.5s | 482s | 232.5s | 3/3 / 2/3 |
| helm | warm | 160.8s | 274.8s | 2s | 40s | 157s | 233s | 3/3 / 3/3 |
| httpx | cold | 47.3s | 658.3s | 2s | 554s | 180s | 1242s | 0/3 / 0/3 |
| httpx | warm | 46.3s | 243.3s | 2s | 103s | 196s | 1102s | 0/3 / 0/3 |
| jquery | cold | 59.6s | 799.4s | 2s | 677s | 170s | 475s | 3/3 / 1/3 |
| jquery | warm | 63.2s | 1132.2s | 2s | 997.5s | 177s | 477.5s | 3/3 / 2/3 |
| nginx-proxy | cold | 712.7s | 932.4s | 2s | 2s | 1388s | 1786s | 2/3 / 3/3 |
| nginx-proxy | warm | 704.4s | 933.8s | 2s | 25s | 1365s | 1829s | 2/3 / 3/3 |
| petclinic | cold | 113.8s | 165s | 2s | 34s | 110s | 129s | 3/3 / 3/3 |
| petclinic | warm | 103.4s | 172.7s | 2s | 41s | 99s | 130s | 3/3 / 3/3 |
| saleor | cold | 1164.2s | 2358.7s | 2s | 243s | 1160s | 2112s | 3/3 / 3/3 |
| saleor | warm | 997.9s | 2027.4s | 2s | 47s | 993s | 1978s | 3/3 / 3/3 |
| starlette | cold | 70.3s | 616.3s | 2s | 357s | 216.5s | 634s | 2/2 / 1/2 |
| starlette | warm | 63.3s | 1051.7s | 2.5s | 436s | 190.5s | 1140s | 2/2 / 0/1 |

## Zode phases (median ms over every job that ran)

| Mode | Jobs | webhook | dispatch | sandbox | runner_boot | assign | setup | steps | queue (p50 / p95) |
|---|---|---|---|---|---|---|---|---|---|
| cold | 66 | 2526.5 | 138206 | 24433 | 15963 | 902 | 4000 | 160000 | 99000 / 677000 |
| warm | 60 | 2584 | 180508 | 25618.5 | 16920 | 847 | 5000 | 150500 | 84500 / 507000 |

GitHub-hosted queue (created to started): cold median 2s, p95 3s over 66 jobs, warm median 2s, p95 3s over 66 jobs

REQ-050 check: 90 Zode jobs with every phase; 90 add up to GitHub's created-to-completed within 1 s (worst 0.004 s); 36 missing a phase; negative phases {'dispatch': 3}.
