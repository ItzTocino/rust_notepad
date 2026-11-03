#!/usr/bin/env python3
"""Emit a provenance-bound status record. Verification remains separate."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ci/evidence"
FIXTURE = ROOT / "ci/fixtures/baseline.json"
POLICY = ROOT / "ci/policy/milestones.json"
REQUIRED = ROOT / "ci/policy/required-checks.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=["correctness", "adversarial", "performance", "release"], required=True)
    parser.add_argument("--status", choices=["PASS", "FAIL", "INCONCLUSIVE", "NOT_APPLICABLE"], required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    payload_dir = OUT / "artifacts"
    payload_dir.mkdir(exist_ok=True)
    payload = payload_dir / "payload.bin"
    payload.write_bytes(b"status-only placeholder; no product measurements")
    report = {
        "schema_version": 1, "lane": args.lane, "status": args.status,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "fixture_sha256": digest(FIXTURE), "runner": __import__("platform").node(),
        "policy_sha256": hashlib.sha256(POLICY.read_bytes() + REQUIRED.read_bytes()).hexdigest(),
        "toolchain": "rustc " + subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "sample_count": 0 if args.lane != "correctness" else len(json.loads(REQUIRED.read_text(encoding="utf-8"))["checks"]),
        "artifact_sha256": digest(payload), "reason": args.reason,
        "metrics": {"checks": json.loads(REQUIRED.read_text(encoding="utf-8"))["checks"]} if args.lane == "correctness" else {}
    }
    (OUT / f"{args.lane}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
