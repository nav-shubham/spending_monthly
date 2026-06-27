# 💵 UPI Spending Analyzer

A premium, interactive dashboard application built with **Streamlit** and **Python** to analyze monthly UPI statements. It parses your transaction history, merges duplicate UPI IDs belonging to the same merchants, and provides details about your cashflow, savings rate, and category-wise spending.

## 🚀 Key Features

- **Automatic Statement Parser**: Parses Paytm `.xlsx` export files directly.
- **Unified Vendor Resolution**: Automatically cleans prefixes and aggregates multiple temporary UPI IDs belonging to the same merchant under a single canonical name.
- **Dynamic Vendor Mappings**: Add new exact UPI matches or keyword patterns directly from the user interface. These mappings are saved to `vendor_mappings.json`.
- **Rich Interactive Dashboards**:
  - Outflow (Expense) and Inflow (Income) metric cards.
  - Interactive charts for monthly trend cashflow, category breakdown (tags), and top merchant vendors.
- **Filters**:
  - Filter transactions by custom date range, transaction type, or category tag.
  - Quick toggles to exclude self-transfers (internal movements) or blocked money (such as IPO mandates).
- **Searchable Transaction Explorer**: Search and browse your parsed statements with full text query support.

## 📦 Tech Stack

- Python 3.12+
- Streamlit
- Pandas
- Plotly
- Openpyxl
- uv (Python project and package manager)

## 🏃 How to Run

To run the application, simply launch the PowerShell script or execute the Streamlit run command:

### Option A: Using the launch script (Windows)
Double-click or run:
```powershell
./run.ps1
```

### Option B: Using the terminal
Run the following command in the project directory:
```bash
uv run streamlit run app.py
```

## ⚙️ Configuration

- **Data Directory**: By default, the application scans the directory `D:\03 Permanent Personal Data\01 Expences\UPI_Statements` for files matching `*.xlsx`. You can change this path directly in the application sidebar.
- **Mappings**: Vendor naming rules are stored in `vendor_mappings.json` in the root of the workspace directory.
