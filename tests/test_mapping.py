import os
import json
import pytest
from src.mapping import MappingManager

def test_mapping_resolution(tmp_path):
    mapping_file = tmp_path / "test_mappings.json"
    
    # Create dummy mapping file
    initial_data = {
        "exact_mappings": {
            "test_upi@okaxis": "Target Exact Merchant"
        },
        "pattern_mappings": {
            "datta": "Shri Datta Mart",
            "blinkit": "Blinkit"
        }
    }
    with open(mapping_file, "w") as f:
        json.dump(initial_data, f)
        
    manager = MappingManager(str(mapping_file))
    
    # Test exact match
    assert manager.resolve_vendor("test_upi@okaxis", "Default Vendor") == "Target Exact Merchant"
    # Case insensitivity
    assert manager.resolve_vendor("TEST_UPI@okaxis", "Default Vendor") == "Target Exact Merchant"
    
    # Test pattern match
    assert manager.resolve_vendor("paytm.s15cg9m@pty", "Paid to Shri Datta Mart") == "Shri Datta Mart"
    assert manager.resolve_vendor("paytm-blinkit@ptybl", "Blinkit") == "Blinkit"
    
    # Test fallback
    assert manager.resolve_vendor("unknown_upi@ybl", "Local Shop") == "Local Shop"

def test_add_remove_mappings(tmp_path):
    mapping_file = tmp_path / "test_mappings.json"
    manager = MappingManager(str(mapping_file))
    
    manager.add_exact_mapping("new_upi@oksbi", "New Vendor")
    manager.add_pattern_mapping("swiggy", "Swiggy Delivery")
    
    # Reload and test persistence
    manager2 = MappingManager(str(mapping_file))
    assert manager2.resolve_vendor("new_upi@oksbi", "Other") == "New Vendor"
    assert manager2.resolve_vendor("swiggy.order@ybl", "Other") == "Swiggy Delivery"
    
    # Test removal
    assert manager2.remove_exact_mapping("new_upi@oksbi") is True
    assert manager2.resolve_vendor("new_upi@oksbi", "Other") == "Other"
