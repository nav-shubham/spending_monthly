import pandas as pd
import pytest
from src.analytics import (
    calculate_kpis, 
    calculate_monthly_trends,
    calculate_top_categories,
    calculate_top_merchants
)

@pytest.fixture
def sample_transactions_df():
    data = {
        'ParsedDate': pd.to_datetime([
            '2026-01-01', '2026-01-02', '2026-01-15', '2026-01-20',
            '2026-02-01', '2026-02-05', '2026-02-15', '2026-02-28'
        ]),
        'Time': [
            '10:30', '14:20', '09:00', '18:15',
            '08:45', '20:10', '11:30', '22:00'
        ],
        'AmountNumeric': [
            1000.00, -200.00, -150.00, -50.00,  # Jan: +1000, -400. Net: 600
            2000.00, -500.00, -150.00, -100.00  # Feb: +2000, -750. Net: 1250
        ],
        'CleanTag': [
            'Income', 'Food', 'Groceries', 'Transport',
            'Income', 'Shopping', 'Groceries', 'Utilities'
        ],
        'Vendor': [
            'Salary', 'Starbucks', 'DMart', 'Uber',
            'Salary', 'Amazon', 'DMart', 'MSEDCL'
        ]
    }
    return pd.DataFrame(data)

def test_calculate_kpis(sample_transactions_df):
    kpis = calculate_kpis(sample_transactions_df)
    
    assert kpis['total_inflow'] == 3000.00
    assert kpis['total_outflow'] == 1150.00
    assert kpis['net_cashflow'] == 1850.00
    assert kpis['savings_rate'] == (1850.00 / 3000.00 * 100)

def test_calculate_monthly_trends(sample_transactions_df):
    monthly = calculate_monthly_trends(sample_transactions_df)
    
    assert len(monthly) == 2
    assert 'YearMonth' in monthly.columns
    assert 'Income' in monthly.columns
    assert 'Expense' in monthly.columns
    assert 'Savings' in monthly.columns
    
    jan = monthly[monthly['YearMonth'] == '2026-01'].iloc[0]
    assert jan['Income'] == 1000.00
    assert jan['Expense'] == 400.00
    assert jan['Savings'] == 600.00
    
    feb = monthly[monthly['YearMonth'] == '2026-02'].iloc[0]
    assert feb['Income'] == 2000.00
    assert feb['Expense'] == 750.00
    assert feb['Savings'] == 1250.00

def test_calculate_top_categories(sample_transactions_df):
    top_cats = calculate_top_categories(sample_transactions_df, limit=2)
    assert len(top_cats) <= 2
    assert top_cats.iloc[0]['CleanTag'] == 'Shopping'  # 500 spent
    assert top_cats.iloc[0]['Spent'] == 500.00

def test_calculate_top_merchants(sample_transactions_df):
    top_merchants = calculate_top_merchants(sample_transactions_df, limit=2)
    assert len(top_merchants) <= 2
    assert top_merchants.iloc[0]['Vendor'] == 'Amazon'  # 500 spent
    assert top_merchants.iloc[0]['Spent'] == 500.00
