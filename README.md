# 💵 UPI Spending Tracker Pro

UPI Spending Tracker Pro is a production-grade, local-first personal finance management application. It parses monthly UPI statements across multiple payment providers (Paytm, PhonePe, Google Pay, generic CSV/Excel), stores transactions in a normalized SQLite database, resolves merchant profiles using a prioritized rules engine, tracks budgets and subscriptions, and offers streamlined visual insights.

---

## 📐 Architecture & Data Flow

The application follows a strictly decoupled, layered architecture:

```
┌──────────────┐      ┌─────────────┐      ┌───────────────┐
│ Statement    │ ───> │ File Parser │ ───> │  Importer     │
│ Excel / CSV  │      │  (parser)   │      │  (importer)   │
└──────────────┘      └─────────────┘      └───────────────┘
                                                   │
                                                   ▼
┌──────────────┐      ┌─────────────┐      ┌───────────────┐
│  Streamlit   │ <─── │   Services  │ <─── │ Repository    │
│  Dashboard   │      │  (business) │      │ (repository)  │
└──────────────┘      └─────────────┘      └───────────────┘
```

1. **Parser Layer (`src/parser.py`)**: Automatically detects column structures and formats (Paytm, PhonePe, Google Pay, or generic layouts) and normalizes them.
2. **Importer Layer (`src/importer.py`)**: Handles statement validation, duplicate file filtering via SHA-256 integrity hashing, import previews, database commits, and last-import undoing.
3. **Repository Layer (`src/repository.py`)**: Direct SQLite database access, transaction commits, mapping rules, budgets, categories, and merchant merge histories.
4. **Service Layer (`src/services.py`)**: Core business workflows including bulk category/merchant updates, merchant merging, and undoing merchant merges.
5. **Rules Resolver (`src/mapping.py`)**: Resolves merchants by checking exact matches, regexes, and pattern substrings in priority order.
6. **Analytics Engine (`src/analytics.py`)**: Computes core KPIs (Income, Expenses, Net Savings, Savings Rate), monthly trends, top categories, and top merchants.
7. **Subscription Detector (`src/subscription.py`)**: Inspects recurring payment intervals to track monthly/annual subscriptions and flag unpaid dues.
8. **Export Layer (`src/export.py`)**: Generates downloadable multi-sheet Excel reports and CSV dumps.
9. **UI Layer (`app.py` & `src/styles.py`)**: Streamlined dark-themed dashboard.

---

## 🗄️ Database Schema

The persistent SQLite database contains the following normalized structure:

```mermaid
erDiagram
    import_history {
        int id PK
        text filename UNIQUE
        text file_hash
        timestamp import_date
        int transaction_count
    }
    categories {
        int id PK
        text name UNIQUE
        boolean is_system
    }
    vendors {
        int id PK
        text name UNIQUE
        int category_id FK
    }
    mapping_rules {
        int id PK
        text type
        text pattern_value UNIQUE
        text target_vendor_name
        int priority
        boolean enabled
        timestamp created_date
    }
    budgets {
        int id PK
        int category_id FK
        real monthly_limit
    }
    merge_history {
        int id PK
        text source_vendor
        text target_vendor
        text transaction_ids
        int rule_id
        timestamp merge_date
    }
    transactions {
        int id PK
        date parsed_date
        text time_str
        text transaction_details
        text upi_id_or_acc
        text amount_str
        real amount_numeric
        boolean is_negative
        text clean_tag
        boolean is_mandate
        boolean is_self_transfer
        text source_file
        int category_id FK
        int vendor_id FK
        int import_id FK
    }
    categories ||--o{ transactions : "categorizes"
    vendors ||--o{ transactions : "resolves"
    categories ||--o{ vendors : "classifies"
    categories ||--o{ budgets : "restricts"
    import_history ||--o{ transactions : "tracks"
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended package manager)

### Installation
1. Clone the repository or navigate to the project directory.
2. Initialize environment and install dependencies:
   ```bash
   uv sync
   ```

---

## 🏃 User Guide

### Running the App
To start the application:
```bash
uv run streamlit run app.py
```
This boots the local development server (typically at `http://localhost:8501`).

### Importing Statements
1. Go to the **Settings** section.
2. Verify the target directory in **Statements Folder Path**.
3. Select a statement file, click **Generate Import Preview** to inspect, and click **Commit Preview** to load transactions.
4. Click **Undo Import** to revert the last sync if needed.

### Merging & Mapping Merchants
1. Under **Merchants & Rules**, add exact, pattern, or regex rules to map UPI IDs to merchants.
2. Use the **Merge Merchants** tab to combine duplicate profiles. Click **Undo Merge** if you make a mistake.
3. Review unknown merchants in **AI Suggestion Assistant** to approve mappings with 1 click.

---

## 🛠️ Developer Guide

### Running Tests
Run the test suite with:
```bash
uv run pytest
```
All unit tests target the parser, database sync, repo queries, rule resolution, and subscription detection.
