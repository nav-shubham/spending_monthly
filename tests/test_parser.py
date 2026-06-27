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
