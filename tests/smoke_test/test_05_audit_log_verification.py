"""Test 5: Comprehensive audit log verification."""
import pytest
import json
from pathlib import Path
import time

def test_audit_log_completeness(services, sender, example_message, audit_log_path):
    """Verify that audit log contains all expected information."""
    
    # Run a complete sequence
    print("📤 Running test sequence...")
    
    # 1. Normal message
    control_id_1 = sender.send_and_expect(example_message, "MSA|AA")
    
    # 2. Kill downstream and send duplicate
    services.kill_downstream()
    sender.send(example_message, "MSA|AA")
    
    # 3. Send new message (fails)
    result = sender.send(example_message, "MSA|AE")
    control_id_2 = result["control_id"]
    time.sleep(3)  # Let retries complete
    
    # 4. Restart and retry
    services.restart_downstream()
    sender.send(example_message, "MSA|AA")
    
    # Now verify the audit log
    print("🔍 Verifying audit log...")
    
    with open(audit_log_path) as f:
        entries = [json.loads(line) for line in f]
    
    # Group by control_id
    by_id = {}
    for entry in entries:
        cid = entry.get("message_control_id")
        if cid:
            by_id.setdefault(cid, []).append(entry)
    
    # Verify message 1
    assert control_id_1 in by_id, f"Missing control_id {control_id_1}"
    msg1_entries = by_id[control_id_1]
    
    # Should have at least: original success + duplicate skip
    successes = [e for e in msg1_entries if e.get("success") == True]
    skips = [e for e in msg1_entries if e.get("status") == "skipped_already_processed"]
    
    assert len(successes) >= 1, "Message 1 should have success"
    assert len(skips) >= 1, "Message 1 should have skip entry"
    
    # Verify message 2
    assert control_id_2 in by_id, f"Missing control_id {control_id_2}"
    msg2_entries = by_id[control_id_2]
    
    failures = [e for e in msg2_entries if e.get("success") == False]
    final_success = [e for e in msg2_entries if e.get("success") == True]
    
    assert len(failures) >= 2, f"Message 2 should have failures, got {len(failures)}"
    assert len(final_success) == 1, "Message 2 should have final success"
    
    # Verify timestamps are present
    for entry in entries:
        assert "timestamp" in entry, "Missing timestamp"
        assert "message_control_id" in entry, "Missing control_id"
    
    print(f"✅ Audit log verification passed - {len(entries)} total entries")
    print(f"   Message 1: {len(msg1_entries)} entries ({len(successes)} success, {len(skips)} skip)")
    print(f"   Message 2: {len(msg2_entries)} entries ({len(failures)} failures, {len(final_success)} success)")