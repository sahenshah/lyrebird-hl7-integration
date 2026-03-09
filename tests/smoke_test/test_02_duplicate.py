"""Test 2: Duplicate message handling with downstream down."""
import pytest
import time
import json
import subprocess
import sys
from pathlib import Path


def _send(project_root: Path, msg: Path) -> str:
    p = subprocess.run(
        [sys.executable, "-m", "app.sender", "--file", str(msg)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")


def test_duplicate_with_downstream_down(services, downstream_api, project_root):
    msg = project_root / "examples" / "sample_adt_a01.hl7"
    audit = project_root / "logs" / "publisher_audit.jsonl"

    # 1) First send (normal)
    out1 = _send(project_root, msg)
    assert "MSA|AA" in out1, f"First send should be AA, got:\n{out1}"

    # 2) Kill downstream API
    subprocess.run(
        ["bash", "-lc", "pkill -f 'uvicorn app.stub_api:app.*--port 9000'"],
        check=False,
    )

    # 3) Send same message again (duplicate -> should still be AA)
    out2 = _send(project_root, msg)
    assert "MSA|AA" in out2, f"Duplicate send should be AA, got:\n{out2}"

    # 4) Audit log should classify duplicate as skipped
    entries = []
    if audit.exists():
        with open(audit) as f:
            entries = [json.loads(line) for line in f if line.strip()]

    dup_entries = [e for e in entries if e.get("message_control_id") == "123456"]
    assert dup_entries, "No audit entries found for control_id=123456"

    has_skipped = any(e.get("status") == "skipped_already_processed" for e in dup_entries)
    assert has_skipped, f"Expected skipped_already_processed in audit, got: {dup_entries}"