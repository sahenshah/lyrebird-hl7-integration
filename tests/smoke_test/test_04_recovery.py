"""Test 4: Recovery and retry after downstream returns."""
import pytest
import json
import time

def test_recovery_and_retry(services, sender, example_message, audit_log_path):
    """Test that failed messages can be retried after recovery."""
    
    # Kill downstream
    print("💀 Killing downstream...")
    services.kill_downstream()
    
    # Send message (should fail)
    print("📤 Sending message that will fail...")
    result1 = sender.send(example_message, "MSA|AE")
    control_id = result1["control_id"]
    
    # Wait for retries to complete
    time.sleep(3)
    
    # Restart downstream
    print("🔄 Restarting downstream...")
    services.restart_downstream()
    
    # Resend same message
    print("📤 Resending same message...")
    result2 = sender.send(example_message, "MSA|AA")
    
    assert result2["control_id"] == control_id, "Control ID should match"
    
    # Check audit log for successful retry
    found_success = False
    found_failures = 0
    
    with open(audit_log_path) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("message_control_id") == control_id:
                if entry.get("success") == True:
                    found_success = True
                else:
                    found_failures += 1
    
    assert found_failures > 0, "Should have failed attempts"
    assert found_success, "Should have successful attempt after recovery"
    
    print(f"✅ Recovery test passed - {found_failures} failures then success")