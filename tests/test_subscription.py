import pandas as pd
import pytest
from datetime import datetime, timedelta
from src.subscription import detect_subscriptions

def test_detect_subscriptions():
    # Construct transactions DataFrame with a recurring subscription and a keyword subscription
    base_date = datetime(2026, 1, 1)
    
    # 1. Netflix (keyword matched) - 1 transaction
    # 2. Local Club (interval matched) - 3 transactions spaced 30 days apart
    data = {
        'ParsedDate': [
            base_date,  # Netflix
            base_date,  # Local Club 1
            base_date + timedelta(days=30),  # Local Club 2
            base_date + timedelta(days=60),  # Local Club 3
        ],
        'AmountNumeric': [
            -649.00,  # Netflix
            -1500.00,  # Local Club
            -1500.00,  # Local Club
            -1500.00,  # Local Club
        ],
        'Vendor': [
            'Netflix India',
            'Local Gym Membership',
            'Local Gym Membership',
            'Local Gym Membership',
        ],
        'CleanTag': ['Subscription', 'Subscription', 'Subscription', 'Subscription']
    }
    df = pd.DataFrame(data)
    
    subs = detect_subscriptions(df)
    
    assert len(subs) == 2
    
    # Check Netflix
    netflix_sub = next(s for s in subs if 'Netflix' in s['vendor'])
    assert netflix_sub['amount'] == 649.00
    assert "Monthly" in netflix_sub['frequency']
    assert netflix_sub['yearly_cost'] == 649.00 * 12
    
    # Check Gym
    gym_sub = next(s for s in subs if 'Gym' in s['vendor'])
    assert gym_sub['amount'] == 1500.00
    assert gym_sub['yearly_cost'] == 1500.00 * 12
    assert "Detected" in gym_sub['frequency']
