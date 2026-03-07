"""Test 2: Duplicate message handling with downstream down."""
import pytest
import time
import json

def test_duplicate_with_downstream_down(services, sender, example_message, audit_log_path):
    """Test that duplicate messages are handled correctly."""
    
    # Send first message (normal)
    print("\n📤 Sending original message...")
    control_id = sender.send_and_expect(example_message, "MSA|AA")
    
    # Kill downstream
    print("💀 Killing downstream...")
    services.kill_downstream()
    
    # Send duplicate
    print("📤 Sending duplicate message...")
    result = sender.send(example_message, "MSA|AA")
    
    # Verify we got AA (idempotency)
    assert "MSA|AA" in result["stdout"], "Duplicate should get AA"
    assert result["control_id"] == control_id, "Control ID should match"
    
    # Check audit log for duplicate marker
    duplicate_found = False
    with open(audit_log_path) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("message_control_id") == control_id:
                if entry.get("status") == "skipped_already_processed":
                    duplicate_found = True
                elif entry.get("success") is True:
                    # First successful entry is fine
                    pass
                else:
                    pytest.fail(f"Unexpected entry: {entry}")
    
    assert duplicate_found, "No 'skipped_already_processed' entry found in audit log"
    print("✅ Duplicate test passed - Message correctly skipped")