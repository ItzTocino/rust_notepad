#!/usr/bin/env python3
"""Independent fail-closed evidence verifier; candidate report is untrusted input."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "ci/fixtures/baseline.json"
SCHEMA = ROOT / "ci/schemas/report.schema.json"
REQUIRED = ROOT / "ci/policy/required-checks.json"
POLICY = ROOT / "ci/policy/milestones.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(report_path):
    report_path = Path(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        return False, ["report must be a JSON object"]
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    required = schema["required"]
    errors = [f"missing field: {key}" for key in required if key not in report]
    errors += [f"unexpected field: {key}" for key in report if key not in props]
    for key in ("schema_version", "lane", "status"):
        if key in report and report[key] not in props[key].get("enum", [props[key].get("const")]):
            errors.append(f"invalid {key}")
    for key in ("commit", "fixture_sha256", "policy_sha256", "artifact_sha256"):
        pattern = props.get(key, {}).get("pattern")
        if key in report and not re.fullmatch(pattern or r"(?!)", str(report[key])):
            errors.append(f"invalid {key}")
    for key in ("runner", "toolchain", "reason"):
        if key in report and (not isinstance(report[key], str) or not report[key]):
            errors.append(f"invalid {key}")
    if "sample_count" in report and (type(report["sample_count"]) is not int or report["sample_count"] < 0):
        errors.append("invalid sample_count")
    if "metrics" in report and not isinstance(report["metrics"], dict):
        errors.append("metrics must be an object")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if report.get("commit") != head:
        errors.append("stale or wrong commit")
    if report.get("fixture_sha256") != sha256(FIXTURE):
        errors.append("wrong fixture hash")
    expected_policy = hashlib.sha256(POLICY.read_bytes() + REQUIRED.read_bytes()).hexdigest()
    if report.get("policy_sha256") != expected_policy:
        errors.append("wrong or stale policy hash")
    artifacts = report_path.parent / "artifacts"
    artifact = artifacts / "payload.bin"
    if not artifact.is_file() or report.get("artifact_sha256") != sha256(artifact):
        errors.append("missing or forged artifact")
    if report.get("status") == "PASS" and report.get("lane") != "correctness" and report.get("sample_count", 0) < 1:
        errors.append("PASS requires samples")
    if report.get("lane") == "performance" and report.get("status") == "PASS":
        metrics = report.get("metrics", {})
        if report.get("sample_count", 0) < 300_000 or metrics.get("independent_runs") != 3 or metrics.get("run_sample_counts") != [100_000, 100_000, 100_000]:
            errors.append("performance PASS requires three independent runs with at least 100,000 samples each")
        numeric_limits = {"hot_edit_p99_ms": 1.0, "hot_edit_upper_95_p99_ms": 1.0, "frame_p99_ms": 16.0,
                          "frame_upper_95_p99_ms": 16.0, "cold_edit_p99_ms": 100.0,
                          "cold_edit_upper_95_p99_ms": 100.0, "peak_rss_bytes": 100_000_000,
                          "instruction_count_regression_percent": 5.0}
        for key, limit in numeric_limits.items():
            value = metrics.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value > limit:
                errors.append(f"performance metric {key} missing or over limit {limit}")
        required_metrics = tuple(numeric_limits) + ("p50_ms", "p95_ms", "independent_runs", "run_sample_counts",
                                                    "cpu_calibrated", "power_calibrated", "affinity_verified",
                                                    "matching_hardware_os_fixture_compiler", "ui_thread_sync_io")
        if not all(key in metrics for key in required_metrics):
            errors.append("performance PASS is missing required calibrated metrics")
        for key in ("cpu_calibrated", "power_calibrated", "affinity_verified", "matching_hardware_os_fixture_compiler"):
            if metrics.get(key) is not True:
                errors.append(f"performance calibration failed: {key}")
        if metrics.get("ui_thread_sync_io") is not False:
            errors.append("UI-thread synchronous I/O detected or unknown")
    expected = json.loads(REQUIRED.read_text(encoding="utf-8"))["checks"]
    if report.get("lane") == "correctness":
        checks = report.get("metrics", {}).get("checks", [])
        if checks != expected:
            errors.append("mandatory checks missing, skipped, reordered, or duplicated")
        if report.get("sample_count") != len(expected):
            errors.append("correctness PASS requires one record for every mandatory check")
        if any("retry" in str(key).lower() for key in report.get("metrics", {})):
            errors.append("retry metadata cannot mask a flaky failure")
    if report.get("status") in ("FAIL", "INCONCLUSIVE"):
        errors.append(f"evidence status is {report['status']}")
    if errors:
        return False, errors
    return True, [f"verified {report['status']} evidence for {report['lane']}"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    args = parser.parse_args()
    try:
        ok, messages = verify(args.report)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        ok, messages = False, [f"invalid evidence: {exc}"]
    for message in messages:
        print(("PASS: " if ok else "FAIL: ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
