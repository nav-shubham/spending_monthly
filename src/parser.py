import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
import pandas as pd
import glob
import os
import re
from typing import Dict, Any


def clean_amount(amount_str):
    """
    Cleans amount string (e.g. '-2,900.50' or '+210.00' or '14,790.00')
    Returns float value and a boolean indicating if it was a negative amount (expense).
    """
    if pd.isna(amount_str):
        return 0.0, False
    s = str(amount_str).replace(',', '').strip()
    is_neg = s.startswith('-')
    # Strip any leading + or -
    s_clean = s.lstrip('+-')
    try:
        val = float(s_clean)
        return -val if is_neg else val, is_neg
    except ValueError:
        return 0.0, False

def clean_tag(tag_val):
    """
    Strips hashes and emoji characters from Paytm category tags.
    e.g. '#🛒 Groceries' -> 'Groceries'
    """
    if pd.isna(tag_val):
        return "Uncategorized"
    s = str(tag_val).replace('#', '').strip()
    # Remove emojis/non-ascii characters
    s_clean = re.sub(r'[^\x00-\x7F]+', '', s).strip()
    return s_clean if s_clean else "Uncategorized"

def extract_default_vendor(details_str):
    """
    Extracts the clean vendor name from transaction detail descriptions by stripping prefixes.
    e.g. 'Paid to Shri Datta Mart' -> 'Shri Datta Mart'
    """
    if pd.isna(details_str):
        return "Unknown"
    s = str(details_str).strip()
    
    # Check if self transfer
    if re.search(r'transferred to self', s, re.IGNORECASE):
        # Extract target bank details if possible
        bank_match = re.search(r'transferred to self,\s*(.+)', s, re.IGNORECASE)
        if bank_match and bank_match.group(1).strip():
            return f"Self Transfer ({bank_match.group(1).strip()})"
        return "Self Transfer"
        
    prefixes = [
        r"^Paid to\s+",
        r"^Received from\s+",
        r"^Money sent to\s+",
        r"^Money received from\s+",
        r"^Transferred to Self,\s+",
        r"^Automatic payment of\s+.*?\s+setup for\s+",
        r"^Automatic payment for\s+",
        r"^Bill Payment for\s+",
        r"^Paid for\s+",
        r"^Money blocked for\s+",
        r"^Money unblocked for\s+",
        r"^Payment to\s+",
        r"^Payment for\s+"
    ]
    for pref in prefixes:
        s = re.sub(pref, "", s, flags=re.IGNORECASE)
    
    # Strip any double spaces
    s = re.sub(r'\s+', ' ', s).strip()
    if not s:
        return "Other"
    return s

def parse_statement_file(file_path):
    """
    Parses a transaction statement file (Paytm, PhonePe, Google Pay, or generic CSV/Excel).
    Automatically detects the format, normalizes the columns, and returns a cleaned DataFrame.
    """
    ext = os.path.splitext(file_path)[1].lower()
    df_raw = None
    source_format = "unknown"
    
    try:
        if ext == '.csv':
            # Try reading as CSV
            try:
                df_raw = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df_raw = pd.read_csv(file_path, encoding='latin1')
        elif ext in ('.xlsx', '.xls'):
            xl = pd.ExcelFile(file_path)
            if 'Passbook Payment History' in xl.sheet_names:
                df_raw = xl.parse('Passbook Payment History')
                source_format = "paytm"
            else:
                # Load first sheet
                df_raw = xl.parse(xl.sheet_names[0])
        else:
            print(f"Unsupported file extension: {ext}")
            return None
            
        if df_raw is None or df_raw.empty:
            return None

        # Clean column names to make detection easier
        cols = [str(c).strip() for c in df_raw.columns]
        df_raw.columns = cols
        
        # --- Format Auto-Detection and Normalization ---
        df_norm = pd.DataFrame()
        
        # 1. Paytm (Verified Sheet or Paytm specific columns)
        if source_format == "paytm" or ('Transaction Details' in cols and 'Other Transaction Details (UPI ID or A/c No)' in cols):
            df_norm = df_raw.copy()
            df_norm['SourceFormat'] = "Paytm"
            
        # 2. PhonePe
        elif any('phonepe' in str(c).lower() for c in cols) or ('Transaction ID' in cols and 'Merchant/Recipient' in cols) or ('Transaction ID' in cols and 'Sender Bank' in cols) or ('Transaction ID' in cols and 'Type' in cols):
            # Normalizing PhonePe format
            # Columns typically: Transaction ID, Date, Description/Merchant, Type (DEBIT/CREDIT), Amount
            df_norm['Date'] = df_raw.get('Date', df_raw.get('Transaction Date', df_raw.get('Timestamp', '')))
            df_norm['Time'] = df_raw.get('Time', '')
            df_norm['Transaction Details'] = df_raw.get('Description', df_raw.get('Merchant/Recipient', df_raw.get('Payment To', '')))
            df_norm['Other Transaction Details (UPI ID or A/c No)'] = df_raw.get('UPI ID', df_raw.get('Receiver UPI ID', ''))
            
            # Amount cleaning for PhonePe
            amounts = df_raw.get('Amount', df_raw.get('Amount (INR)', 0.0))
            txn_type = df_raw.get('Type', df_raw.get('Transaction Type', 'DEBIT'))
            # Format as standard Paytm strings with +/- prefix
            formatted_amounts = []
            for amt, t in zip(amounts, txn_type):
                amt_clean = str(amt).replace('₹', '').replace(',', '').strip()
                t_str = str(t).upper()
                if 'DEBIT' in t_str or 'OUT' in t_str or 'PAY' in t_str:
                    formatted_amounts.append(f"-{amt_clean}")
                else:
                    formatted_amounts.append(f"+{amt_clean}")
            df_norm['Amount'] = formatted_amounts
            df_norm['Comment'] = df_raw.get('Comment', df_raw.get('Remarks', ''))
            df_norm['Tags'] = 'Uncategorized'
            df_norm['Remarks'] = ''
            df_norm['SourceFormat'] = "PhonePe"
            
        # 3. Google Pay / Generic CSV
        else:
            # Let's map best match columns
            date_col = next((c for c in cols if any(k in c.lower() for k in ['date', 'time', 'timestamp'])), None)
            desc_col = next((c for c in cols if any(k in c.lower() for k in ['desc', 'details', 'particulars', 'narration', 'payee', 'merchant'])), None)
            upi_col = next((c for c in cols if any(k in c.lower() for k in ['upi', 'account', 'vpa', 'vpa/upi'])), None)
            amount_col = next((c for c in cols if any(k in c.lower() for k in ['amount', 'value', 'txnamt'])), None)
            
            if date_col and amount_col:
                df_norm['Date'] = df_raw[date_col]
                df_norm['Time'] = ''
                df_norm['Transaction Details'] = df_raw[desc_col] if desc_col else 'Transaction'
                df_norm['Other Transaction Details (UPI ID or A/c No)'] = df_raw[upi_col] if upi_col else ''
                df_norm['Amount'] = df_raw[amount_col].astype(str)
                df_norm['Comment'] = ''
                df_norm['Tags'] = 'Uncategorized'
                df_norm['Remarks'] = ''
                df_norm['SourceFormat'] = "Google Pay / Generic"
            else:
                print(f"Skipping {file_path}: Unknown format columns: {cols}")
                return None
                
        # --- Clean & Standardize Values ---
        # Fill missing values for text columns
        df_norm['Transaction Details'] = df_norm['Transaction Details'].fillna('')
        df_norm['Other Transaction Details (UPI ID or A/c No)'] = df_norm['Other Transaction Details (UPI ID or A/c No)'].fillna('')
        df_norm['Comment'] = df_norm.get('Comment', pd.Series(['']*len(df_norm))).fillna('')
        df_norm['Tags'] = df_norm.get('Tags', pd.Series(['Uncategorized']*len(df_norm))).fillna('Uncategorized')
        df_norm['Remarks'] = df_norm.get('Remarks', pd.Series(['']*len(df_norm))).fillna('')
        
        # Clean amount
        cleaned_amounts_info = df_norm['Amount'].apply(clean_amount)
        df_norm['AmountNumeric'] = [info[0] for info in cleaned_amounts_info]
        df_norm['IsNegative'] = [info[1] for info in cleaned_amounts_info]
        
        # Clean category tag
        df_norm['CleanTag'] = df_norm['Tags'].apply(clean_tag)
        
        # Parse Dates
        # Standard format is DD/MM/YYYY or YYYY-MM-DD
        df_norm['ParsedDate'] = pd.to_datetime(df_norm['Date'], errors='coerce')
        # If coerce failed for some, try dayfirst
        failed_mask = df_norm['ParsedDate'].isna() & df_norm['Date'].notna()
        if failed_mask.any():
            df_norm.loc[failed_mask, 'ParsedDate'] = pd.to_datetime(df_norm.loc[failed_mask, 'Date'], dayfirst=True, errors='coerce')
            
        # Identify Mandates
        df_norm['IsMandate'] = df_norm['Comment'].str.contains("not included in total", case=False, na=False) | \
                               df_norm['Transaction Details'].str.contains("Money blocked for|Money unblocked for", case=False, na=False)
        
        # Extract default vendor name
        df_norm['DefaultVendor'] = df_norm['Transaction Details'].apply(extract_default_vendor)
        
        # Identify Self Transfer
        df_norm['IsSelfTransfer'] = df_norm['Transaction Details'].str.contains("transferred to self", case=False, na=False) | \
                                    (df_norm['CleanTag'].str.lower() == 'transfers')
        
        # Source filename for tracking
        df_norm['SourceFile'] = os.path.basename(file_path)
        
        return df_norm
        
    except Exception as e:
        print(f"Error parsing file {file_path}: {e}")
        return None


def load_all_statements(folder_path):
    """
    Finds and parses all .xlsx statement files in the folder_path.
    Returns a combined DataFrame.
    """
    files = glob.glob(os.path.join(folder_path, "*.xlsx"))
    all_dfs = []
    for file_path in files:
        df = parse_statement_file(file_path)
        if df is not None and not df.empty:
            all_dfs.append(df)
            
    if not all_dfs:
        return pd.DataFrame()
        
    combined = pd.concat(all_dfs, ignore_index=True)
    # Sort by date and time
    combined = combined.sort_values(by=['ParsedDate', 'Time'], ascending=[False, False]).reset_index(drop=True)
    return combined

def sync_statements_to_db(db_manager, mapping_manager, folder_path: str) -> Dict[str, Any]:
    """
    Scans the folder_path for new/updated statement Excel files, calculates hashes,
    parses them, resolves vendors, and stores them in the persistent SQLite database.
    """
    from src.db import get_file_hash
    
    if not os.path.exists(folder_path):
        return {"status": "error", "message": f"Directory not found: {folder_path}"}
        
    files = glob.glob(os.path.join(folder_path, "*.xlsx"))
    if not files:
        return {"status": "no_files", "message": "No statement Excel files found."}
        
    synced_files = []
    total_added = 0
    total_skipped = 0
    
    for file_path in files:
        filename = os.path.basename(file_path)
        f_hash = get_file_hash(file_path)
        
        if not f_hash:
            continue
            
        # Check if already imported
        if db_manager.is_file_imported(filename, f_hash):
            continue
            
        # Parse statement
        df = parse_statement_file(file_path)
        if df is not None and not df.empty:
            # Resolve vendor names using rule engine
            # resolve_vendor returns (name, rule_id, conflict)
            df['Vendor'] = df.apply(
                lambda row: mapping_manager.resolve_vendor(
                    row['Other Transaction Details (UPI ID or A/c No)'], 
                    row['DefaultVendor'],
                    row['Transaction Details']
                )[0],
                axis=1
            )
            
            # Save into SQLite DB
            added, skipped = db_manager.insert_transactions_batch(df, filename, f_hash)
            total_added += added
            total_skipped += skipped
            synced_files.append(filename)
            
    return {
        "status": "success",
        "synced_files": synced_files,
        "added_transactions": total_added,
        "skipped_transactions": total_skipped
    }

