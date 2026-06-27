import pandas as pd
import glob
import os
import re

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
        r"^Money unblocked for\s+"
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
    Parses a single Paytm Excel sheet statement.
    Returns a cleaned pandas DataFrame.
    """
    try:
        xl = pd.ExcelFile(file_path)
        if 'Passbook Payment History' not in xl.sheet_names:
            print(f"Skipping {file_path}: 'Passbook Payment History' sheet not found.")
            return None
        
        df = xl.parse('Passbook Payment History')
        
        # Check required columns
        required_cols = ['Date', 'Time', 'Transaction Details', 'Other Transaction Details (UPI ID or A/c No)', 'Amount']
        for col in required_cols:
            if col not in df.columns:
                print(f"Skipping {file_path}: Required column '{col}' is missing.")
                return None
                
        # Fill missing values for text columns
        df['Transaction Details'] = df['Transaction Details'].fillna('')
        df['Other Transaction Details (UPI ID or A/c No)'] = df['Other Transaction Details (UPI ID or A/c No)'].fillna('')
        df['Comment'] = df['Comment'].fillna('')
        df['Tags'] = df['Tags'].fillna('Uncategorized')
        df['Remarks'] = df['Remarks'].fillna('')
        
        # Clean amount
        cleaned_amounts_info = df['Amount'].apply(clean_amount)
        df['AmountNumeric'] = [info[0] for info in cleaned_amounts_info]
        df['IsNegative'] = [info[1] for info in cleaned_amounts_info]
        
        # Clean category tag
        df['CleanTag'] = df['Tags'].apply(clean_tag)
        
        # Parse Dates
        # Standard format is DD/MM/YYYY
        df['ParsedDate'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        
        # Identify Mandates
        # E.g., Comment contains "not included in total"
        df['IsMandate'] = df['Comment'].str.contains("not included in total", case=False, na=False) | \
                          df['Transaction Details'].str.contains("Money blocked for|Money unblocked for", case=False, na=False)
        
        # Extract default vendor name
        df['DefaultVendor'] = df['Transaction Details'].apply(extract_default_vendor)
        
        # Identify Self Transfer
        df['IsSelfTransfer'] = df['Transaction Details'].str.contains("transferred to self", case=False, na=False) | \
                               (df['CleanTag'].str.lower() == 'transfers')
        
        # Source filename for tracking
        df['SourceFile'] = os.path.basename(file_path)
        
        return df
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
