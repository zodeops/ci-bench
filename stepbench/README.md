# stepbench: why a Zode step takes about 2x GitHub's

The 13 Nov acceptance run found Zode about 2x slower than GitHub-hosted at
running the same steps, and gave three possible causes without separating
them: nested virtualisation, CPU overcommit, egress. `stepbench.sh` splits a
step into the costs each of those hits differently and runs in three places:

- GitHub `ubuntu-24.04`, 5 jobs (run 43501951176)
- Zode `zode-4x8`, 5 jobs in the same run, 13 Nov ~20:29 UTC, with the
  12-node fleet almost idle (load under 1 on 9 of the 10 new nodes before the run)
- The node host itself (eu-6, eu-11), pinned to 4 CPUs with `taskset`: the
  same GCE `n2-standard-16` with no nested VM in the way

Raw lines are in `results-2026-11-13/`, and `table.py` prints the table.

## Medians

| Test | GitHub | Node host (L1) | Zode VM, quietest (#4) | Zode VM, other 4 |
|---|---|---|---|---|
| CPU | EPYC 9V45 / Xeon 6975P / EPYC 7763 | Xeon @ 2.80GHz (Cascade Lake) | same | same |
| Python loop, s | 1.2 | 1.9 to 3.3 | 1.9 | 3.4 to 4.1 |
| sha256 single thread, MB/s | 1,860 to 2,020 | 407 to 435 | 390 | 362 to 417 |
| 2 GB first touch (page faults), s | 0.7 to 1.4 | 1.0 to 1.2 | 12.8 | 12.5 to 14.0 (1.6 on #5) |
| fork+exec x2000, s | 0.9 to 1.5 | 1.3 to 1.6 | 3.1 | 3.2 to 4.3 |
| syscall, ns | 169 to 418 | 200 to 393 | 225 | 430 to 630 |
| Go `build -a std`, s | 12.5 to 19.9 | 11.9 to 15.0 | 15.1 | 17.8 to 23.4 |
| 30k small files, s | 1.0 to 3.2 | 1.6 to 2.1 | 2.3 | 3.1 to 4.1 |
| 2 GB sequential write, s | 5.5 to 11.6 | 12.6 to 12.8 | 3.2 | 3.6 to 6.5 |
| 78 MB from dl.google.com, s | 0.4 to 1.6 | 0.2 to 0.3 | 0.5 | 0.4 to 1.0 |
| steal ticks during the run | 0 | 0 | 101 | 170 to 1,012 |
| whole script, s | 43 to 52 | 49 to 55 | 58 | 65 to 72 |

## What it says

1. **Nested paging is the biggest single cost.** First touch of new memory
   is about 12x slower in a Zode VM than on its own host (12.8 s against
   1.0 s for 2 GB, about 24 us per 4 KB fault against 2 us). fork+exec is
   2.5x slower for the same reason: every new process faults in fresh pages.
   Test runners (pytest-xdist and Jest workers, `go test` binaries, shell
   loops) do exactly this all the time. Job #5 faulted in 2 GB in 1.6 s; it
   most likely ran on a standby whose guest RAM had been pre-faulted, which
   points at the fix: a page that is already mapped through both EPT layers
   costs nothing extra. Plain compute in the VM is not slower: the
   quietest VM's Python loop (1.9 s) equals the host's.
2. **The CPUs are a generation or more behind.** GitHub's 4-vCPU runners
   landed on AMD EPYC 9V45 (Zen 5), Xeon 6975P (Granite Rapids) and EPYC
   7763 (Zen 3). `n2-standard-16` gives a 2019 Cascade Lake: 1.6x slower on
   single-thread interpreter work and 4.7x slower on SHA-256 (no SHA-NI;
   it hits git, npm/pip integrity checks and Docker layer digests).
3. **Contention doubles it again, even on an idle fleet.** 4 of 5 Zode jobs
   ran the Python loop in 3.4 to 4.1 s against 1.9 s on the quiet one, with
   up to 10 s of steal. Placement is a random draw weighted by free RAM
   only (`internal/cp/scheduler/scheduler.go` Pick); it ignores CPU, so a
   run's jobs and standbys land together (6 VMs each on eu-3/7/9/10 during
   this run while most nodes held 2). A full node is 7 x 4 vCPU = 28 vCPUs on
   16 hyperthreads (8 cores).
4. **Not the cause: network egress and disk.** Downloads from Google's CDN and
   PyPI take the same time on both sides. Zode's ZFS disk is faster than
   GitHub's for sequential writes and about even for small files. (The slow
   Actions cache restore in REQ-054 is a different path. The VM config shows
   virtio-net with checksum and TSO offload off, and one disk queue, both
   worth testing there.)

## Levers, in order of size

- Get rid of the second paging layer. Bare metal (PRD D1: a leased EU node)
  removes nested EPT entirely. Inside GCP, a `-metal` machine type would
  do the same; check availability and price first.
- Until then, back guest RAM with huge pages (`memory.hugepages` is false in
  the VM config today), so the nested layer maps 2 MB at a time instead of
  4 KB. This is untested here and needs a drill on an idle node.
- A current CPU generation: Zen 4/5 or Sapphire Rapids and later, with SHA-NI.
- Place CI by CPU, not only RAM: spread a run's jobs across idle nodes and cap
  vCPU overcommit for CI sizes.
