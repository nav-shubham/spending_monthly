import re
from typing import List, Dict, Any, Tuple, Optional
from src.repository import Repository

class MappingManager:
    def __init__(self, repository: Repository):
        self.repository = repository
        self.exact_rules = {}   # key -> target_vendor
        self.pattern_rules = []  # list of (pattern, target_vendor, priority, rule_id)
        self.regex_rules = []    # list of (regex_pattern, target_vendor, priority, rule_id)
        self.refresh_rules_cache()

    def refresh_rules_cache(self):
        """Loads all active rules from SQLite database into memory for fast matching."""
        rules = self.repository.get_rules()
        
        self.exact_rules = {}
        self.pattern_rules = []
        self.regex_rules = []
        
        for rule in rules:
            if not rule.get('enabled', 1):
                continue
                
            rule_id = rule['id']
            rtype = rule['type']
            val = rule['pattern_value'].strip()
            target = rule['target_vendor_name']
            priority = rule.get('priority', 1)
            
            if rtype == 'exact':
                self.exact_rules[val.lower()] = (target, rule_id)
            elif rtype == 'pattern':
                self.pattern_rules.append((val.lower(), target, priority, rule_id))
            elif rtype == 'regex':
                try:
                    compiled = re.compile(val, re.IGNORECASE)
                    self.regex_rules.append((compiled, target, priority, rule_id))
                except re.error as e:
                    print(f"Invalid regex in rule #{rule_id}: {val} - {e}")
                    
        # Sort pattern rules by priority DESC
        self.pattern_rules.sort(key=lambda x: x[2], reverse=True)

    def resolve_vendor(self, upi_id: str, default_vendor: str, details_str: str = "") -> Tuple[str, Optional[int], bool]:
        """
        Resolves a vendor name using rules.
        Returns:
            (resolved_vendor_name, matching_rule_id, is_conflict)
        """
        upi_clean = str(upi_id).strip().lower()
        vendor_clean = str(default_vendor).strip().lower()
        details_clean = str(details_str).strip().lower()
        
        matches = []  # list of (resolved_name, rule_id, priority)
        
        # 1. Exact Match
        if upi_clean in self.exact_rules:
            target, r_id = self.exact_rules[upi_clean]
            matches.append((target, r_id, 4))  # exact rules default priority 4
            
        # 2. Regex Match
        for pattern_re, target, priority, r_id in self.regex_rules:
            if pattern_re.search(upi_clean) or pattern_re.search(vendor_clean) or pattern_re.search(details_clean):
                matches.append((target, r_id, priority))
                
        # 3. Pattern Match
        for pattern_val, target, priority, r_id in self.pattern_rules:
            if pattern_val in upi_clean or pattern_val in vendor_clean or pattern_val in details_clean:
                matches.append((target, r_id, priority))
                
        if not matches:
            return default_vendor, None, False
            
        # Sort matches by priority descending
        matches.sort(key=lambda x: x[2], reverse=True)
        
        # Simple conflict check: multiple matching rules resolving to DIFFERENT vendors
        unique_vendors = set(m[0] for m in matches)
        is_conflict = len(unique_vendors) > 1
        
        best_match = matches[0]
        return best_match[0], best_match[1], is_conflict

    def add_exact_mapping(self, upi_id: str, vendor_name: str, priority: int = 4):
        self.repository.add_rule('exact', upi_id, vendor_name, priority=priority)
        self.refresh_rules_cache()

    def add_pattern_mapping(self, pattern: str, vendor_name: str, priority: int = 2):
        self.repository.add_rule('pattern', pattern, vendor_name, priority=priority)
        self.refresh_rules_cache()

    def add_regex_mapping(self, pattern: str, vendor_name: str, priority: int = 3):
        self.repository.add_rule('regex', pattern, vendor_name, priority=priority)
        self.refresh_rules_cache()

    def remove_rule(self, rule_id: int) -> bool:
        res = self.repository.delete_rule(rule_id)
        if res:
            self.refresh_rules_cache()
        return res

    def toggle_rule(self, rule_id: int, enabled: bool) -> bool:
        res = self.repository.toggle_rule(rule_id, enabled)
        if res:
            self.refresh_rules_cache()
        return res
