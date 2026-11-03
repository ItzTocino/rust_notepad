# Requirements traceability

| Requirement | Policy/evidence | Milestone 1 disposition |
|---|---|---|
| 10,000,000,000-byte documents | `policy/milestones.json` | NOT_APPLICABLE: no document model |
| Peak RSS below 100,000,000 bytes | `policy/milestones.json` | NOT_APPLICABLE: no editor workload |
| Hot edit p99 below 1ms; 32 cursors | `policy/milestones.json` | NOT_APPLICABLE: no edit operation |
| Interactive frame p99 at most 16ms | `policy/milestones.json` | NOT_APPLICABLE: no frame harness |
| Cold random edit p99 at most 100ms | `policy/milestones.json` | NOT_APPLICABLE: no calibrated NVMe lab |
| 1M undo/redo; 10M adversarial ops | `policy/milestones.json` | NOT_APPLICABLE: neither feature exists |
| Build, lint and tests | PR workflow | Implemented; must run on provisioned self-hosted runner |
| Evidence fails closed | `scripts/verify_report.py` | Implemented and exercised by malformed report corpus |

Final latency qualification requires at least 100,000 samples in each of three independent runs, matching OS/hardware/compiler/fixture, warmup outside timed interval, observed p99 and one-sided 95% upper confidence bound under the limit. Statistical regression above 5% fails. Cold cache is reported separately. Compile time is excluded. No retry may turn a failed/flaky check green.

Future measurement lanes should store lossless samples, p50/p95/p99, confidence bounds, peak RSS including mapped resident pages, CPU/power/affinity calibration, fixture and source hashes, toolchain, runner identity and artifact links. Criterion is exploratory only; instruction-count tools, fuzzers, mutation testing and sanitizers are supplemental. Missing hardware/features remain NOT_APPLICABLE or INCONCLUSIVE, never PASS.

Public PR jobs require a disposable per-job VM. Performance and release jobs require a dedicated exclusive Windows host, separately labeled `perf-exclusive`; never run untrusted PR code on it. Configure branch protection to require correctness and detector checks, block skipped checks, and restrict trusted runner group access. This repository account lacks permission to inspect or configure Actions runners and has read-only repository access; an operator must provision/register the labels before jobs can execute.
