# ci-bench results: 2026-11-13-quiet

132 runs. Wall is dispatch to the last job done; queue is the longest job's GitHub queue time; run is the jobs' summed run time. Medians over the runs that passed (over all runs when none passed).

| Repo | Mode | GitHub wall | Zode wall | GitHub queue | Zode queue | GitHub run | Zode run | Passed (GitHub / Zode) |
|---|---|---|---|---|---|---|---|---|
| alpine | cold | 308.2s | 910.3s | 2s | 230s | 304s | 689s | 3/3 / 3/3 |
| alpine | warm | 324.5s | 894.7s | 2s | 41s | 320s | 860s | 3/3 / 3/3 |
| caddy | cold | 79.9s | 161.9s | 3s | 25s | 75s | 131s | 3/3 / 3/3 |
| caddy | warm | 81.6s | 149.6s | 2s | 25s | 77s | 122s | 3/3 / 3/3 |
| excalidraw | cold | 226.2s | 570.7s | 2s | 34s | 222s | 538s | 3/3 / 3/3 |
| excalidraw | warm | 201.4s | 610.7s | 2s | 28s | 198s | 580.5s | 3/3 / 2/3 |
| fzf | cold | 438.3s | 586.1s | 4s | 34s | 432s | 550s | 3/3 / 1/3 |
| fzf | warm | 402.5s | 641.8s | 2s | 36s | 398s | 604s | 3/3 / 2/3 |
| helm | cold | 398.9s | 1093.6s | 2s | 64s | 393s | 971s | 3/3 / 3/3 |
| helm | warm | 152.3s | 437.3s | 2s | 38s | 148s | 394s | 3/3 / 3/3 |
| httpx | cold | 47.3s | 107.2s | 3s | 34s | 198s | 438s | 0/3 / 0/3 |
| httpx | warm | 48.2s | 104.2s | 3s | 30s | 193s | 406s | 0/3 / 0/3 |
| jquery | cold | 63.4s | 145.5s | 2s | 36s | 182s | 388s | 3/3 / 3/3 |
| jquery | warm | 60.2s | 123.2s | 3s | 33s | 181s | 368s | 3/3 / 3/3 |
| nginx-proxy | cold | 717.5s | 1058.5s | 2s | 35s | 1398s | 1993s | 3/3 / 3/3 |
| nginx-proxy | warm | 676.7s | 1126.6s | 2s | 45s | 1328s | 2149s | 2/3 / 3/3 |
| petclinic | cold | 117.3s | 206.1s | 2s | 41s | 113s | 162s | 3/3 / 3/3 |
| petclinic | warm | 106.3s | 199.2s | 2s | 40s | 102s | 157s | 3/3 / 3/3 |
| saleor | cold | 1069s | 2198.6s | 2s | 36s | 1064s | 2160s | 3/3 / 3/3 |
| saleor | warm | 812.5s | 1859s | 3s | 38s | 807s | 1812s | 3/3 / 3/3 |
| starlette | cold | 65s | 150.9s | 4s | 28s | 226s | 475s | 3/3 / 3/3 |
| starlette | warm | 59.2s | 148s | 3s | 27s | 188s | 453s | 3/3 / 3/3 |

## Zode phases (median ms over every job that ran)

| Mode | Jobs | webhook | dispatch | sandbox | runner_boot | assign | setup | steps | queue (p50 / p95) |
|---|---|---|---|---|---|---|---|---|---|
| cold | 72 | 2542.5 | 35.5 | 18840 | 10475 | 836 | 3000 | 109500 | 29500 / 79000 |
| warm | 72 | 2521.5 | 24 | 19106 | 9781 | 892 | 3000 | 98500 | 26500 / 45000 |

GitHub-hosted queue (created to started): cold median 2s, p95 14s over 72 jobs, warm median 2s, p95 3s over 72 jobs

REQ-050 check: 79 Zode jobs with every phase; 79 add up to GitHub's created-to-completed within 1 s (worst 0.004 s); 65 missing a phase; negative phases {'dispatch': 13}.
