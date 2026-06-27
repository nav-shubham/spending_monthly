# UPI Spending Analyzer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a premium, interactive Streamlit application to parse UPI statements, automatically group similar/multiple UPI IDs under unified vendors, categorize transactions, and visualize monthly spending and income trends.

**Architecture:** The application will consist of a modular codebase:
1. A parser module (`src/parser.py`) to read and clean Paytm UPI statements (handling date formatting, float amount parsing, self-transfers, and blocked mandates).
2. A mapping manager (`src/mapping.py`) that loads, updates, and persists custom UPI-to-Vendor mappings to `vendor_mappings.json`.
3. A Streamlit frontend (`app.py`) providing interactive metric cards, Plotly charts, vendor mapping UI, and a transaction explorer.

**Tech Stack:** Python 3.12, Streamlit, Pandas, Openpyxl, Plotly, JSON.

---

### Task 1: Initialize Project Directories and Config

**Files:**
- Create: `docs/plans/2026-06-27-upi-spending-analyzer.md`
- Create: `src/__init__.py`
- Create: `vendor_mappings.json`

**Step 1: Write the initialization of the directories and dummy config**
We'll create the source directory and write a basic `vendor_mappings.json` schema.

```json
{
  "exact_mappings": {},
  "pattern_mappings": {
    "datta": "Shri Datta Mart",
    "blinkit": "Blinkit",
    "jio": "Jio / MyJio",
    "electricity": "MSEDCL Electricity",
    "openaillc": "OpenAI"
  }
}
```

**Step 2: Commit**
```bash
git add src/ vendor_mappings.json
git commit -m "chore: initialize src directory and default vendor mappings config"
```

---

### Task 2: Implement the UPI Statement Parser

**Files:**
- Create: `src/parser.py`
- Create: `tests/test_parser.py`

**Step 1: Write parser logic that handles Paytm statement fields**
We need a robust parser that:
1. Loads the Excel files from the target directory.
2. Extracts sheets, specifically `Passbook Payment History`.
3. Cleans the `Amount` column: removes commas, converts to float, preserves negative values for expenses and positive for income.
4. Cleans the `Date` and `Time` columns.
5. Standardizes the default Vendor Name from `Transaction Details` (e.g., stripping "Paid to", "Received from", "Money sent to").
6. Cleans the `Tags` column (strips emojis and hashes, e.g., `#🛒 Groceries` -> `Groceries`).
7. Correctly identifies blocked/unblocked money mandates using the `Comment` column or regex (to exclude them from regular spending).

**Step 2: Write tests for the parser**
Create `tests/test_parser.py` using simple mock dataframes to assert cleaning operations and check assertions.

```python
import pandas as pd
from src.parser import clean_amount, clean_tag, extract_default_vendor

def test_cleaning_logic():
    assert clean_amount("-2,900.50") == -2900.50
    assert clean_amount("+210.00") == 210.00
    assert clean_amount("14,790.00") == 14790.00
    assert clean_tag("#🛒 Groceries") == "Groceries"
    assert extract_default_vendor("Paid to Shri Datta Mart") == "Shri Datta Mart"
    assert extract_default_vendor("Transferred to Self, Kotak Bank") == "Self Transfer"
```

**Step 3: Run parser verification**
Create a runner script to execute verification and ensure parser logic matches actual files.

**Step 4: Commit**
```bash
git add src/parser.py tests/test_parser.py
git commit -m "feat: implement statement parser and tests for cleaning data"
```

---

### Task 3: Implement the Mapping Manager

**Files:**
- Create: `src/mapping.py`
- Modify: `vendor_mappings.json`

**Step 1: Write mapping utility code**
We need a class/module to:
1. Load `vendor_mappings.json`.
2. Apply exact match rules (e.g. `q130619719@ybl` -> `Ramchandra Mahaling`).
3. Apply pattern match rules (e.g. if UPI ID or transaction detail contains "datta" -> `Shri Datta Mart`).
4. Support updates to mappings and saving them back to the JSON file.

```python
import json
import os

class MappingManager:
    # Logic to load, map UPI/Details to Vendor, and save mappings
```

**Step 2: Write tests for MappingManager**
Test exact matching, pattern matching, and configuration persistence.

**Step 3: Commit**
```bash
git add src/mapping.py
git commit -m "feat: implement mapping manager to resolve and persist unified vendor names"
```

---

### Task 4: Build the Streamlit Frontend

**Files:**
- Create: `app.py`
- Create: `src/styles.py`

**Step 1: Write Custom Premium CSS Styling**
We will implement a premium layout in Streamlit using a custom theme, CSS injections for card designs, beautiful font weights, and rounded corners (following the high design aesthetic rules).

**Step 2: Streamlit Application Layout**
1. **Sidebar**: Statement folder selector, toggle options (Exclude/Include Self Transfers, Exclude/Include Blocked Mandates), Date Range filters.
2. **Dashboard Tab**:
   - Metric cards: Total Outflow, Total Inflow, Net Cashflow, Average Transaction.
   - Plotly Bar Chart: Monthly Income vs Expenses.
   - Plotly Pie Chart: Expenses by Category (Tags).
   - Plotly Bar Chart: Top 15 Vendors by Expense.
3. **Vendor Mapping Tab**:
   - An interactive table displaying all unique UPI IDs, their transaction count, total amount, and resolved Vendor.
   - A form to map selected UPI IDs to a unified vendor name and save it, instantly updating the visuals.
4. **Transaction Explorer Tab**:
   - Data editor/table of all transactions with sorting and search filters.

**Step 3: Commit**
```bash
git add app.py src/styles.py
git commit -m "feat: implement streamlit user interface with dashboards, charts, and vendor mapping manager"
```

---

### Task 5: End-to-End Verification & Launch

**Files:**
- Create: `run.ps1` (Convenient powershell script to execute `uv run streamlit run app.py`)
- Create: `README.md`

**Step 1: Test with real statements**
Verify that all 10 Excel files load correctly and that the UI maps multiple UPI IDs for "Shri Datta Mart", "Jio / Myjio", etc. correctly.

**Step 2: Commit and write docs**
```bash
git add run.ps1 README.md
git commit -m "feat: add local run script and project documentation"
```
