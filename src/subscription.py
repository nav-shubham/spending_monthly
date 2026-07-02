import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

SUBSCRIPTION_KEYWORDS = [
    "netflix", "spotify", "youtube premium", "icloud", "google one", 
    "amazon prime", "microsoft 365", "office 365", "disney", "hotstar", 
    "openai", "chatgpt", "github copilot", "zoom", "canva", "adobe", 
    "playstore", "app store", "subscription", "membership"
]

def detect_subscriptions(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Analyzes transactions to detect recurring monthly or annual subscriptions.
    Identifies them based on keyword matching, or regular interval spacing (25-35 days).
    """
    subscriptions = []
    
    debits = df[df['AmountNumeric'] < 0].copy()
    if debits.empty:
        return subscriptions
        
    debits['ParsedDate'] = pd.to_datetime(debits['ParsedDate'])
    debits['AmountAbs'] = debits['AmountNumeric'].abs()
    
    # 1. Group by Merchant and Amount to find identical periodic payments
    grouped = debits.groupby(['Vendor', 'AmountAbs'])
    
    current_date = datetime.now()
    
    for (vendor, amount), group in grouped:
        if len(group) < 2:
            # Check if it matches a known subscription keyword even if it has only 1 transaction
            vendor_lower = vendor.lower()
            if any(kw in vendor_lower for kw in SUBSCRIPTION_KEYWORDS):
                # Single subscription transaction
                last_payment = group['ParsedDate'].max()
                subscriptions.append({
                    "vendor": vendor,
                    "amount": amount,
                    "frequency": "Monthly (Estimated)",
                    "billing_cycle": "Monthly",
                    "transaction_count": 1,
                    "last_payment_date": last_payment,
                    "yearly_cost": amount * 12,
                    "missed_payment": False,
                    "reason": "Recognized subscription service name"
                })
            continue
            
        # Sort transaction dates chronologically
        dates = sorted(group['ParsedDate'].unique())
        
        # Calculate intervals in days
        intervals = []
        for i in range(1, len(dates)):
            diff_days = (dates[i] - dates[i-1]).days
            intervals.append(diff_days)
            
        if not intervals:
            continue
            
        # Analyze intervals to determine subscription type
        avg_interval = sum(intervals) / len(intervals)
        
        is_monthly = 25 <= avg_interval <= 35
        is_annual = 350 <= avg_interval <= 375
        
        # Or check if interval consistency is high
        # We check standard deviation of intervals. If low, it is recurring
        interval_std = pd.Series(intervals).std() if len(intervals) > 1 else 0.0
        is_consistent = interval_std < 5.0 if len(intervals) > 1 else True
        
        if (is_monthly or is_annual) and is_consistent:
            cycle = "Monthly" if is_monthly else "Annual"
            freq_multiplier = 12 if is_monthly else 1
            last_payment = max(dates)
            
            # Check for missed payment
            # A payment is missed if the elapsed time since last_payment is more than 1.5 times the expected interval
            expected_days = 30 if is_monthly else 365
            days_since_last = (pd.Timestamp(current_date) - pd.Timestamp(last_payment)).days
            missed = days_since_last > (expected_days * 1.5)
            
            subscriptions.append({
                "vendor": vendor,
                "amount": amount,
                "frequency": f"{cycle} (Detected)",
                "billing_cycle": cycle,
                "transaction_count": len(dates),
                "last_payment_date": last_payment,
                "yearly_cost": amount * freq_multiplier,
                "missed_payment": missed,
                "reason": f"Recurring payments every {int(avg_interval)} days."
            })
            
    # Remove duplicates where a merchant might have both keyword and interval detections
    seen_vendors = set()
    unique_subs = []
    for sub in sorted(subscriptions, key=lambda x: x['yearly_cost'], reverse=True):
        v = sub['vendor']
        if v not in seen_vendors:
            seen_vendors.add(v)
            unique_subs.append(sub)
            
    return unique_subs
