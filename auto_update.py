import os
import glob
import sqlite3
import openpyxl
import pandas as pd
from src.repository import Repository, get_file_hash
from src.mapping import MappingManager
from src.importer import Importer
from generate_final_excel import generate_final_excel

def sync_excel_edits_to_db(db_path: str, excel_path: str):
    """
    Reads spending_tracker_final.xlsx, extracts any manual edits (overridden formulas
    or added rules), and persists them back to the SQLite database.
    """
    if not os.path.exists(excel_path):
        print("No existing Excel report found to sync overrides from.")
        return
        
    print("Reading existing spending_tracker_final.xlsx for manual edits...")
    try:
        # Load workbook keeping formula strings intact (data_only=False)
        wb = openpyxl.load_workbook(excel_path, data_only=False)
    except Exception as e:
        print(f"Warning: Could not open existing Excel file to sync edits: {e}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Sync Rules Sheet
    if "Rules" in wb.sheetnames:
        ws_rules = wb["Rules"]
        
        # A. Exact UPI rules in columns A-B (rows 5 onwards)
        row = 5
        while True:
            upi = ws_rules.cell(row=row, column=1).value
            vendor = ws_rules.cell(row=row, column=2).value
            if not upi and not vendor:
                break
            if upi and vendor:
                upi_clean = str(upi).strip()
                vendor_clean = str(vendor).strip()
                if upi_clean and vendor_clean:
                    cursor.execute("INSERT OR IGNORE INTO vendors (name) VALUES (?)", (vendor_clean,))
                    cursor.execute("""
                        INSERT INTO mapping_rules (type, pattern_value, target_vendor_name, priority, enabled)
                        VALUES ('exact', ?, ?, 4, 1)
                        ON CONFLICT(pattern_value) DO UPDATE SET target_vendor_name=excluded.target_vendor_name
                    """, (upi_clean, vendor_clean))
            row += 1
            
        # B. Substring pattern rules in columns D-F (rows 5 onwards)
        row = 5
        while True:
            pattern = ws_rules.cell(row=row, column=4).value
            vendor = ws_rules.cell(row=row, column=5).value
            prio = ws_rules.cell(row=row, column=6).value
            if not pattern and not vendor:
                break
            if pattern and vendor:
                pattern_clean = str(pattern).strip().lower()
                vendor_clean = str(vendor).strip()
                prio_val = int(prio) if prio is not None else 2
                if pattern_clean and vendor_clean:
                    cursor.execute("INSERT OR IGNORE INTO vendors (name) VALUES (?)", (vendor_clean,))
                    cursor.execute("""
                        INSERT INTO mapping_rules (type, pattern_value, target_vendor_name, priority, enabled)
                        VALUES ('pattern', ?, ?, ?, 1)
                        ON CONFLICT(pattern_value) DO UPDATE SET target_vendor_name=excluded.target_vendor_name, priority=excluded.priority
                    """, (pattern_clean, vendor_clean, prio_val))
            row += 1
            
        # C. Vendor category mapping in columns H-I (rows 5 onwards)
        row = 5
        while True:
            vendor = ws_rules.cell(row=row, column=8).value
            category = ws_rules.cell(row=row, column=9).value
            if not vendor and not category:
                break
            if vendor and category:
                vendor_clean = str(vendor).strip()
                cat_clean = str(category).strip()
                if vendor_clean and cat_clean:
                    cursor.execute("INSERT OR IGNORE INTO categories (name, is_system) VALUES (?, 0)", (cat_clean,))
                    cursor.execute("SELECT id FROM categories WHERE name = ?", (cat_clean,))
                    cat_id = cursor.fetchone()[0]
                    cursor.execute("INSERT OR IGNORE INTO vendors (name, category_id) VALUES (?, ?)", (vendor_clean, cat_id))
                    cursor.execute("UPDATE vendors SET category_id = ? WHERE name = ?", (cat_id, vendor_clean))
            row += 1
            
    # 2. Sync Transactions Sheet (Manual Overrides)
    if "Transactions" in wb.sheetnames:
        ws_tx = wb["Transactions"]
        
        cursor.execute("SELECT id, name FROM categories")
        cat_map = {r[1].lower(): r[0] for r in cursor.fetchall()}
        cursor.execute("SELECT id, name FROM vendors")
        ven_map = {r[1].lower(): r[0] for r in cursor.fetchall()}
        
        row = 2
        while True:
            date_val = ws_tx.cell(row=row, column=1).value
            amt_val = ws_tx.cell(row=row, column=5).value
            if date_val is None and amt_val is None:
                break
                
            time_val = ws_tx.cell(row=row, column=2).value or ""
            narr_val = ws_tx.cell(row=row, column=3).value or ""
            upi_val = ws_tx.cell(row=row, column=4).value or ""
            
            if hasattr(date_val, 'strftime'):
                date_str = date_val.strftime('%Y-%m-%d')
            else:
                date_str = str(date_val).strip()
                
            try:
                amt_numeric = float(amt_val)
            except (ValueError, TypeError):
                row += 1
                continue
                
            resolved_vendor_cell = ws_tx.cell(row=row, column=7).value
            category_cell = ws_tx.cell(row=row, column=8).value
            
            vendor_override = None
            category_override = None
            
            # Check if Column G is an override (doesn't start with '=' and is not empty)
            if resolved_vendor_cell and not str(resolved_vendor_cell).startswith('='):
                vendor_override = str(resolved_vendor_cell).strip()
                
            # Check if Column H is an override (doesn't start with '=' and is not empty)
            if category_cell and not str(category_cell).startswith('='):
                category_override = str(category_cell).strip()
                
            if vendor_override or category_override:
                cursor.execute("""
                    SELECT id, category_id, vendor_id FROM transactions 
                    WHERE parsed_date = ? AND time_str = ? AND transaction_details = ? 
                      AND upi_id_or_acc = ? AND amount_numeric = ?
                """, (date_str, str(time_val), str(narr_val), str(upi_val), amt_numeric))
                t_row = cursor.fetchone()
                
                if t_row:
                    t_id, current_cat_id, current_ven_id = t_row
                    updates = []
                    params = []
                    
                    if vendor_override:
                        ven_key = vendor_override.lower()
                        if ven_key not in ven_map:
                            cursor.execute("INSERT OR IGNORE INTO vendors (name) VALUES (?)", (vendor_override,))
                            cursor.execute("SELECT id FROM vendors WHERE name = ?", (vendor_override,))
                            v_id = cursor.fetchone()[0]
                            ven_map[ven_key] = v_id
                        else:
                            v_id = ven_map[ven_key]
                        
                        if v_id != current_ven_id:
                            updates.append("vendor_id = ?")
                            params.append(v_id)
                            
                    if category_override:
                        cat_key = category_override.lower()
                        if cat_key not in cat_map:
                            cursor.execute("INSERT OR IGNORE INTO categories (name, is_system) VALUES (?, 0)", (category_override,))
                            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_override,))
                            c_id = cursor.fetchone()[0]
                            cat_map[cat_key] = c_id
                        else:
                            c_id = cat_map[cat_key]
                            
                        if c_id != current_cat_id:
                            updates.append("category_id = ?, clean_tag = ?")
                            params.extend([c_id, category_override])
                            
                    if updates:
                        params.append(t_id)
                        cursor.execute(f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?", params)
            row += 1
            
    conn.commit()
    conn.close()
    print("Manual Excel overrides successfully synced back to database.")

def auto_update():
    statements_dir = r"D:\03 Permanent Personal Data\01 Expences\UPI_Statements"
    db_file = "spending_tracker.db"
    excel_file = "spending_tracker_final.xlsx"
    
    if not os.path.exists(statements_dir):
        print(f"Error: Statements directory not found: {statements_dir}")
        return
        
    # --- STEP 1: Sync existing manual changes back to SQLite database ---
    sync_excel_edits_to_db(db_file, excel_file)
    
    # --- STEP 2: Scans folder for new statements ---
    repository = Repository(db_file)
    mapping_manager = MappingManager(repository)
    importer = Importer(repository, mapping_manager)
    
    extensions = ("*.xlsx", "*.xls", "*.csv")
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(statements_dir, ext)))
        
    new_files_imported = 0
    
    for file_path in files:
        filename = os.path.basename(file_path)
        f_hash = get_file_hash(file_path)
        
        if not f_hash:
            continue
            
        # Check if already imported
        if repository.is_file_imported(filename, f_hash):
            continue
            
        print(f"New file detected: {filename}. Parsing and importing...")
        df = importer.preview_import(file_path)
        if df is not None and not df.empty:
            success, msg = importer.commit_import(file_path, df)
            if success:
                print(f"Successfully committed: {msg}")
                new_files_imported += 1
            else:
                print(f"Failed to commit {filename}: {msg}")
        else:
            print(f"Error: Statement format not recognized or empty for {filename}.")
                
    # Always regenerate excel output if sync succeeded or new files added
    print("Writing fresh database snapshot into spending_tracker_final.xlsx...")
    generate_final_excel()
    print("Excel report updated successfully!")

if __name__ == "__main__":
    auto_update()
