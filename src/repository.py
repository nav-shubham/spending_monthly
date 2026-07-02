import sqlite3
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
import json
import hashlib

def get_file_hash(file_path: str) -> str:
    """Computes SHA-256 hash of a file to identify duplicate statements."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except Exception:
        return ""

DEFAULT_CATEGORIES = [
    "Food", "Groceries", "Shopping", "Transport", "Fuel", "Medical", 
    "Utilities", "Entertainment", "Investment", "Subscription", "Education", 
    "Travel", "Personal Care", "Transfers", "Income", "Others"
]

class Repository:
    def __init__(self, db_path: str = "spending_tracker.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        """Initializes database schema, seeds categories, and creates indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Import History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE,
                    file_hash TEXT,
                    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    transaction_count INTEGER
                )
            """)
            
            # 2. Categories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    is_system BOOLEAN DEFAULT 0
                )
            """)
            
            # 3. Vendors
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    category_id INTEGER,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
                )
            """)
            
            # 4. Mapping Rules (Simplified: removed last_used and usage metrics)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mapping_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT CHECK(type IN ('exact', 'pattern', 'regex')),
                    pattern_value TEXT UNIQUE,
                    target_vendor_name TEXT,
                    priority INTEGER DEFAULT 1,
                    enabled BOOLEAN DEFAULT 1,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 5. Transactions (Unique constraint prevents duplicate imports)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parsed_date DATE,
                    time_str TEXT,
                    transaction_details TEXT,
                    upi_id_or_acc TEXT,
                    amount_str TEXT,
                    amount_numeric REAL,
                    is_negative BOOLEAN,
                    clean_tag TEXT,
                    is_mandate BOOLEAN,
                    is_self_transfer BOOLEAN,
                    source_file TEXT,
                    category_id INTEGER,
                    vendor_id INTEGER,
                    import_id INTEGER,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL,
                    FOREIGN KEY(vendor_id) REFERENCES vendors(id) ON DELETE SET NULL,
                    FOREIGN KEY(import_id) REFERENCES import_history(id) ON DELETE CASCADE,
                    UNIQUE(parsed_date, time_str, transaction_details, upi_id_or_acc, amount_numeric)
                )
            """)
            
            # 6. Budgets
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER UNIQUE,
                    monthly_limit REAL,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
                )
            """)
            
            # 7. Merge History (supports undoing merchant merges)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS merge_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_vendor TEXT,
                    target_vendor TEXT,
                    transaction_ids TEXT,  -- JSON list of transaction IDs affected
                    rule_id INTEGER,       -- Associated mapping rule ID created (optional)
                    merge_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for optimized reads
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(parsed_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions(amount_numeric)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_vendor ON transactions(vendor_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mapping_rules_priority ON mapping_rules(priority DESC)")
            
            # Seed categories
            for cat in DEFAULT_CATEGORIES:
                cursor.execute("INSERT OR IGNORE INTO categories (name, is_system) VALUES (?, 1)", (cat,))
                
            conn.commit()

    # --- CATEGORIES ---
    def get_categories(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, is_system FROM categories ORDER BY name ASC")
            return [dict(row) for row in cursor.fetchall()]

    def add_category(self, name: str) -> Tuple[bool, str]:
        name_clean = name.strip()
        if not name_clean:
            return False, "Category name cannot be empty."
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO categories (name, is_system) VALUES (?, 0)", (name_clean,))
                conn.commit()
                return True, "Category added."
            except sqlite3.IntegrityError:
                return False, f"Category '{name_clean}' already exists."

    def delete_category(self, cat_id: int) -> Tuple[bool, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_system FROM categories WHERE id = ?", (cat_id,))
            row = cursor.fetchone()
            if not row:
                return False, "Category not found."
            if row['is_system']:
                return False, "System categories cannot be deleted."
            
            cursor.execute("UPDATE transactions SET category_id = NULL WHERE category_id = ?", (cat_id,))
            cursor.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
            conn.commit()
            return True, "Category deleted."

    # --- RULES ---
    def get_rules(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, type, pattern_value, target_vendor_name, priority, enabled FROM mapping_rules ORDER BY priority DESC, created_date DESC")
            return [dict(row) for row in cursor.fetchall()]

    def add_rule(self, rtype: str, val: str, target: str, priority: int = 1) -> Tuple[bool, str]:
        val = val.strip()
        target = target.strip()
        if not val or not target:
            return False, "Rule value and target cannot be empty."
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Add vendor if it doesn't exist
                cursor.execute("INSERT OR IGNORE INTO vendors (name) VALUES (?)", (target,))
                cursor.execute("""
                    INSERT INTO mapping_rules (type, pattern_value, target_vendor_name, priority, enabled)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(pattern_value) DO UPDATE SET
                        type=excluded.type,
                        target_vendor_name=excluded.target_vendor_name,
                        priority=excluded.priority
                """, (rtype, val, target, priority))
                conn.commit()
                return True, "Rule saved."
            except Exception as e:
                return False, str(e)

    def delete_rule(self, rule_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM mapping_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0

    def toggle_rule(self, rule_id: int, enabled: bool) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE mapping_rules SET enabled = ? WHERE id = ?", (1 if enabled else 0, rule_id))
            conn.commit()
            return cursor.rowcount > 0

    # --- IMPORTS & INC SYNC ---
    def is_file_imported(self, filename: str, file_hash: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_hash FROM import_history WHERE filename = ?", (filename,))
            row = cursor.fetchone()
            return row is not None and row['file_hash'] == file_hash

    def insert_import_record(self, filename: str, file_hash: str, txn_count: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO import_history (filename, file_hash, transaction_count)
                VALUES (?, ?, ?)
            """, (filename, file_hash, txn_count))
            conn.commit()
            return cursor.lastrowid

    def delete_import(self, import_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions WHERE import_id = ?", (import_id,))
            cursor.execute("DELETE FROM import_history WHERE id = ?", (import_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_latest_import(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, filename, transaction_count, import_date FROM import_history ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_import_history(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, filename, transaction_count, import_date FROM import_history ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    # --- TRANSACTIONS ---
    def insert_transactions(self, df: pd.DataFrame, import_id: int) -> Tuple[int, int]:
        """Inserts transactions. Returns (inserted_count, duplicates_skipped)"""
        inserted = 0
        duplicates = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Prefetch categories & vendors mappings for efficiency
            cursor.execute("SELECT id, name FROM categories")
            cat_map = {r['name'].lower(): r['id'] for r in cursor.fetchall()}
            
            cursor.execute("SELECT id, name FROM vendors")
            ven_map = {r['name'].lower(): r['id'] for r in cursor.fetchall()}
            
            for _, row in df.iterrows():
                tag = row.get('CleanTag', 'Others')
                cat_id = cat_map.get(tag.lower())
                if not cat_id:
                    cursor.execute("INSERT OR IGNORE INTO categories (name, is_system) VALUES (?, 0)", (tag,))
                    cursor.execute("SELECT id FROM categories WHERE name = ?", (tag,))
                    r = cursor.fetchone()
                    cat_id = r['id'] if r else None
                    cat_map[tag.lower()] = cat_id
                    
                vendor = row.get('Vendor', row.get('DefaultVendor', 'Unknown'))
                ven_id = ven_map.get(vendor.lower())
                if not ven_id:
                    cursor.execute("INSERT OR IGNORE INTO vendors (name, category_id) VALUES (?, ?)", (vendor, cat_id))
                    cursor.execute("SELECT id FROM vendors WHERE name = ?", (vendor,))
                    r = cursor.fetchone()
                    ven_id = r['id'] if r else None
                    ven_map[vendor.lower()] = ven_id
                    
                try:
                    p_date = row['ParsedDate'].strftime('%Y-%m-%d') if isinstance(row['ParsedDate'], pd.Timestamp) else str(row['ParsedDate'])
                    cursor.execute("""
                        INSERT INTO transactions (
                            parsed_date, time_str, transaction_details, upi_id_or_acc, 
                            amount_str, amount_numeric, is_negative, clean_tag, 
                            is_mandate, is_self_transfer, source_file, category_id, vendor_id, import_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        p_date,
                        str(row.get('Time', '')),
                        str(row.get('Transaction Details', '')),
                        str(row.get('Other Transaction Details (UPI ID or A/c No)', '')),
                        str(row.get('Amount', '')),
                        float(row.get('AmountNumeric', 0.0)),
                        1 if row.get('IsNegative', False) else 0,
                        tag,
                        1 if row.get('IsMandate', False) else 0,
                        1 if row.get('IsSelfTransfer', False) else 0,
                        str(row.get('SourceFile', '')),
                        cat_id,
                        ven_id,
                        import_id
                    ))
                    inserted += 1
                except sqlite3.IntegrityError:
                    duplicates += 1
            conn.commit()
        return inserted, duplicates

    def get_transactions_df(self, filters: Dict[str, Any] = None) -> pd.DataFrame:
        query = """
            SELECT 
                t.id,
                t.parsed_date as ParsedDate,
                t.time_str as Time,
                t.transaction_details as [Transaction Details],
                t.upi_id_or_acc as [Other Transaction Details (UPI ID or A/c No)],
                t.amount_str as Amount,
                t.amount_numeric as AmountNumeric,
                t.is_negative as IsNegative,
                c.name as CleanTag,
                t.is_mandate as IsMandate,
                t.is_self_transfer as IsSelfTransfer,
                t.source_file as SourceFile,
                v.name as Vendor
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN vendors v ON t.vendor_id = v.id
            WHERE 1=1
        """
        params = []
        if filters:
            if filters.get('exclude_self_transfers'):
                query += " AND t.is_self_transfer = 0"
            if filters.get('exclude_blocked_mandates'):
                query += " AND t.is_mandate = 0"
            if filters.get('start_date'):
                query += " AND t.parsed_date >= ?"
                params.append(filters['start_date'])
            if filters.get('end_date'):
                query += " AND t.parsed_date <= ?"
                params.append(filters['end_date'])
            if filters.get('category') and filters['category'] != "All":
                query += " AND c.name = ?"
                params.append(filters['category'])
            if filters.get('vendor') and filters['vendor'] != "All":
                query += " AND v.name = ?"
                params.append(filters['vendor'])
            if filters.get('type') == "Debits (Expenses)":
                query += " AND t.amount_numeric < 0"
            elif filters.get('type') == "Credits (Income)":
                query += " AND t.amount_numeric > 0"
            if filters.get('search_q'):
                query += " AND (LOWER(v.name) LIKE ? OR LOWER(t.upi_id_or_acc) LIKE ? OR LOWER(t.transaction_details) LIKE ?)"
                q_like = f"%{filters['search_q'].lower()}%"
                params.extend([q_like, q_like, q_like])

        query += " ORDER BY t.parsed_date DESC, t.time_str DESC"
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            
        if not df.empty:
            df['ParsedDate'] = pd.to_datetime(df['ParsedDate'])
            df['IsNegative'] = df['IsNegative'].astype(bool)
            df['IsMandate'] = df['IsMandate'].astype(bool)
            df['IsSelfTransfer'] = df['IsSelfTransfer'].astype(bool)
            
            # Compute DefaultVendor dynamically
            from src.parser import extract_default_vendor
            df['DefaultVendor'] = df['Transaction Details'].apply(extract_default_vendor)
            
        return df

    def bulk_update_category(self, transaction_ids: List[int], cat_name: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (cat_name,))
            r = cursor.fetchone()
            if not r:
                return 0
            cat_id = r['id']
            
            placeholders = ",".join("?" for _ in transaction_ids)
            cursor.execute(f"UPDATE transactions SET category_id = ?, clean_tag = ? WHERE id IN ({placeholders})", [cat_id, cat_name] + transaction_ids)
            conn.commit()
            return cursor.rowcount

    def bulk_update_vendor(self, transaction_ids: List[int], vendor_name: str) -> int:
        vendor_name = vendor_name.strip()
        if not vendor_name:
            return 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO vendors (name) VALUES (?)", (vendor_name,))
            cursor.execute("SELECT id FROM vendors WHERE name = ?", (vendor_name,))
            v_id = cursor.fetchone()['id']
            
            placeholders = ",".join("?" for _ in transaction_ids)
            cursor.execute(f"UPDATE transactions SET vendor_id = ? WHERE id IN ({placeholders})", [v_id] + transaction_ids)
            conn.commit()
            return cursor.rowcount

    # --- BUDGETS ---
    def get_budgets(self) -> Dict[str, float]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT c.name, b.monthly_limit FROM budgets b JOIN categories c ON b.category_id = c.id")
            return {row['name']: row['monthly_limit'] for row in cursor.fetchall()}

    def save_budget(self, cat_name: str, limit: float) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (cat_name,))
            r = cursor.fetchone()
            if not r:
                return False
            cat_id = r['id']
            cursor.execute("""
                INSERT INTO budgets (category_id, monthly_limit) VALUES (?, ?)
                ON CONFLICT(category_id) DO UPDATE SET monthly_limit = excluded.monthly_limit
            """, (cat_id, limit))
            conn.commit()
            return True

    def delete_budget(self, cat_name: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (cat_name,))
            r = cursor.fetchone()
            if not r:
                return False
            cursor.execute("DELETE FROM budgets WHERE category_id = ?", (r['id'],))
            conn.commit()
            return cursor.rowcount > 0

    # --- VENDOR MERGE & UNDO MERGE ---
    def record_merge(self, src: str, target: str, txn_ids: List[int], rule_id: Optional[int]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO merge_history (source_vendor, target_vendor, transaction_ids, rule_id)
                VALUES (?, ?, ?, ?)
            """, (src, target, json.dumps(txn_ids), rule_id))
            conn.commit()
            return cursor.lastrowid

    def get_latest_merge(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, source_vendor, target_vendor, transaction_ids, rule_id FROM merge_history ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_merge_record(self, merge_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM merge_history WHERE id = ?", (merge_id,))
            conn.commit()

    def get_unique_vendors(self) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM vendors ORDER BY name ASC")
            return [row['name'] for row in cursor.fetchall()]

    def clear_all_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions")
            cursor.execute("DELETE FROM vendors")
            cursor.execute("DELETE FROM import_history")
            cursor.execute("DELETE FROM budgets")
            cursor.execute("DELETE FROM merge_history")
            cursor.execute("DELETE FROM categories WHERE is_system = 0")
            conn.commit()
