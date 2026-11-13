# Other providers and their terms

Read 13 Nov 2026 (PRD REQ-062, Q9: publish only where a provider's terms
allow it; otherwise cite the provider's own table as self-reported). This is
a reading of public terms, not legal advice; an enterprise contract can say
something else.

## What ci-bench runs and publishes

| Provider | Terms read | Benchmark clause | Verdict | On the page |
|---|---|---|---|---|
| GitHub-hosted | [Terms for Additional Products and Features](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features) (effective 27 Aug 2026), "Competitive Benchmarking" | Benchmarking is allowed when the benchmarker waives any benchmark restriction on its own product toward GitHub | Allowed: [Zode's terms](https://zode.dev/terms) have no benchmark restriction | Run every week |
| Zode | [zode.dev/terms](https://zode.dev/terms) | None | Allowed | Run every week |
| Graphide | [Terms](https://graphide.com/terms) v2.1 (30 Oct 2026): none. [License](https://graphide.com/license), Draft 0.1, section 3: no use "to benchmark it for publication, without our prior written consent", marked "Draft, pending review by counsel. Not yet in force" | Draft clause against publishing benchmarks of its software | Not run: the clause is not in force, but it states Graphide's intent, and ci-bench has no account there | Self-reported, cited |
| Blacksmith | [Terms](https://docs.blacksmith.sh/about/terms-of-service) (effective 20 Jul 2026), section 3 | None (no security tests, no load that degrades the service) | Allowed | Not run yet (no account); self-reported, cited |
| Depot | [Terms](https://depot.dev/terms-of-service) (effective 27 Jun 2025), F.2 | None (beta features are confidential) | Allowed | Not run yet (no account); self-reported, cited |
| Namespace | [Terms](https://namespace.so/terms) (valid from 31 Aug 2024), sections 4 and 6 | None, but section 4 limits use to "your own internal, personal, non-commercial use" | Unclear | Not run; self-reported, cited |
| Ubicloud | [Terms](https://www.ubicloud.com/docs/about/terms-of-service), section 5.4 | None (no reverse engineering) | Allowed | Not run yet (no account); self-reported, cited |
| WarpBuild | [Terms](https://www.warpbuild.com/legal/terms) (30 Sep 2026), section 9 | None by name; bars using the service "to compete with" its owner | Unclear for a competitor | Not run; self-reported, cited |
| RunsOn | [License](https://runs-on.com/legal/license/) (effective 5 Jun 2026), sections 9 and 10 | None; its own [benchmark data](https://runs-on.com/benchmarks/) is CC BY 4.0 | Allowed | Not run yet (it runs in your own AWS account); self-reported, cited |
| BuildJet | [Terms](https://buildjet.com/for-github-actions/docs/about/terms-of-service) | None | Closed its runners on 31 Mar 2026 ([post](https://buildjet.com/for-github-actions/blog/we-are-shutting-down)) | Left out |
| Cirrus Runners | Terms link 404s | Unverified | [No new customers](https://cirruslabs.org/) | Left out |

"Not run yet (no account)" means the terms would let ci-bench publish, but
running a provider needs an account and its own billing, which this
benchmark does not have yet. Adding one is a runner label: the harness
dispatches any label, and `provider_of` in `scripts/bench.py` maps it to a
provider name.

## Their own numbers (self-reported, not measured here)

| Provider | Claim | Source |
|---|---|---|
| Graphide | "CI 10-20x faster than GitHub-hosted runners"; its table of 10 open-source repositories shows 11.3x to 50x. It gets there by skipping tests a change cannot reach, so it is a different measure from full-suite time on the same hardware | [graphide.com](https://graphide.com) |
| Blacksmith | "2x faster hardware", "costs 60% less than GitHub runners" | [blacksmith.sh](https://www.blacksmith.sh) |
| Depot | "up to 10x faster"; grpc 5.9x, kafka 2.3x, zed 2.0x (baseline runner not stated) | [depot.dev](https://depot.dev/products/github-actions) |
| Namespace | A demo run in 4 min 56 s against 9 min 52 s on GitHub-hosted | [namespace.so](https://namespace.so/github-actions) |
| Ubicloud | "Go twice as fast", "85% lower cost than GitHub-hosted runners" | [ubicloud.com](https://www.ubicloud.com/use-cases/github-actions) |
| WarpBuild | "2x faster, 50% cheaper" | [warpbuild.com](https://www.warpbuild.com) |
| RunsOn | Builds 2.0x to 2.6x faster; Docker 4 min 57 s against 12 min 53 s | [runs-on.com/benchmarks](https://runs-on.com/benchmarks/) |

## GitHub's prices and machines used on the page

- `ubuntu-24.04` on a public repository: 4 vCPU, 16 GB RAM, 14 GB SSD; on
  a private one 2 vCPU, 8 GB
  ([runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)).
- Linux x64 2-core $0.006 a minute, 4-core larger runner $0.012 a minute
  ([pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing),
  after the [1 Jan 2026 cut](https://github.blog/changelog/2026-01-01-reduced-pricing-for-github-hosted-runners-usage/)).
  The page prices GitHub's runs at the 4-core rate, the same machine the
  public run used.
- The announced $0.002 a minute charge for self-hosted runners (which would
  apply to Zode runners on private repositories) is postponed with no date
  ([changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/));
  the page leaves it out and will add it if it starts.
