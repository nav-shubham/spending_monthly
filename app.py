import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import re
from datetime import datetime

from src.repository import Repository
from src.mapping import MappingManager
from src.services import Services
from src.importer import Importer
from src.analytics import calculate_kpis, calculate_monthly_trends, calculate_top_categories, calculate_top_merchants
from src.subscription import detect_subscriptions
from src.export import generate_csv_export, generate_excel_report
from src.styles import apply_custom_styles, render_metric_card
from src.ai_suggest import get_ai_suggestion

# Page Config
st.set_page_config(
    page_title="UPI Spending Tracker Pro",
    page_icon="💵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply premium styling
apply_custom_styles()

# Constants
DEFAULT_STATEMENTS_DIR = r"D:\03 Permanent Personal Data\01 Expences\UPI_Statements"
DEFAULT_DB_FILE = "spending_tracker.db"

# Session State Initialization
if 'statements_dir' not in st.session_state:
    st.session_state.statements_dir = DEFAULT_STATEMENTS_DIR
if 'db_file' not in st.session_state:
    st.session_state.db_file = DEFAULT_DB_FILE
if 'preview_df' not in st.session_state:
    st.session_state.preview_df = None
if 'preview_filepath' not in st.session_state:
    st.session_state.preview_filepath = None
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = ""

# App Header
st.markdown('<div class="main-title">UPI Spending Tracker Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Focused personal finance manager & rules resolution engine</div>', unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
st.sidebar.markdown("### ⚙️ Configuration")

# DB Selection
db_file = st.sidebar.text_input(
    "SQLite Database File",
    value=st.session_state.db_file,
    help="SQLite database file storing transaction history."
)
st.session_state.db_file = db_file

gemini_key = st.sidebar.text_input(
    "Gemini API Key",
    type="password",
    value=st.session_state.gemini_api_key,
    help="Provide your Gemini API key to enable high-fidelity AI-assisted merchant suggestions."
)
st.session_state.gemini_api_key = gemini_key

# Initialize Service & Repository Layers
repository = Repository(db_file)
mapping_manager = MappingManager(repository)
services = Services(repository, mapping_manager)
importer = Importer(repository, mapping_manager)

# Global Filters
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Global Filters")

exclude_self_transfers = st.sidebar.checkbox(
    "Exclude Self Transfers",
    value=True,
    help="Exclude bank transfers to own accounts."
)

exclude_blocked_mandates = st.sidebar.checkbox(
    "Exclude IPO Mandates",
    value=True,
    help="Exclude IPO block/unblock mandates."
)

# Load base transactions from DB
filters_db = {
    'exclude_self_transfers': exclude_self_transfers,
    'exclude_blocked_mandates': exclude_blocked_mandates
}
df_all = repository.get_transactions_df(filters_db)

# Date Filter Slider / Input
if not df_all.empty:
    min_date = df_all['ParsedDate'].min()
    max_date = df_all['ParsedDate'].max()
    if pd.isna(min_date) or pd.isna(max_date):
        min_date = datetime.now()
        max_date = datetime.now()
        
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date()
    )
    
    # Filter data
    df = df_all.copy()
    if len(date_range) == 2:
        start_dt, end_dt = date_range
        df = df[(df['ParsedDate'].dt.date >= start_dt) & (df['ParsedDate'].dt.date <= end_dt)]
else:
    df = pd.DataFrame()

# Navigation selectors
st.sidebar.markdown("---")
nav_section = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "🔍 Transactions", "🏢 Merchants & Rules", "🛍️ Budgets & Subscriptions", "⚙️ Settings"]
)

# ----------------- SECTION 1: DASHBOARD -----------------
if nav_section == "📊 Dashboard":
    if df.empty:
        st.info("No transaction data loaded. Please import statement files under the Settings section.")
    else:
        kpis = calculate_kpis(df)
        
        # Metric Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            render_metric_card("Total Income", f"₹{kpis['total_inflow']:,.2f}", "income")
        with col2:
            render_metric_card("Total Expenses", f"₹{kpis['total_outflow']:,.2f}", "expense")
        with col3:
            net = kpis['net_cashflow']
            render_metric_card("Net Savings", f"₹{net:,.2f}" if net >= 0 else f"-₹{abs(net):,.2f}", "net" if net >= 0 else "expense")
        with col4:
            render_metric_card("Savings Rate", f"{kpis['savings_rate']:.1f}%", "savings")
            
        st.markdown("---")
        
        # Charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("### 📈 Monthly Cashflow Trend")
            monthly = calculate_monthly_trends(df)
            if not monthly.empty:
                fig_monthly = go.Figure()
                fig_monthly.add_trace(go.Bar(x=monthly['YearMonth'], y=monthly['Income'], name='Income', marker_color='#10b981'))
                fig_monthly.add_trace(go.Bar(x=monthly['YearMonth'], y=monthly['Expense'], name='Expense', marker_color='#f43f5e'))
                fig_monthly.update_layout(
                    barmode='group', template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False), yaxis=dict(title='Amount in ₹', gridcolor='#334155'),
                    margin=dict(l=0, r=0, t=20, b=0)
                )
                st.plotly_chart(fig_monthly, width='stretch')
            else:
                st.info("No trend data available.")
                
        with chart_col2:
            st.markdown("### 🛍️ Top Expenses by Category")
            top_cats = calculate_top_categories(df)
            if not top_cats.empty:
                fig_cats = px.pie(top_cats, values='Spent', names='CleanTag', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_cats.update_layout(
                    template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=0, r=0, t=20, b=0)
                )
                fig_cats.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_cats, width='stretch')
            else:
                st.info("No category data available.")
                
        st.markdown("---")
        
        st.markdown("### 🏢 Top Merchants by Expense")
        top_merchants = calculate_top_merchants(df)
        if not top_merchants.empty:
            # Ascending for horizontal bar
            top_merchants_plot = top_merchants.sort_values(by='Spent', ascending=True)
            fig_merchants = px.bar(
                top_merchants_plot, x='Spent', y='Vendor', orientation='h',
                color='Spent', color_continuous_scale=['#818cf8', '#6366f1', '#4f46e5']
            )
            fig_merchants.update_layout(
                template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(gridcolor='#334155'), yaxis=dict(showgrid=False),
                margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False
            )
            st.plotly_chart(fig_merchants, width='stretch')
        else:
            st.info("No merchant spend data available.")

# ----------------- SECTION 2: TRANSACTIONS -----------------
elif nav_section == "🔍 Transactions":
    st.markdown("### 🔍 Transaction Explorer & Bulk Editor")
    
    if df_all.empty:
        st.info("Please sync statement files to load transactions.")
    else:
        # Multi-filter block
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            q_search = st.text_input("Free-text Search (description/any)", "")
            cats = ["All"] + [c['name'] for c in repository.get_categories()]
            selected_cat = st.selectbox("Category Filter", options=cats)
        with col_f2:
            max_amt = float(df_all['AmountNumeric'].abs().max() + 100)
            amt_range = st.slider("Amount Range (₹)", min_value=0.0, max_value=max_amt, value=(0.0, max_amt))
            direction = st.radio("Direction", ["All", "Debits (Expenses)", "Credits (Income)"], horizontal=True)
        with col_f3:
            unique_vends = ["All"] + repository.get_unique_vendors()
            selected_vendor = st.selectbox("Merchant Filter", options=unique_vends)
            unique_upis = ["All"] + sorted(list(set(df_all['Other Transaction Details (UPI ID or A/c No)'].dropna().tolist())))
            selected_upi = st.selectbox("UPI ID Filter (Autocomplete)", options=unique_upis)
            
        # Apply local filters
        df_filtered = df_all.copy()
        if q_search:
            q = q_search.lower()
            df_filtered = df_filtered[
                df_filtered['Vendor'].str.lower().str.contains(q, na=False) |
                df_filtered['Other Transaction Details (UPI ID or A/c No)'].str.lower().str.contains(q, na=False) |
                df_filtered['Transaction Details'].str.lower().str.contains(q, na=False)
            ]
        if selected_cat != "All":
            df_filtered = df_filtered[df_filtered['CleanTag'] == selected_cat]
        if selected_vendor != "All":
            df_filtered = df_filtered[df_filtered['Vendor'] == selected_vendor]
        if selected_upi != "All":
            df_filtered = df_filtered[df_filtered['Other Transaction Details (UPI ID or A/c No)'] == selected_upi]
        if direction == "Debits (Expenses)":
            df_filtered = df_filtered[df_filtered['AmountNumeric'] < 0]
        elif direction == "Credits (Income)":
            df_filtered = df_filtered[df_filtered['AmountNumeric'] > 0]
        df_filtered = df_filtered[(df_filtered['AmountNumeric'].abs() >= amt_range[0]) & (df_filtered['AmountNumeric'].abs() <= amt_range[1])]
        
        # Display Transaction Table with Multi-Row Selection for Bulk Edits
        st.markdown(f"**Found {df_filtered.shape[0]} transactions**")
        
        # Prepare columns
        show_cols = ['id', 'ParsedDate', 'Time', 'Vendor', 'AmountNumeric', 'CleanTag', 'Other Transaction Details (UPI ID or A/c No)', 'Transaction Details', 'SourceFile']
        available_cols = [c for c in show_cols if c in df_filtered.columns]
        
        # Setup selection
        select_event = st.dataframe(
            df_filtered[available_cols],
            on_select="rerun",
            selection_mode="multi-row",
            width='stretch',
            hide_index=True,
            column_config={
                "id": "ID",
                "ParsedDate": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "AmountNumeric": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f"),
                "CleanTag": "Category",
                "Other Transaction Details (UPI ID or A/c No)": "UPI ID / Acc",
                "Transaction Details": "Narration"
            }
        )
        
        # Handle selection for bulk editing
        selected_indices = select_event.get("selection", {}).get("rows", [])
        
        if selected_indices:
            # Retrieve transaction IDs
            selected_ids = df_filtered.iloc[selected_indices]['id'].tolist()
            st.markdown(f"💼 **Bulk Editor: {len(selected_ids)} rows selected**")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown("**1. Assign Category**")
                bulk_cat = st.selectbox("Bulk Select Category", options=[c['name'] for c in repository.get_categories() if c['name'] != "All"])
                if st.button("🏷️ Bulk Assign Category", width='stretch'):
                    updated = services.bulk_assign_category(selected_ids, bulk_cat)
                    st.success(f"Successfully updated category for {updated} transactions!")
                    st.rerun()
            with col_b2:
                st.markdown("**2. Assign Merchant**")
                all_vends = repository.get_unique_vendors()
                bulk_merchant_opt = st.selectbox("Select Existing Merchant", options=["+ Create New Merchant..."] + all_vends)
                if bulk_merchant_opt == "+ Create New Merchant...":
                    bulk_merchant = st.text_input("New Merchant Name", placeholder="e.g. Swiggy")
                else:
                    bulk_merchant = bulk_merchant_opt
                    
                if st.button("🏢 Bulk Assign Merchant", width='stretch'):
                    if not bulk_merchant or not bulk_merchant.strip():
                        st.error("Please enter a valid merchant name.")
                    else:
                        updated = services.bulk_assign_vendor(selected_ids, bulk_merchant)
                        st.success(f"Successfully updated merchant name for {updated} transactions!")
                        st.rerun()
        else:
            st.info("💡 Pro Tip: Check rows in the table above to bulk-edit category tags or merchant names simultaneously.")

# ----------------- SECTION 3: MERCHANTS & RULES -----------------
elif nav_section == "🏢 Merchants & Rules":
    st.markdown("### 🏢 Merchant Resolution & Rules Manager")
    
    tab_re1, tab_re2, tab_re3 = st.tabs(["⚙️ Rules Engine", "🔀 Merge Merchants", "🔮 AI Suggestion Assistant"])
    
    with tab_re1:
        col_r1, col_r2 = st.columns([1, 2])
        
        with col_r1:
            st.markdown("#### ➕ Add New Resolution Rule")
            r_type = st.radio("Trigger Mode", ["Exact UPI ID", "Keyword Substring", "Regex Expression"])
            
            # Autocomplete Trigger Pattern
            all_upis_list = sorted(list(set(df_all['Other Transaction Details (UPI ID or A/c No)'].dropna().tolist()))) if not df_all.empty else []
            all_def_vends_list = sorted(list(set(df_all['DefaultVendor'].dropna().tolist()))) if not df_all.empty else []
            patt_opts = ["(Custom Entry...)"]
            if r_type == "Exact UPI ID":
                patt_opts.extend(all_upis_list)
            else:
                patt_opts.extend(all_def_vends_list)
                
            sel_patt = st.selectbox("Select/Search Pattern Suggestion", options=patt_opts)
            if sel_patt == "(Custom Entry...)":
                r_val = st.text_input("Pattern / String Value", placeholder="e.g. blinkit")
            else:
                r_val = sel_patt
                
            # Autocomplete Unified Merchant Name
            all_vends = repository.get_unique_vendors()
            target_merchant_opt = st.selectbox("Unified Merchant Name", options=["+ Create New Merchant..."] + all_vends)
            if target_merchant_opt == "+ Create New Merchant...":
                r_target = st.text_input("New Merchant Name", placeholder="e.g. Swiggy")
            else:
                r_target = target_merchant_opt
                
            r_prio = st.slider("Priority Level (1-5)", min_value=1, max_value=5, value=2)
            
            if st.button("💾 Save Rule", width='stretch'):
                if not r_val or not r_val.strip() or not r_target or not r_target.strip():
                    st.error("Rule pattern trigger value and unified merchant name cannot be empty.")
                else:
                    db_type = 'exact' if r_type == "Exact UPI ID" else ('regex' if r_type == "Regex Expression" else 'pattern')
                    success, msg = repository.add_rule(db_type, r_val, r_target, r_prio)
                    if success:
                        st.success("Rule saved successfully!")
                        mapping_manager.refresh_rules_cache()
                        st.rerun()
                    else:
                        st.error(msg)
                    
        with col_r2:
            st.markdown("#### 📜 Active Rules List")
            rules = repository.get_rules()
            if rules:
                rules_df = pd.DataFrame(rules)
                st.dataframe(
                    rules_df[['id', 'type', 'pattern_value', 'target_vendor_name', 'priority', 'enabled']],
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "id": "Rule ID",
                        "type": "Type",
                        "pattern_value": "Trigger Pattern",
                        "target_vendor_name": "Resolved Name",
                        "priority": "Priority",
                        "enabled": "Active"
                    }
                )
                
                col_ro1, col_ro2 = st.columns(2)
                with col_ro1:
                    toggle_id = st.selectbox("Select Rule ID to Toggle State", options=rules_df['id'].tolist())
                    if st.button("🔌 Toggle Active State", width='stretch'):
                        current_st = rules_df[rules_df['id'] == toggle_id]['enabled'].iloc[0]
                        if mapping_manager.toggle_rule(toggle_id, not current_st):
                            st.success("Rule updated.")
                            st.rerun()
                with col_ro2:
                    delete_id = st.selectbox("Select Rule ID to Remove", options=rules_df['id'].tolist(), key="del_rule_box")
                    if st.button("🗑️ Delete Resolution Rule", width='stretch'):
                        if mapping_manager.remove_rule(delete_id):
                            st.success("Rule deleted.")
                            st.rerun()
            else:
                st.info("No mapping rules defined.")

    with tab_re2:
        st.markdown("#### 🔀 Merge Duplicate Merchants")
        st.write("Clean transaction histories by merging multiple vendor profiles under a canonical merchant profile. This creates an automatic keyword resolution rule.")
        
        unique_vendors_list = repository.get_unique_vendors()
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            source_v = st.selectbox("Source Merchant (to merge from)", options=unique_vendors_list)
        with col_m2:
            target_v = st.selectbox("Target Merchant (to keep)", options=unique_vendors_list)
            
        col_mb1, col_mb2 = st.columns(2)
        with col_mb1:
            if st.button("🔀 Merge Merchants", width='stretch'):
                success, msg = services.merge_merchants(source_v, target_v)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with col_mb2:
            # Undo last merge button
            latest_merge = repository.get_latest_merge()
            if latest_merge:
                if st.button(f"⏪ Undo Merge: '{latest_merge['source_vendor']}' ➡️ '{latest_merge['target_vendor']}'", width='stretch'):
                    success, msg = services.undo_last_merchant_merge()
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.button("⏪ Undo Last Merge", disabled=True, width='stretch')

    with tab_re3:
        st.markdown("#### 🔮 Optional AI Suggestion Assistant")
        st.write("Inspects transactions without matching mappings and uses local NLP cleanups or Gemini AI to recommend merchant profiles.")
        
        # Unmapped: Resolved vendor matches default vendor and no rules match
        unmapped_all = df_all[df_all['Vendor'] == df_all['DefaultVendor']]
        
        if not unmapped_all.empty:
            unmapped_summary = unmapped_all.groupby(['Other Transaction Details (UPI ID or A/c No)', 'DefaultVendor']).agg(
                Count=('AmountNumeric', 'count'),
                DetailsSample=('Transaction Details', lambda x: x.iloc[0])
            ).reset_index().sort_values(by='Count', ascending=False)
            
            col_ai1, col_ai2 = st.columns(2)
            with col_ai1:
                labels = [f"{row['DefaultVendor']} ({row['Other Transaction Details (UPI ID or A/c No)']}) - {row['Count']} txns" for _, row in unmapped_summary.iterrows()]
                selected_val = st.selectbox("Select Unmapped Merchant", options=labels)
                
                sel_idx = labels.index(selected_val)
                row_sel = unmapped_summary.iloc[sel_idx]
                
                t_upi = row_sel['Other Transaction Details (UPI ID or A/c No)']
                t_def = row_sel['DefaultVendor']
                t_details = row_sel['DetailsSample']
                
                st.info(f"**UPI:** `{t_upi}`\n\n**Raw Vendor:** `{t_def}`\n\n**Details:** `{t_details}`")
                
            with col_ai2:
                api_key = st.session_state.gemini_api_key if st.session_state.gemini_api_key else None
                with st.spinner("Analyzing data patterns..."):
                    suggestion = get_ai_suggestion(t_upi, t_def, t_details, api_key=api_key)
                    
                st.metric("Suggested Merchant Profile", suggestion["suggested_merchant"])
                st.metric("Confidence Score", f"{suggestion['confidence_score'] * 100:.0f}%")
                st.write(f"**Reasoning:** {suggestion['reason']}")
                
                if st.button("👍 Approve AI Suggestion", width='stretch'):
                    repository.add_rule('exact', t_upi, suggestion["suggested_merchant"], priority=4)
                    st.success("Rule added!")
                    mapping_manager.refresh_rules_cache()
                    st.rerun()
        else:
            st.success("🎉 All merchants in your database are fully resolved under active mapping rules!")

# ----------------- SECTION 4: BUDGETS & SUBSCRIPTIONS -----------------
elif nav_section == "🛍️ Budgets & Subscriptions":
    st.markdown("### 🛍️ Monthly Category Budgets & Subscriptions")
    
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        st.markdown("#### 📊 Budget Adherence Limits")
        
        budgets = repository.get_budgets()
        categories = repository.get_categories()
        cat_names = [c['name'] for c in categories]
        
        # Add limit
        with st.form("budget_limits_form"):
            b_cat = st.selectbox("Category", options=cat_names)
            b_val = st.number_input("Limit (₹)", min_value=0.0, step=500.0, value=float(budgets.get(b_cat, 0.0)))
            
            col_bf1, col_bf2 = st.columns(2)
            with col_bf1:
                save_limit = st.form_submit_button("💾 Save Budget Limit", width='stretch')
            with col_bf2:
                del_limit = st.form_submit_button("🗑️ Remove Limit", width='stretch')
                
            if save_limit:
                if repository.save_budget(b_cat, b_val):
                    st.success(f"Limit for '{b_cat}' saved.")
                    st.rerun()
            if del_limit:
                if repository.delete_budget(b_cat):
                    st.success(f"Limit for '{b_cat}' removed.")
                    st.rerun()
                    
        st.markdown("#### 🎯 Active Budgets Progress")
        now = datetime.now()
        df_cur = df[(df['ParsedDate'].dt.year == now.year) & (df['ParsedDate'].dt.month == now.month) & (df['AmountNumeric'] < 0)]
        cur_cat_spends = df_cur.groupby('CleanTag')['AmountNumeric'].sum().abs().to_dict() if not df_cur.empty else {}
        
        if budgets:
            for cat, limit in budgets.items():
                spent = cur_cat_spends.get(cat, 0.0)
                pct = (spent / limit) if limit > 0 else 0.0
                rem = limit - spent
                
                if pct >= 1.0:
                    st.error(f"🚨 **{cat}**: Overspent! Spent: ₹{spent:,.2f} / Limit: ₹{limit:,.2f} (Over by ₹{abs(rem):,.2f})")
                    pct_val = 1.0
                elif pct >= 0.85:
                    st.warning(f"⚠️ **{cat}**: Near limit! Spent: ₹{spent:,.2f} / Limit: ₹{limit:,.2f} (Remaining: ₹{rem:,.2f})")
                    pct_val = pct
                else:
                    st.info(f"✅ **{cat}**: Spent: ₹{spent:,.2f} / Limit: ₹{limit:,.2f} (Remaining: ₹{rem:,.2f})")
                    pct_val = pct
                st.progress(pct_val)
        else:
            st.info("No budgets configured.")
            
    with col_b2:
        st.markdown("#### 🔄 Recurring Subscriptions Detected")
        st.write("Scans historical debit profiles for periodic repeating transactions.")
        
        subs = detect_subscriptions(df)
        if subs:
            total_annual = sum(s['yearly_cost'] for s in subs)
            st.markdown(f"Estimated Yearly Subscriptions Total: **₹{total_annual:,.2f}**")
            
            subs_df = pd.DataFrame(subs)
            st.dataframe(
                subs_df[['vendor', 'amount', 'frequency', 'yearly_cost', 'missed_payment', 'reason']],
                width='stretch',
                hide_index=True,
                column_config={
                    "vendor": "Vendor Name",
                    "amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f"),
                    "frequency": "Billing Cycle",
                    "yearly_cost": st.column_config.NumberColumn("Yearly Cost (₹)", format="₹%.2f"),
                    "missed_payment": st.column_config.CheckboxColumn("Due / Missed?"),
                    "reason": "Detection Heuristics"
                }
            )
            
            # Show missed warning
            missed = [s for s in subs if s['missed_payment']]
            if missed:
                for ms in missed:
                    st.warning(f"🔔 **Subscription Due Alert**: '{ms['vendor']}' (usually ₹{ms['amount']:,.2f}) appears unpaid in recent cycle.")
        else:
            st.info("No recurring patterns detected.")

# ----------------- SECTION 5: SETTINGS -----------------
elif nav_section == "⚙️ Settings":
    st.markdown("### ⚙️ Settings, Custom Categories, & Imports")
    
    tab_se1, tab_se2, tab_se3 = st.tabs(["📥 Import & Sync Manager", "🗂️ Categories Manager", "🗑️ Danger Zone"])
    
    with tab_se1:
        st.markdown("#### 📥 Incremental Import Scanner")
        st.write("Scan your statements directory for new Excel/CSV statement files and verify contents before importing.")
        
        folder_dir = st.text_input("Statements Folder Path", value=st.session_state.statements_dir)
        st.session_state.statements_dir = folder_dir
        
        if os.path.exists(folder_dir):
            files = [f for f in os.listdir(folder_dir) if f.lower().endswith(('.xlsx', '.xls', '.csv'))]
            if files:
                st.write(f"📁 Found {len(files)} files in folder path:")
                sel_import_file = st.selectbox("Select File to Import", options=files)
                filepath = os.path.join(folder_dir, sel_import_file)
                
                col_imp1, col_imp2 = st.columns(2)
                with col_imp1:
                    # Generate Preview
                    if st.button("🔍 Generate Import Preview", width='stretch'):
                        preview = importer.preview_import(filepath)
                        if preview is not None:
                            st.session_state.preview_df = preview
                            st.session_state.preview_filepath = filepath
                            st.success("Import preview loaded!")
                        else:
                            st.error("Failed to parse statement preview. Check file schema.")
                with col_imp2:
                    # Undo Last Import button
                    latest_import = repository.get_latest_import()
                    if latest_import:
                        if st.button(f"⏪ Undo Import: '{latest_import['filename']}'", width='stretch'):
                            success, msg = importer.undo_last_import()
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.button("⏪ Undo Last Import", disabled=True, width='stretch')
                        
                # Show Preview details and Commit button
                if st.session_state.preview_df is not None and st.session_state.preview_filepath == filepath:
                    df_prev = st.session_state.preview_df
                    st.markdown("##### 🔍 Preview Details (First 15 Rows)")
                    st.dataframe(df_prev.head(15), width='stretch', hide_index=True)
                    
                    st.markdown(f"**Summary:** Total rows to commit: `{len(df_prev)}` transactions.")
                    if st.button("📥 Commit Preview to Database", width='stretch'):
                        success, msg = importer.commit_import(filepath, df_prev)
                        if success:
                            st.success(msg)
                            st.session_state.preview_df = None
                            st.session_state.preview_filepath = None
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                st.warning("No Excel or CSV statement files found in the specified directory.")
        else:
            st.error("Invalid statements folder directory path.")
            
        st.markdown("---")
        st.markdown("#### 📜 Sync History Log")
        history = repository.get_import_history()
        if history:
            st.dataframe(pd.DataFrame(history), width='stretch', hide_index=True)
        else:
            st.info("No import history records found.")

    with tab_se2:
        st.markdown("#### 🗂️ Categories Manager")
        
        categories = repository.get_categories()
        cats_df = pd.DataFrame(categories)
        st.dataframe(cats_df, width='stretch', hide_index=True)
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("**Add Custom Category**")
            new_cat_name = st.text_input("Category Name", placeholder="e.g. Gifts")
            if st.button("➕ Add Category", width='stretch'):
                success, msg = repository.add_category(new_cat_name)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with col_c2:
            st.markdown("**Remove Custom Category**")
            custom_cats = [c for c in categories if not c['is_system']]
            if custom_cats:
                cat_to_del = st.selectbox("Select Custom Category", options=[c['id'] for c in custom_cats], format_func=lambda x: next(c['name'] for c in custom_cats if c['id'] == x))
                if st.button("🗑️ Delete Category", width='stretch'):
                    success, msg = repository.delete_category(cat_to_del)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.write("No custom user categories defined.")

    with tab_se3:
        st.markdown("#### 🚨 Danger Zone")
        st.write("These actions permanently delete database logs. Proceed with caution.")
        
        if st.button("💥 Reset & Clear Database", width='stretch'):
            repository.clear_all_data()
            st.success("All transaction histories, budgets, custom rules, and sync logs deleted.")
            st.rerun()
            
        st.markdown("---")
        # Exporter download links are placed here
        st.markdown("#### 📥 Exports & Offline Backups")
        st.write("Download spreadsheet summaries of transaction datasets currently stored in SQLite:")
        
        if not df.empty:
            # CSV Download
            csv_str = generate_csv_export(df)
            st.download_button("Download CSV Dump", csv_str, file_name="spending_transactions.csv", mime="text/csv", width='stretch')
            
            # Excel Download
            category_summary = df[df['AmountNumeric'] < 0].groupby('CleanTag')['AmountNumeric'].sum().abs().reset_index().rename(columns={'AmountNumeric': 'Spent'})
            monthly_summary = calculate_monthly_trends(df)
            excel_bytes = generate_excel_report(df, monthly_summary, category_summary)
            st.download_button("Download Excel Report", excel_bytes, file_name="spending_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
        else:
            st.info("Import statements to enable Excel/CSV downloads.")

# Footer
st.markdown('<div class="footer">UPI Spending Tracker Pro | Streamlined Personal Finance Management</div>', unsafe_allow_html=True)
