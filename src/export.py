import pandas as pd
import io

def generate_csv_export(df: pd.DataFrame) -> str:
    """Generates a raw CSV export of the transaction list."""
    if df.empty:
        return ""
    df_export = df.copy()
    if 'ParsedDate' in df_export.columns:
        df_export['ParsedDate'] = df_export['ParsedDate'].dt.strftime('%d/%m/%Y')
    return df_export.to_csv(index=False)

def generate_excel_report(df: pd.DataFrame, monthly_trends: pd.DataFrame, category_breakdown: pd.DataFrame) -> io.BytesIO:
    """
    Generates a multi-tab, formatted Excel report using openpyxl.
    Tabs: Transactions, Monthly Trends, Category Breakdown
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Transactions
        df_tx = df.copy()
        if not df_tx.empty and 'ParsedDate' in df_tx.columns:
            df_tx['ParsedDate'] = df_tx['ParsedDate'].dt.strftime('%Y-%m-%d')
        
        cols_to_export = [
            'ParsedDate', 'Time', 'Vendor', 'AmountNumeric', 'CleanTag', 
            'Other Transaction Details (UPI ID or A/c No)', 'Transaction Details', 'SourceFile'
        ]
        available_cols = [c for c in cols_to_export if c in df_tx.columns]
        df_tx_export = df_tx[available_cols].rename(columns={
            'ParsedDate': 'Date',
            'AmountNumeric': 'Amount (₹)',
            'CleanTag': 'Category',
            'Other Transaction Details (UPI ID or A/c No)': 'UPI ID / Acc'
        })
        df_tx_export.to_excel(writer, sheet_name='Transactions', index=False)
        
        # Sheet 2: Monthly Trends
        if not monthly_trends.empty:
            monthly_trends.to_excel(writer, sheet_name='Monthly Trends', index=False)
            
        # Sheet 3: Category Summary
        if not category_breakdown.empty:
            category_breakdown.to_excel(writer, sheet_name='Category Summary', index=False)
            
    output.seek(0)
    return output
