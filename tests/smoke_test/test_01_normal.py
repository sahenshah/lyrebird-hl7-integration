"""Test 1: Normal operation - all services up."""
import pytest
from pathlib import Path

def test_normal_operation(services, sender, example_message, audit_log_path):
    """Test that a normal message is processed successfully."""
    
    # Send message
    control_id = sender.send_and_expect(example_message, "MSA|AA")
    
    # Verify audit log
    assert audit_log_path.exists()
    
    # Find our message in audit log
    entries = []
    with open(audit_log_path) as f:
        for line in f:
            entry = eval(line)
            if entry.get("message_control_id") == control_id:
                entries.append(entry)
    
    assert len(entries) == 1, "Expected exactly one audit entry"
    assert entries[0]["success"] == True
    assert "response_time_ms" in entries[0]
    
    print(f"\n✅ Normal operation test passed - Control ID: {control_id}")