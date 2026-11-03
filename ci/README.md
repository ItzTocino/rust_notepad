# CI foundation

## Local commands

```powershell
cargo fmt --all -- --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked --all-targets
cargo build --locked --release
python ci/scripts/test_verifier.py
```

`rust-toolchain.toml` pins Rust 1.85.1 plus formatter and Clippy. `Cargo.lock` pins iced 0.13.1 and its dependency graph. The GUI smoke check is a successful release build; opening a native window needs an interactive desktop and is not claimed in headless CI.

## GitHub runners

All workflow jobs target self-hosted runners. Correctness and adversarial workflows require a disposable Windows x64 VM registered with labels `self-hosted`, `windows`, `x64`, `ephemeral`. Destroy it after every job and keep persistent credentials off it. Performance and release workflows require a separate, exclusive calibrated Windows host labeled `self-hosted`, `windows`, `x64`, `perf-exclusive`; it must not run alongside other workloads. Provision a Windows MSVC build environment, Rustup, Python 3, and the pinned toolchain. Workflows do not fall back to GitHub-hosted runners.

The repository is public. Do not expose persistent self-hosted runners to arbitrary PR code. Configure runner-group access and disposable per-job isolation. Protect `master` with required correctness and adversarial checks, require CODEOWNERS review for policy/workflow edits, block skipped required checks, and restrict who can dispatch performance/release workflows. Workflow tokens have `contents: read`; checkout disables credential persistence. Actions are pinned to full commit SHAs.

## Evidence and limitations

`verify_report.py` checks report fields, schema constraints, current commit, fixture and policy hashes, payload digest, mandatory checks, sample minima, calibration fields, and final performance thresholds. `test_verifier.py` uses throwaway temporary files and includes a valid positive control. A passing detector suite is not evidence of editor defect coverage: saved-byte corruption, Unicode boundaries, multi-cursor ordering, index errors, undo/journal recovery, frame stalls, real process RSS, cold-cache latency, crash recovery, and 10M operation corruption tests require the corresponding product features and workload harnesses.

The performance lane emits `NOT_APPLICABLE` at milestone 1. A future `PASS` requires three independent runs with at least 100,000 samples each, observed and one-sided 95% upper-bound p99 under each hard limit, matching hardware/OS/compiler/fixture, calibration checks, no synchronous UI-thread I/O, and no more than 5% instruction-count regression. No benchmark harness exists yet because the app has no edit/render workload contract. The current placeholder artifact is not a measurement.

Fuzzing (proptest/cargo-fuzz), mutation testing, Miri/sanitizers, Criterion/Iai-Callgrind, startup timing, packaging/provenance, large sparse fixtures, and release fault injection remain feature-gated. The aspiration of 50x defect detection per compute-hour is unproven because no comparable V0 held-out defect dataset exists.
