import sqlite3
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import sys
import os

def generate_final_excel():
    db_path = "spending_tracker.db"
    excel_path = "spending_tracker_final.xlsx"
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
        
    conn = sqlite3.connect(db_path)
    
    # 1. Fetch transactions
    query_tx = """
        SELECT 
            t.parsed_date as ParsedDate,
            t.time_str as Time,
            t.transaction_details as Narration,
            t.upi_id_or_acc as [UPI ID / Acc],
            t.amount_numeric as Amount,
            t.source_file as SourceFile
        FROM transactions t
        ORDER BY t.parsed_date DESC, t.time_str DESC
    """
    df_tx = pd.read_sql_query(query_tx, conn)
    
    # Compute DefaultVendor dynamically from Narration
    from src.parser import extract_default_vendor
    df_tx['DefaultVendor'] = df_tx['Narration'].apply(extract_default_vendor)
    
    # 2. Fetch mapping rules
    query_rules = """
        SELECT type, pattern_value, target_vendor_name, priority, enabled 
        FROM mapping_rules 
        WHERE enabled = 1
        ORDER BY priority DESC
    """
    df_rules = pd.read_sql_query(query_rules, conn)
    
    # Separate exact rules and pattern rules
    df_exact_rules = df_rules[df_rules['type'] == 'exact']
    df_pattern_rules = df_rules[df_rules['type'] == 'pattern']
    
    # 3. Fetch vendors and categories
    query_vendors = """
        SELECT v.name as Vendor, c.name as Category 
        FROM vendors v 
        LEFT JOIN categories c ON v.category_id = c.id
        ORDER BY v.name ASC
    """
    df_vendors = pd.read_sql_query(query_vendors, conn)
    
    # 4. Fetch budgets
    query_budgets = """
        SELECT c.name as Category, b.monthly_limit as LimitAmount 
        FROM budgets b 
        JOIN categories c ON b.category_id = c.id
        ORDER BY c.name ASC
    """
    df_budgets = pd.read_sql_query(query_budgets, conn)
    
    conn.close()
    
    # Create Workbook
    wb = openpyxl.Workbook()
    
    # Define styles
    font_family = "Segoe UI"
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid") # Dark Blue
    zebra_fill = PatternFill(start_color="F2F5F8", end_color="F2F5F8", fill_type="solid")  # Very Light Gray Blue
    
    header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    title_font = Font(name=font_family, size=16, bold=True, color="1F497D")
    section_font = Font(name=font_family, size=13, bold=True, color="1F497D")
    bold_font = Font(name=font_family, size=11, bold=True)
    regular_font = Font(name=font_family, size=11)
    kpi_val_font = Font(name=font_family, size=18, bold=True, color="1F497D")
    
    thin_border_side = Side(border_style="thin", color="D9D9D9")
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    
    # ------------------ SHEET 1: DASHBOARD ------------------
    ws_dash = wb.active
    ws_dash.title = "Dashboard"
    ws_dash.views.sheetView[0].showGridLines = True
    
    # Title
    ws_dash["A1"] = "UPI Spending Tracker Pro - Financial Dashboard"
    ws_dash["A1"].font = title_font
    
    ws_dash["A2"] = "Offline spending analytics generated from SQLite database"
    ws_dash["A2"].font = Font(name=font_family, size=11, italic=True)
    
    # KPI Headers
    ws_dash["A4"] = "KPI Metric"
    ws_dash["B4"] = "Value"
    ws_dash["A4"].font = header_font
    ws_dash["A4"].fill = header_fill
    ws_dash["B4"].font = header_font
    ws_dash["B4"].fill = header_fill
    
    kpis = [
        ("Total Income", "=SUMIF(Transactions!E:E, \">0\")"),
        ("Total Expenses", "=ABS(SUMIF(Transactions!E:E, \"<0\"))"),
        ("Net Savings", "=B5-B6"),
        ("Savings Rate", "=IF(B5>0, B7/B5, 0)")
    ]
    
    for idx, (metric, formula) in enumerate(kpis, start=5):
        ws_dash[f"A{idx}"] = metric
        ws_dash[f"B{idx}"] = formula
        ws_dash[f"A{idx}"].font = bold_font
        ws_dash[f"B{idx}"].font = kpi_val_font if metric != "Savings Rate" else bold_font
        ws_dash[f"A{idx}"].border = thin_border
        ws_dash[f"B{idx}"].border = thin_border
        
        if metric == "Savings Rate":
            ws_dash[f"B{idx}"].number_format = "0.0%"
        else:
            ws_dash[f"B{idx}"].number_format = "₹#,##0.00"
            
    # Budget Tracking section
    ws_dash["A11"] = "Category Budgets & Limits"
    ws_dash["A11"].font = section_font
    
    ws_dash["A13"] = "Category"
    ws_dash["B13"] = "Monthly Limit"
    ws_dash["C13"] = "Spent (Current Month)"
    ws_dash["D13"] = "Remaining"
    for col_idx, text in enumerate(["Category", "Monthly Limit", "Spent (Current Month)", "Remaining"], start=1):
        cell = ws_dash.cell(row=13, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        
    row_b = 14
    if not df_budgets.empty:
        for idx, row in df_budgets.iterrows():
            cat = row['Category']
            lim = row['LimitAmount']
            ws_dash.cell(row=row_b, column=1, value=cat).font = regular_font
            ws_dash.cell(row=row_b, column=2, value=lim).font = regular_font
            ws_dash.cell(row=row_b, column=2).number_format = "₹#,##0.00"
            
            spent_formula = f'=ABS(SUMIFS(Transactions!$E$2:$E${len(df_tx)+1}, Transactions!$H$2:$H${len(df_tx)+1}, A{row_b}, Transactions!$E$2:$E${len(df_tx)+1}, "<0"))'
            ws_dash.cell(row=row_b, column=3, value=spent_formula).font = regular_font
            ws_dash.cell(row=row_b, column=3).number_format = "₹#,##0.00"
            
            rem_formula = f'=B{row_b}-C{row_b}'
            ws_dash.cell(row=row_b, column=4, value=rem_formula).font = bold_font
            ws_dash.cell(row=row_b, column=4).number_format = "₹#,##0.00"
            
            for c_idx in range(1, 5):
                ws_dash.cell(row=row_b, column=c_idx).border = thin_border
            row_b += 1
    else:
        ws_dash.cell(row=row_b, column=1, value="No budgets configured in SQLite.").font = regular_font
        ws_dash.merge_cells(start_row=row_b, start_column=1, end_row=row_b, end_column=4)
        ws_dash.cell(row=row_b, column=1).alignment = Alignment(horizontal="center")
        ws_dash.cell(row=row_b, column=1).border = thin_border
        row_b += 1
        
    # Instructions Box
    ws_dash["F4"] = "Excel Tracker Instructions:"
    ws_dash["F4"].font = bold_font
    
    instructions = [
        "• This file is connected live to your SQLite data rules.",
        "• Modifying patterns or categories in the 'Rules' sheet updates transactions instantly.",
        "• To refresh the dashboard charts, right-click any chart/Pivot and click 'Refresh'.",
        "• Column G in 'Transactions' uses INDEX/MATCH array formulas to resolve merchants.",
        "• Column H in 'Transactions' uses VLOOKUP to resolve categories."
    ]
    for idx, inst in enumerate(instructions, start=5):
        ws_dash[f"F{idx}"] = inst
        ws_dash[f"F{idx}"].font = regular_font

    # ------------------ SHEET 2: RULES ------------------
    ws_rules = wb.create_sheet(title="Rules")
    ws_rules.views.sheetView[0].showGridLines = True
    
    # Title
    ws_rules["A1"] = "Merchant & Category Resolution Rules"
    ws_rules["A1"].font = title_font
    
    # Exact UPI Mappings Table (A-B)
    ws_rules["A3"] = "Exact UPI Rules (VLOOKUP)"
    ws_rules["A3"].font = section_font
    ws_rules["A4"] = "UPI ID / Account"
    ws_rules["B4"] = "Resolved Merchant"
    ws_rules["A4"].font = header_font
    ws_rules["A4"].fill = header_fill
    ws_rules["B4"].font = header_font
    ws_rules["B4"].fill = header_fill
    
    row_e = 5
    if not df_exact_rules.empty:
        for idx, row in df_exact_rules.iterrows():
            ws_rules.cell(row=row_e, column=1, value=row['pattern_value']).font = regular_font
            ws_rules.cell(row=row_e, column=2, value=row['target_vendor_name']).font = regular_font
            ws_rules.cell(row=row_e, column=1).border = thin_border
            ws_rules.cell(row=row_e, column=2).border = thin_border
            row_e += 1
    else:
        ws_rules.cell(row=row_e, column=1, value="No exact rules configured.").font = regular_font
        ws_rules.cell(row=row_e, column=1).border = thin_border
        ws_rules.cell(row=row_e, column=2).border = thin_border
        row_e += 1
        
    # Substring Pattern Rules Table (D-F)
    ws_rules["D3"] = "Substring Pattern Rules"
    ws_rules["D3"].font = section_font
    ws_rules["D4"] = "Pattern (Keyword)"
    ws_rules["E4"] = "Resolved Vendor"
    ws_rules["F4"] = "Priority"
    ws_rules["D4"].font = header_font
    ws_rules["D4"].fill = header_fill
    ws_rules["E4"].font = header_font
    ws_rules["E4"].fill = header_fill
    ws_rules["F4"].font = header_font
    ws_rules["F4"].fill = header_fill
    
    row_p = 5
    if not df_pattern_rules.empty:
        for idx, row in df_pattern_rules.iterrows():
            ws_rules.cell(row=row_p, column=4, value=row['pattern_value']).font = regular_font
            ws_rules.cell(row=row_p, column=5, value=row['target_vendor_name']).font = regular_font
            ws_rules.cell(row=row_p, column=6, value=row['priority']).font = regular_font
            ws_rules.cell(row=row_p, column=4).border = thin_border
            ws_rules.cell(row=row_p, column=5).border = thin_border
            ws_rules.cell(row=row_p, column=6).border = thin_border
            row_p += 1
    else:
        ws_rules.cell(row=row_p, column=4, value="No pattern rules configured.").font = regular_font
        ws_rules.cell(row=row_p, column=4).border = thin_border
        ws_rules.cell(row=row_p, column=5).border = thin_border
        ws_rules.cell(row=row_p, column=6).border = thin_border
        row_p += 1
        
    # Vendor to Category Mapping Table (H-I)
    ws_rules["H3"] = "Vendor Categories Mapping"
    ws_rules["H3"].font = section_font
    ws_rules["H4"] = "Resolved Vendor Name"
    ws_rules["I4"] = "Mapped Category"
    ws_rules["H4"].font = header_font
    ws_rules["H4"].fill = header_fill
    ws_rules["I4"].font = header_font
    ws_rules["I4"].fill = header_fill
    
    row_v = 5
    if not df_vendors.empty:
        for idx, row in df_vendors.iterrows():
            ws_rules.cell(row=row_v, column=8, value=row['Vendor']).font = regular_font
            ws_rules.cell(row=row_v, column=9, value=row['Category'] if row['Category'] else "Others").font = regular_font
            ws_rules.cell(row=row_v, column=8).border = thin_border
            ws_rules.cell(row=row_v, column=9).border = thin_border
            row_v += 1
    else:
        ws_rules.cell(row=row_v, column=8, value="No vendors in database.").font = regular_font
        ws_rules.cell(row=row_v, column=8).border = thin_border
        ws_rules.cell(row=row_v, column=9).border = thin_border
        row_v += 1

    # ------------------ SHEET 3: TRANSACTIONS ------------------
    ws_tx = wb.create_sheet(title="Transactions")
    ws_tx.views.sheetView[0].showGridLines = True
    
    headers = [
        "Date", "Time", "Narration", "UPI ID / Acc", "Amount (₹)", 
        "Default Vendor", "Resolved Vendor (Live)", "Category (Live)", "Source File"
    ]
    
    for col_idx, text in enumerate(headers, start=1):
        cell = ws_tx.cell(row=1, column=col_idx, value=text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        
    for row_idx, (_, row) in enumerate(df_tx.iterrows(), start=2):
        parsed_dt = row['ParsedDate']
        if isinstance(parsed_dt, pd.Timestamp):
            date_str = parsed_dt.strftime('%Y-%m-%d')
        else:
            date_str = str(parsed_dt)
            
        time_val = str(row['Time'])
        narr = str(row['Narration'])
        upi = str(row['UPI ID / Acc'] or '')
        amt = float(row['Amount'])
        def_vendor = str(row['DefaultVendor'] or 'Unknown')
        src_file = str(row['SourceFile'] or '')
        
        ws_tx.cell(row=row_idx, column=1, value=date_str).number_format = "YYYY-MM-DD"
        ws_tx.cell(row=row_idx, column=2, value=time_val)
        ws_tx.cell(row=row_idx, column=3, value=narr)
        ws_tx.cell(row=row_idx, column=4, value=upi)
        ws_tx.cell(row=row_idx, column=5, value=amt).number_format = "₹#,##0.00"
        ws_tx.cell(row=row_idx, column=6, value=def_vendor)
        
        resolved_formula = f'=IFERROR(INDEX(Rules!$E$5:$E$300, MATCH(1, INDEX((Rules!$D$5:$D$300<>"") * ISNUMBER(SEARCH(Rules!$D$5:$D$300, C{row_idx})), 0), 0)), F{row_idx})'
        ws_tx.cell(row=row_idx, column=7, value=resolved_formula)
        
        category_formula = f'=IFERROR(VLOOKUP(G{row_idx}, Rules!$H$5:$I$300, 2, FALSE), "Others")'
        ws_tx.cell(row=row_idx, column=8, value=category_formula)
        
        ws_tx.cell(row=row_idx, column=9, value=src_file)
        
        # Formatting rows
        for col_idx in range(1, 10):
            cell = ws_tx.cell(row=row_idx, column=col_idx)
            cell.font = regular_font
            cell.border = thin_border
            if row_idx % 2 == 1:
                cell.fill = zebra_fill
                
            if col_idx in [1, 2, 9]:
                cell.alignment = Alignment(horizontal="center")
            elif col_idx == 5:
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left")
                
    # Auto adjust column widths for all sheets
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or '')
                if val_str.startswith('='):
                    val_str = "Resolved Vendor Name Example" 
                max_len = max(max_len, len(val_str))
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)
            
    wb.save(excel_path)
    print(f"Final Excel populated successfully at: {excel_path}")

if __name__ == "__main__":
    generate_final_excel()
