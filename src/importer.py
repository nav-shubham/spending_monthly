import os
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from src.repository import Repository, get_file_hash
from src.parser import parse_statement_file

class Importer:
    def __init__(self, repository: Repository, mapping_manager):
        self.repository = repository
        self.mapping_manager = mapping_manager

    def preview_import(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Parses statement file and returns transaction preview DataFrame.
        Does not commit to SQLite.
        """
        if not os.path.exists(file_path):
            return None
        df = parse_statement_file(file_path)
        if df is not None and not df.empty:
            # Add preview calculations for Vendor
            df['Vendor'] = df.apply(
                lambda row: self.mapping_manager.resolve_vendor(
                    row['Other Transaction Details (UPI ID or A/c No)'], 
                    row['DefaultVendor'],
                    row['Transaction Details']
                )[0],
                axis=1
            )
            return df
        return None

    def commit_import(self, file_path: str, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Commits statement transactions to SQLite database.
        Checks for duplicates using file hashing.
        """
        filename = os.path.basename(file_path)
        f_hash = get_file_hash(file_path)
        
        if not f_hash:
            return False, "Could not compute statement file integrity hash."
            
        if self.repository.is_file_imported(filename, f_hash):
            return False, f"File '{filename}' already imported previously."
            
        # 1. Insert import history log
        import_id = self.repository.insert_import_record(filename, f_hash, len(df))
        
        # 2. Insert transactions batch
        inserted, duplicates = self.repository.insert_transactions(df, import_id)
        
        # 3. Update the record count to match actual inserted count
        # (Though we log total, keeping it correct is clean)
        return True, f"Successfully imported '{filename}'. Added {inserted} new transactions. Skipped {duplicates} duplicate rows."

    def undo_last_import(self) -> Tuple[bool, str]:
        """Undoes the last import session, deleting its transactions and log."""
        latest = self.repository.get_latest_import()
        if not latest:
            return False, "No previous import history record found."
            
        import_id = latest['id']
        filename = latest['filename']
        tx_count = latest['transaction_count']
        
        if self.repository.delete_import(import_id):
            return True, f"Successfully undone last import '{filename}' (removed {tx_count} transactions)."
        return False, "Failed to remove the last import."
