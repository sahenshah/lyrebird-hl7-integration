"""Test 3: New message with downstream down."""
import pytest
import json
import time

def test_new_message_downstream_down(services, sender, example_message, audit_log_path):
    """Test that new messages fail correctly when downstream is down."""
    
    # Ensure downstream is dead
    print("💀 Ensuring downstream is down...")
    services.kill_downstream()
    
    # Send new message
    print("📤 Sending new message with downstream down...")
    result = sender.send(example_message, "MSA|AE")
    
    # Verify we got AE
    assert "MSA|AE" in result["stdout"], "Should get AE when downstream down"
    control_id = result["control_id"]
    
    # Check audit log for retry attempts
    time.sleep(2)  # Give time for retries to complete
    
    attempts = []
    with open(audit_log_path) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("message_control_id") == control_id:
                attempts.append(entry)
    
    # Should have multiple attempts (your retry logic)
    assert len(attempts) >= 3, f"Expected at least 3 attempts, got {len(attempts)}"
    
    # All attempts should have success=false
    for i, attempt in enumerate(attempts):
        assert attempt["success"] == False, f"Attempt {i+1} should be failure"
    
    print(f"✅ Failure test passed - {len(attempts)} retry attempts logged")