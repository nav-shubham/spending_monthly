import pytest
import pandas as pd
from src.parser import clean_amount, clean_tag, extract_default_vendor

def test_clean_amount():
    assert clean_amount("-2,900.50") == (-2900.50, True)
    assert clean_amount("+210.00") == (210.00, False)
    assert clean_amount("14,790.00") == (14790.00, False)
    assert clean_amount(None) == (0.0, False)
    assert clean_amount("invalid") == (0.0, False)

def test_clean_tag():
    assert clean_tag("#🛒 Groceries") == "Groceries"
    assert clean_tag("#🧾 Bill Payments") == "Bill Payments"
    assert clean_tag("#🛍 Shopping") == "Shopping"
    assert clean_tag(None) == "Uncategorized"
    assert clean_tag("Normal Tag") == "Normal Tag"

def test_extract_default_vendor():
    assert extract_default_vendor("Paid to Shri Datta Mart") == "Shri Datta Mart"
    assert extract_default_vendor("Received from Balaji Kisan Dudhal") == "Balaji Kisan Dudhal"
    assert extract_default_vendor("Money sent to Mr Vijay Sadashiv Kadam1") == "Mr Vijay Sadashiv Kadam1"
    assert extract_default_vendor("Transferred to Self, Kotak Mahindra Bank") == "Self Transfer (Kotak Mahindra Bank)"
    assert extract_default_vendor("Transferred to Self, ") == "Self Transfer"
    assert extract_default_vendor(None) == "Unknown"

def test_parse_statement_file_phonepe(tmp_path):
    # Construct a dummy PhonePe CSV
    csv_file = tmp_path / "phonepe_statement.csv"
    content = (
        "Transaction ID,Date,Description,Amount,Type\n"
        "T123,2026-06-01,Payment to DMart,1500.00,DEBIT\n"
        "T124,2026-06-02,Salary credit,25000.00,CREDIT\n"
    )
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    from src.parser import parse_statement_file
    df = parse_statement_file(str(csv_file))
    
    assert df is not None
    assert len(df) == 2
    assert df.iloc[0]['DefaultVendor'] == "DMart"
    assert df.iloc[0]['AmountNumeric'] == -1500.00
    assert df.iloc[1]['AmountNumeric'] == 25000.00
    assert df.iloc[0]['SourceFormat'] == "PhonePe"


def test_parse_statement_file_generic(tmp_path):
    # Construct a dummy generic CSV
    csv_file = tmp_path / "generic_statement.csv"
    content = (
        "Date,Details,Amount,UPI ID\n"
        "2026-06-15,Uber India,-450.00,uber@paytm\n"
        "2026-06-16,Friend Transfer,200.00,friend@upi\n"
    )
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    from src.parser import parse_statement_file
    df = parse_statement_file(str(csv_file))
    
    assert df is not None
    assert len(df) == 2
    assert df.iloc[0]['DefaultVendor'] == "Uber India"
    assert df.iloc[0]['AmountNumeric'] == -450.00
    assert df.iloc[1]['AmountNumeric'] == 200.00
    assert df.iloc[0]['SourceFormat'] == "Google Pay / Generic"


