import json
from typing import List, Dict, Any, Tuple, Optional
from src.repository import Repository

class Services:
    def __init__(self, repository: Repository, mapping_manager):
        self.repository = repository
        self.mapping_manager = mapping_manager

    # --- BULK EDITING WORKFLOWS ---
    def bulk_assign_category(self, transaction_ids: List[int], category_name: str) -> int:
        """Assigns category to multiple transactions at once."""
        if not transaction_ids or not category_name:
            return 0
        return self.repository.bulk_update_category(transaction_ids, category_name)

    def bulk_assign_vendor(self, transaction_ids: List[int], vendor_name: str) -> int:
        """Assigns vendor to multiple transactions at once."""
        if not transaction_ids or not vendor_name:
            return 0
        return self.repository.bulk_update_vendor(transaction_ids, vendor_name)

    # --- MERCHANTS MERGING & UNDO ---
    def merge_merchants(self, source_vendor: str, target_vendor: str) -> Tuple[bool, str]:
        """
        Merges source merchant into target merchant:
        1. Identifies all transactions matching source_vendor.
        2. Bulk updates their vendor to target_vendor.
        3. Creates a mapping rule so future imports auto-resolve.
        4. Logs the action in merge_history for undo support.
        """
        source_clean = source_vendor.strip()
        target_clean = target_vendor.strip()
        
        if not source_clean or not target_clean:
            return False, "Merchant names cannot be empty."
        if source_clean.lower() == target_clean.lower():
            return False, "Cannot merge a merchant into itself."
            
        # Find all transactions currently resolved to source_clean
        df_src = self.repository.get_transactions_df({'vendor': source_clean})
        if df_src.empty:
            return False, f"No transactions found for merchant '{source_clean}'."
            
        txn_ids = df_src['id'].tolist()
        
        # 1. Update the transactions
        updated_count = self.repository.bulk_update_vendor(txn_ids, target_clean)
        
        # 2. Add auto-resolution rule (pattern match)
        # Create a rule that resolves the source name to the target name
        rule_added, msg = self.repository.add_rule('pattern', source_clean.lower(), target_clean, priority=2)
        rule_id = None
        if rule_added:
            self.mapping_manager.refresh_rules_cache()
            # Fetch the rule ID we just added
            rules = self.repository.get_rules()
            rule_id_candidates = [r['id'] for r in rules if r['pattern_value'].lower() == source_clean.lower() and r['target_vendor_name'] == target_clean]
            if rule_id_candidates:
                rule_id = rule_id_candidates[0]
                
        # 3. Log into merge history
        self.repository.record_merge(source_clean, target_clean, txn_ids, rule_id)
        
        return True, f"Successfully merged '{source_clean}' into '{target_clean}'. Updated {updated_count} transactions."

    def undo_last_merchant_merge(self) -> Tuple[bool, str]:
        """Undoes the latest merchant merge operation, restoring transaction names and rules."""
        latest = self.repository.get_latest_merge()
        if not latest:
            return False, "No previous merge history record found."
            
        merge_id = latest['id']
        source = latest['source_vendor']
        target = latest['target_vendor']
        txn_ids_str = latest['transaction_ids']
        rule_id = latest['rule_id']
        
        try:
            txn_ids = json.loads(txn_ids_str)
        except Exception:
            return False, "Corrupt merge transaction list. Cannot restore."
            
        # 1. Restore transaction vendor names back to source
        restored_count = self.repository.bulk_update_vendor(txn_ids, source)
        
        # 2. Delete the created mapping rule if existed
        if rule_id:
            self.repository.delete_rule(rule_id)
            self.mapping_manager.refresh_rules_cache()
            
        # 3. Delete merge record log
        self.repository.delete_merge_record(merge_id)
        
        return True, f"Successfully undone merge: Restored {restored_count} transactions back to '{source}'."
