#!/usr/bin/env python3
"""Throwaway evidence corpus: baseline plus targeted malformed reports."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "ci/fixtures/baseline.json"
VERIFIER = ROOT / "ci/scripts/verify_report.py"
CHECKS = json.loads((ROOT / "ci/policy/required-checks.json").read_text())["checks"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


POLICY_SHA = digest((ROOT / "ci/policy/milestones.json").read_bytes() + (ROOT / "ci/policy/required-checks.json").read_bytes())


def main():
    good = {
        "schema_version": 1, "lane": "correctness", "status": "PASS",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "fixture_sha256": digest(FIXTURE.read_bytes()), "policy_sha256": POLICY_SHA, "runner": "isolated-test-runner",
        "toolchain": "test toolchain", "sample_count": len(CHECKS),
        "artifact_sha256": digest(b"payload"), "reason": "positive control",
        "metrics": {"checks": CHECKS}
    }
    perf_metrics = {
        "hot_edit_p99_ms": 0.8, "hot_edit_upper_95_p99_ms": 0.9,
        "multi_cursor_edit_p99_ms": 0.8, "multi_cursor_edit_upper_95_p99_ms": 0.9,
        "frame_p99_ms": 12.0, "frame_upper_95_p99_ms": 14.0,
        "cold_edit_p99_ms": 80.0, "cold_edit_upper_95_p99_ms": 90.0,
        "peak_rss_bytes": 90_000_000, "instruction_count_regression_percent": 2.0,
        "p50_ms": 0.2, "p95_ms": 0.6, "independent_runs": 3,
        "run_sample_counts": [100_000, 100_000, 100_000], "multi_cursor_count": 32,
        "cpu_calibrated": True, "power_calibrated": True, "affinity_verified": True,
        "matching_hardware_os_fixture_compiler": True, "ui_thread_sync_io": False,
        "confidence_method": "one_sided_95_percent", "raw_samples_sha256": digest(b"payload")
    }
    perf_good = {**good, "lane": "performance", "sample_count": 300_000, "metrics": perf_metrics}
    release_metrics = {"fixture_bytes": 10_000_000_000, "undo_redo_transactions": 1_000_000,
                       "adversarial_operations": 10_000_000, "peak_rss_bytes": 90_000_000,
                       "crash_recovery_verified": True, "byte_exact_10gb_fixture": True,
                       "provenance_verified": True}
    release_good = {**good, "lane": "release", "metrics": release_metrics}
    cases = {
        "positive control": (good, b"payload", True),
        "calibrated performance control": (perf_good, b"payload", True),
        "release qualification control": (release_good, b"payload", True),
        "missing sample count": ({k: v for k, v in good.items() if k != "sample_count"}, b"payload", False),
        "stale SHA": ({**good, "commit": "0" * 40}, b"payload", False),
        "wrong fixture": ({**good, "fixture_sha256": "0" * 64}, b"payload", False),
        "forged artifact": ({**good, "artifact_sha256": "0" * 64}, b"payload", False),
        "empty PASS report": ({**good, "sample_count": 0}, b"payload", False),
        "performance with insufficient samples": ({**good, "lane": "performance", "sample_count": 99_999, "metrics": {}}, b"payload", False),
        "slow edit p99": ({**perf_good, "metrics": {**perf_metrics, "hot_edit_p99_ms": 2.0}}, b"payload", False),
        "slow frame": ({**perf_good, "metrics": {**perf_metrics, "frame_p99_ms": 18.0}}, b"payload", False),
        "excess RSS": ({**perf_good, "metrics": {**perf_metrics, "peak_rss_bytes": 200_000_000}}, b"payload", False),
        "UI synchronous I/O": ({**perf_good, "metrics": {**perf_metrics, "ui_thread_sync_io": True}}, b"payload", False),
        "instruction regression": ({**perf_good, "metrics": {**perf_metrics, "instruction_count_regression_percent": 6.0}}, b"payload", False),
        "lost undo transaction": ({**release_good, "metrics": {**release_metrics, "undo_redo_transactions": 999_999}}, b"payload", False),
        "skipped mandatory check": ({**good, "metrics": {"checks": CHECKS[:-1]}}, b"payload", False),
        "flaky retry laundering": ({**good, "metrics": {"checks": CHECKS, "retry_result": "PASS"}}, b"payload", False),
        "protected threshold edit": ({**good, "policy_sha256": "0" * 64}, b"payload", False),
        "wrong schema": ({**good, "schema_version": 99}, b"payload", False),
        "missing report": (None, b"payload", False),
        "truncated report": ("{", b"payload", False),
        "stale fixture artifact": (good, b"tampered", False),
    }
    failures = 0
    with tempfile.TemporaryDirectory(prefix="ci-redteam-") as temp:
        base = Path(temp)
        (base / "artifacts").mkdir()
        for name, (report, payload, expected) in cases.items():
            (base / "artifacts/payload.bin").write_bytes(payload)
            path = base / "report.json"
            if report is None:
                path.unlink(missing_ok=True)
            elif isinstance(report, str):
                path.write_text(report)
            else:
                path.write_text(json.dumps(report))
            result = subprocess.run([sys.executable, str(VERIFIER), str(path)], cwd=ROOT, capture_output=True, text=True)
            detected = result.returncode != 0
            passed = detected is (not expected)
            print(f"{'PASS' if passed else 'FAIL'} {name}: expected_accept={expected}, got_accept={not detected}; {result.stdout.strip() or result.stderr.strip()}")
            failures += not passed
    if failures:
        raise SystemExit(1)
    print(f"RED->GREEN detector suite: {len(cases)} cases, 1 positive control accepted, {len(cases)-1} defects rejected")


if __name__ == "__main__":
    main()
