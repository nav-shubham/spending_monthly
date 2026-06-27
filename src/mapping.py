import json
import os

class MappingManager:
    def __init__(self, mapping_file="vendor_mappings.json"):
        self.mapping_file = mapping_file
        self.exact_mappings = {}
        self.pattern_mappings = {}
        self.load_mappings()

    def load_mappings(self):
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, "r") as f:
                    data = json.load(f)
                    self.exact_mappings = data.get("exact_mappings", {})
                    self.pattern_mappings = data.get("pattern_mappings", {})
            except Exception as e:
                print(f"Error loading mapping file {self.mapping_file}: {e}")
                self.exact_mappings = {}
                self.pattern_mappings = {}
        else:
            self.exact_mappings = {}
            self.pattern_mappings = {}

    def save_mappings(self):
        try:
            with open(self.mapping_file, "w") as f:
                json.dump({
                    "exact_mappings": self.exact_mappings,
                    "pattern_mappings": self.pattern_mappings
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving mapping file {self.mapping_file}: {e}")

    def resolve_vendor(self, upi_id, default_vendor):
        """
        Resolves a unified vendor name for a given UPI ID and default vendor name
        using exact mappings first, then keyword pattern matching, and finally
        falling back to the default vendor.
        """
        upi_clean = str(upi_id).strip().lower()
        vendor_clean = str(default_vendor).strip().lower()
        
        if not upi_clean:
            return default_vendor
            
        # 1. Exact matches (UPI ID)
        for mapped_upi, vendor in self.exact_mappings.items():
            if mapped_upi.strip().lower() == upi_clean:
                return vendor
                
        # 2. Pattern matches (check if pattern is a substring of upi_id or default_vendor)
        for pattern, vendor in self.pattern_mappings.items():
            pat_clean = pattern.strip().lower()
            if pat_clean in upi_clean or pat_clean in vendor_clean:
                return vendor
                
        # 3. Fallback
        return default_vendor

    def add_exact_mapping(self, upi_id, vendor_name):
        self.exact_mappings[upi_id.strip()] = vendor_name.strip()
        self.save_mappings()

    def add_pattern_mapping(self, pattern, vendor_name):
        self.pattern_mappings[pattern.strip()] = vendor_name.strip()
        self.save_mappings()

    def remove_exact_mapping(self, upi_id):
        cleaned_id = upi_id.strip()
        if cleaned_id in self.exact_mappings:
            del self.exact_mappings[cleaned_id]
            self.save_mappings()
            return True
        return False

    def remove_pattern_mapping(self, pattern):
        cleaned_pattern = pattern.strip()
        if cleaned_pattern in self.pattern_mappings:
            del self.pattern_mappings[cleaned_pattern]
            self.save_mappings()
            return True
        return False
