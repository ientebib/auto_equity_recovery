#!/usr/bin/env python3
"""
Test suite for the Lead Completion Tracking System

This script tests all aspects of the completion tracking functionality
to ensure it works correctly with the existing lead recovery system.
"""

import sys
import time
import uuid
from pathlib import Path

# Add the lead_recovery package to the path
sys.path.append(str(Path(__file__).parent))

from lead_recovery.cache import SummaryCache, compute_conversation_digest

def test_basic_completion_workflow():
    """Test the basic completion workflow"""
    print("🧪 Testing basic completion workflow...")
    
    cache = SummaryCache()
    
    # Test data - use unique identifiers to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    phone = f"test_phone_{unique_id}"
    recipe = f"test_recipe_{unique_id}"
    conversation = f"Test conversation content {unique_id}"
    agent = "Test Agent"
    notes = "Test completion notes"
    
    digest = compute_conversation_digest(conversation)
    
    # 1. Check initial status (should be ACTIVE)
    status = cache.get_lead_completion_status(phone, recipe, digest)
    assert status['status'] == 'ACTIVE', f"Expected ACTIVE, got {status['status']}"
    assert not status['is_completed'], "Lead should not be completed initially"
    print("   ✅ Initial status check passed")
    
    # 2. Mark as complete
    success = cache.mark_lead_complete(phone, recipe, digest, agent, notes)
    assert success, "Failed to mark lead as complete"
    print("   ✅ Lead completion passed")
    
    # 3. Check completed status
    status = cache.get_lead_completion_status(phone, recipe, digest)
    assert status['status'] == 'COMPLETED', f"Expected COMPLETED, got {status['status']}"
    assert status['is_completed'], "Lead should be marked as completed"
    assert status['completion_info']['completed_by'] == agent, "Completed by mismatch"
    print("   ✅ Completion status check passed")
    
    # 4. Test reactivation on conversation change
    new_conversation = conversation + "\nNew message from customer"
    new_digest = compute_conversation_digest(new_conversation)
    
    status = cache.get_lead_completion_status(phone, recipe, new_digest)
    assert status['status'] == 'REACTIVATED', f"Expected REACTIVATED, got {status['status']}"
    assert not status['is_completed'], "Reactivated lead should not be completed"
    assert status['needs_reactivation'], "Lead should need reactivation"
    print("   ✅ Reactivation test passed")
    
    return True

def test_completion_stats():
    """Test completion statistics functionality"""
    print("🧪 Testing completion statistics...")
    
    cache = SummaryCache()
    unique_id = str(uuid.uuid4())[:8]
    recipe = f"test_stats_recipe_{unique_id}"
    
    # Create some test completions
    test_leads = [
        (f"phone1_{unique_id}", "Agent A", "Completed lead 1"),
        (f"phone2_{unique_id}", "Agent B", "Completed lead 2"),
        (f"phone3_{unique_id}", "Agent A", "Completed lead 3"),
    ]
    
    for phone, agent, notes in test_leads:
        conversation = f"Test conversation for {phone}"
        digest = compute_conversation_digest(conversation)
        cache.mark_lead_complete(phone, recipe, digest, agent, notes)
    
    # Test stats
    stats = cache.get_completion_stats(recipe)
    assert stats['total_tracked'] >= 3, f"Expected at least 3 tracked leads, got {stats['total_tracked']}"
    assert 'COMPLETED' in stats['status_counts'], "Should have completed leads in stats"
    assert stats['status_counts']['COMPLETED'] >= 3, "Should have at least 3 completed leads"
    print("   ✅ Completion stats test passed")
    
    # Test completed leads list
    completed_leads = cache.get_completed_leads_for_recipe(recipe)
    assert len(completed_leads) >= 3, f"Expected at least 3 completed leads, got {len(completed_leads)}"
    print("   ✅ Completed leads list test passed")
    
    return True

def test_backward_compatibility():
    """Test that completion tracking doesn't break existing functionality"""
    print("🧪 Testing backward compatibility...")
    
    cache = SummaryCache()
    
    # Test that existing cache methods still work
    unique_id = str(uuid.uuid4())[:8]
    test_key = f"test_backward_compat_{unique_id}"
    test_data = {"test": "data", "timestamp": time.time()}
    model_version = "test_model_v1"
    
    # Test basic cache operations (using correct signature)
    cache.set(test_key, test_data, model_version)
    retrieved = cache.get(test_key, model_version)
    assert retrieved == test_data, "Basic cache operations should still work"
    print("   ✅ Basic cache operations test passed")
    
    # Test that completion tracking doesn't interfere with normal operations
    phone = f"compat_test_phone_{unique_id}"
    recipe = f"compat_test_recipe_{unique_id}"
    conversation = f"Compatibility test conversation {unique_id}"
    digest = compute_conversation_digest(conversation)
    
    # Check status for non-existent completion (should be ACTIVE)
    status = cache.get_lead_completion_status(phone, recipe, digest)
    assert status['status'] == 'ACTIVE', "Non-tracked leads should be ACTIVE"
    print("   ✅ Non-tracked lead status test passed")
    
    return True

def test_edge_cases():
    """Test edge cases and error handling"""
    print("🧪 Testing edge cases...")
    
    cache = SummaryCache()
    
    # Test with empty/None values
    try:
        status = cache.get_lead_completion_status("", "", "")
        # Should not crash, should return ACTIVE status
        assert status['status'] == 'ACTIVE', "Empty values should return ACTIVE status"
        print("   ✅ Empty values test passed")
    except Exception as e:
        print(f"   ❌ Empty values test failed: {e}")
        return False
    
    # Test with very long strings
    long_phone = "1" * 100
    long_recipe = "recipe" * 50
    long_conversation = "conversation " * 1000
    long_digest = compute_conversation_digest(long_conversation)
    
    try:
        status = cache.get_lead_completion_status(long_phone, long_recipe, long_digest)
        assert status['status'] == 'ACTIVE', "Long strings should work"
        print("   ✅ Long strings test passed")
    except Exception as e:
        print(f"   ❌ Long strings test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 Lead Completion Tracking System Tests")
    print("=" * 50)
    
    tests = [
        test_basic_completion_workflow,
        test_completion_stats,
        test_backward_compatibility,
        test_edge_cases,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ {test.__name__} PASSED")
            else:
                failed += 1
                print(f"❌ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The completion tracking system is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 