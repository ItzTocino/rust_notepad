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
        run_counts = metrics.get("run_sample_counts")
        if (report.get("sample_count", 0) < 300_000 or metrics.get("independent_runs") != 3
                or not isinstance(run_counts, list) or len(run_counts) != 3
                or any(type(n) is not int or n < 100_000 for n in run_counts)):
            errors.append("performance PASS requires three independent runs with at least 100,000 samples each")
        numeric_limits = {"hot_edit_p99_ms": (1.0, True), "hot_edit_upper_95_p99_ms": (1.0, True),
                          "multi_cursor_edit_p99_ms": (1.0, True), "multi_cursor_edit_upper_95_p99_ms": (1.0, True),
                          "frame_p99_ms": (16.0, False), "frame_upper_95_p99_ms": (16.0, False),
                          "cold_edit_p99_ms": (100.0, False), "cold_edit_upper_95_p99_ms": (100.0, False),
                          "peak_rss_bytes": (100_000_000, True), "instruction_count_regression_percent": (5.0, False)}
        for key, (limit, strict) in numeric_limits.items():
            value = metrics.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value > limit or (strict and value == limit):
                errors.append(f"performance metric {key} missing or over limit {limit}")
        required_metrics = tuple(numeric_limits) + ("p50_ms", "p95_ms", "independent_runs", "run_sample_counts", "multi_cursor_count",
                                                    "cpu_calibrated", "power_calibrated", "affinity_verified",
                                                    "matching_hardware_os_fixture_compiler", "ui_thread_sync_io",
                                                    "confidence_method", "raw_samples_sha256")
        if not all(key in metrics for key in required_metrics):
            errors.append("performance PASS is missing required calibrated metrics")
        for key in ("cpu_calibrated", "power_calibrated", "affinity_verified", "matching_hardware_os_fixture_compiler"):
            if metrics.get(key) is not True:
                errors.append(f"performance calibration failed: {key}")
        if metrics.get("ui_thread_sync_io") is not False:
            errors.append("UI-thread synchronous I/O detected or unknown")
        if metrics.get("multi_cursor_count") != 32:
            errors.append("performance qualification must include exactly 32 cursors")
        if metrics.get("confidence_method") != "one_sided_95_percent":
            errors.append("performance confidence method must be one-sided 95 percent")
        if not re.fullmatch(r"[0-9a-f]{64}", str(metrics.get("raw_samples_sha256", ""))):
            errors.append("performance report is missing the raw sample artifact hash")
        if not artifact.is_file() or metrics.get("raw_samples_sha256") != sha256(artifact):
            errors.append("raw sample artifact hash does not match retained artifact")
        for observed_key, upper_key in (("hot_edit_p99_ms", "hot_edit_upper_95_p99_ms"),
                                        ("multi_cursor_edit_p99_ms", "multi_cursor_edit_upper_95_p99_ms"),
                                        ("frame_p99_ms", "frame_upper_95_p99_ms"),
                                        ("cold_edit_p99_ms", "cold_edit_upper_95_p99_ms")):
            observed, upper = metrics.get(observed_key), metrics.get(upper_key)
            if isinstance(observed, (int, float)) and isinstance(upper, (int, float)) and upper < observed:
                errors.append(f"confidence bound {upper_key} is below observed p99 {observed_key}")
    if report.get("lane") == "release" and report.get("status") == "PASS":
        metrics = report.get("metrics", {})
        required_release = {"fixture_bytes": 10_000_000_000, "undo_redo_transactions": 1_000_000,
                            "adversarial_operations": 10_000_000, "peak_rss_bytes": 100_000_000,
                            "crash_recovery_verified": True, "byte_exact_10gb_fixture": True,
                            "provenance_verified": True}
        for key, minimum in required_release.items():
            value = metrics.get(key)
            if isinstance(minimum, bool):
                valid = value is minimum
            elif key == "fixture_bytes":
                valid = type(value) is int and value == minimum
            elif key == "peak_rss_bytes":
                valid = type(value) is int and value < minimum
            else:
                valid = type(value) is int and value >= minimum
            if not valid:
                errors.append(f"release qualification missing or failing {key}")
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
