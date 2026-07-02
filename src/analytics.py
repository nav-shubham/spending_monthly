import pandas as pd
from typing import Dict, Any

def calculate_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculates simplified core KPIs (Total Inflow, Total Outflow, Net Savings, Savings Rate)."""
    if df.empty:
        return {
            "total_inflow": 0.0, "total_outflow": 0.0, 
            "net_cashflow": 0.0, "savings_rate": 0.0
        }
        
    inflow_tx = df[df['AmountNumeric'] > 0]
    outflow_tx = df[df['AmountNumeric'] < 0]
    
    total_inflow = inflow_tx['AmountNumeric'].sum()
    total_outflow = abs(outflow_tx['AmountNumeric'].sum())
    net_cashflow = total_inflow - total_outflow
    savings_rate = (net_cashflow / total_inflow * 100) if total_inflow > 0 else 0.0
    
    return {
        "total_inflow": total_inflow,
        "total_outflow": total_outflow,
        "net_cashflow": net_cashflow,
        "savings_rate": savings_rate
    }

def calculate_monthly_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates income, expenses, and savings grouped by calendar month."""
    if df.empty:
        return pd.DataFrame(columns=['YearMonth', 'Income', 'Expense', 'Savings'])
        
    df_monthly = df.copy()
    df_monthly['YearMonth'] = df_monthly['ParsedDate'].dt.to_period('M').astype(str)
    
    monthly = df_monthly.groupby('YearMonth').agg(
        Income=('AmountNumeric', lambda x: x[x > 0].sum()),
        Expense=('AmountNumeric', lambda x: abs(x[x < 0].sum()))
    ).reset_index()
    
    monthly['Savings'] = monthly['Income'] - monthly['Expense']
    return monthly.sort_values('YearMonth')

def calculate_top_categories(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Calculates category spending totals."""
    outflow_tx = df[df['AmountNumeric'] < 0].copy()
    if outflow_tx.empty:
        return pd.DataFrame(columns=['CleanTag', 'Spent'])
        
    summary = outflow_tx.groupby('CleanTag')['AmountNumeric'].agg(lambda x: abs(x.sum())).reset_index()
    summary = summary.rename(columns={'AmountNumeric': 'Spent'}).sort_values(by='Spent', ascending=False)
    return summary.head(limit)

def calculate_top_merchants(df: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    """Calculates merchant spending totals."""
    outflow_tx = df[df['AmountNumeric'] < 0].copy()
    if outflow_tx.empty:
        return pd.DataFrame(columns=['Vendor', 'Spent'])
        
    summary = outflow_tx.groupby('Vendor')['AmountNumeric'].agg(lambda x: abs(x.sum())).reset_index()
    summary = summary.rename(columns={'AmountNumeric': 'Spent'}).sort_values(by='Spent', ascending=False)
    return summary.head(limit)
