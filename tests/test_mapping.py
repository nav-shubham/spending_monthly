import os
import sqlite3
import pytest
from src.repository import Repository
from src.mapping import MappingManager

@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_tracker.db"
    repo = Repository(str(db_file))
    yield repo
    # Clean up
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass

def test_repository_categories(temp_repo):
    # Verify default categories exist
    cats = temp_repo.get_categories()
    cat_names = [c['name'] for c in cats]
    assert "Food" in cat_names
    assert "Groceries" in cat_names
    
    # Test adding custom category
    success, msg = temp_repo.add_category("Gifts")
    assert success is True
    cats = temp_repo.get_categories()
    cat_names = [c['name'] for c in cats]
    assert "Gifts" in cat_names
    
    # Test duplicate prevention
    success, msg = temp_repo.add_category("Gifts")
    assert success is False
    
    # Test deleting custom category
    gifts_id = [c['id'] for c in cats if c['name'] == "Gifts"][0]
    success, msg = temp_repo.delete_category(gifts_id)
    assert success is True
    
    # Test system category deletion prevention
    food_id = [c['id'] for c in cats if c['name'] == "Food"][0]
    success, msg = temp_repo.delete_category(food_id)
    assert success is False

def test_mapping_resolution(temp_repo):
    # Add mapping rules directly via repo
    temp_repo.add_rule('exact', 'test_upi@okaxis', 'Target Exact Merchant', priority=4)
    temp_repo.add_rule('pattern', 'datta', 'Shri Datta Mart', priority=2)
    temp_repo.add_rule('pattern', 'blinkit', 'Blinkit', priority=2)
    temp_repo.add_rule('regex', r'swiggy\d+', 'Swiggy Delivery', priority=3)
    
    manager = MappingManager(temp_repo)
    
    # Test exact match
    resolved, rule_id, conflict = manager.resolve_vendor("test_upi@okaxis", "Default Vendor")
    assert resolved == "Target Exact Merchant"
    assert rule_id is not None
    assert conflict is False
    
    # Test exact match case insensitivity
    resolved, _, _ = manager.resolve_vendor("TEST_UPI@okaxis", "Default Vendor")
    assert resolved == "Target Exact Merchant"
    
    # Test pattern match
    resolved, _, _ = manager.resolve_vendor("paytm.s15cg9m@pty", "Paid to Shri Datta Mart")
    assert resolved == "Shri Datta Mart"
    
    # Test regex match
    resolved, _, _ = manager.resolve_vendor("swiggy123@okaxis", "Default Vendor")
    assert resolved == "Swiggy Delivery"
    
    # Test fallback
    resolved, rule_id, conflict = manager.resolve_vendor("unknown_upi@ybl", "Local Shop")
    assert resolved == "Local Shop"
    assert rule_id is None
    assert conflict is False

def test_rule_conflict_detection(temp_repo):
    # Add rules that will both match
    # 'datta mart' matches both 'datta' and 'mart'
    temp_repo.add_rule('pattern', 'datta', 'Shri Datta Mart', priority=2)
    temp_repo.add_rule('pattern', 'mart', 'Generic Mart', priority=2)
    
    manager = MappingManager(temp_repo)
    
    resolved, rule_id, conflict = manager.resolve_vendor("paytm@dattamart", "Default")
    # Both match. Priority is same, so it will pick whichever is sorted first. But conflict should be True.
    assert conflict is True
    assert resolved in ("Shri Datta Mart", "Generic Mart")
