import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

from src.parser import load_all_statements, clean_amount
from src.mapping import MappingManager
from src.styles import apply_custom_styles, render_metric_card

# Page Config
st.set_page_config(
    page_title="UPI Spending Analyzer",
    page_icon="💵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply premium styling
apply_custom_styles()

# Constants
DEFAULT_STATEMENTS_DIR = r"D:\03 Permanent Personal Data\01 Expences\UPI_Statements"
MAPPINGS_FILE = "vendor_mappings.json"

# State Initialization
if 'statements_dir' not in st.session_state:
    st.session_state.statements_dir = DEFAULT_STATEMENTS_DIR

# App Title & Header
st.markdown('<div class="main-title">UPI Spending Analyzer</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Analyze, group, and track your monthly UPI expenses & income</div>', unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
st.sidebar.markdown("### ⚙️ Settings")

# Folder Selection
folder_path = st.sidebar.text_input(
    "UPI Statements Directory",
    value=st.session_state.statements_dir,
    help="Absolute path to the directory containing Paytm statement .xlsx files."
)
st.session_state.statements_dir = folder_path

# Reload Button
reload_data = st.sidebar.button("🔄 Reload Statements", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Filters")

exclude_self_transfers = st.sidebar.checkbox(
    "Exclude Self Transfers",
    value=True,
    help="Exclude bank transfers to own accounts (e.g. transfers between self accounts)."
)

exclude_blocked_mandates = st.sidebar.checkbox(
    "Exclude IPO Mandates",
    value=True,
    help="Exclude blocked and unblocked IPO/Mandate transactions that do not impact actual spend."
)

# ----------------- DATA LOADING -----------------
@st.cache_data(show_spinner=False)
def get_raw_data(folder):
    if not os.path.exists(folder):
        return pd.DataFrame()
    return load_all_statements(folder)

# Load raw statements
with st.spinner("Parsing statement files..."):
    df_raw = get_raw_data(st.session_state.statements_dir)

if reload_data:
    st.cache_data.clear()
    st.rerun()

if df_raw.empty:
    st.warning(f"⚠️ No statements found in the specified directory: `{st.session_state.statements_dir}`. Please verify the folder contains Paytm statement `.xlsx` files.")
    st.stop()

# Initialize mapping manager
mapping_manager = MappingManager(MAPPINGS_FILE)

# Apply Vendor Mappings dynamically
df = df_raw.copy()
df['Vendor'] = df.apply(
    lambda row: mapping_manager.resolve_vendor(
        row['Other Transaction Details (UPI ID or A/c No)'], 
        row['DefaultVendor']
    ),
    axis=1
)

# Apply exclusions
if exclude_self_transfers:
    df = df[~df['IsSelfTransfer']]
    
if exclude_blocked_mandates:
    df = df[~df['IsMandate']]

# Date Filter
min_date = df['ParsedDate'].min()
max_date = df['ParsedDate'].max()

if pd.isna(min_date) or pd.isna(max_date):
    min_date = datetime.now()
    max_date = datetime.now()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Filter by selected date range
if len(date_range) == 2:
    start_dt, end_dt = date_range
    df = df[(df['ParsedDate'].dt.date >= start_dt) & (df['ParsedDate'].dt.date <= end_dt)]

# ----------------- MAIN TABS -----------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "🔍 Spend Breakdown", "🔄 Comparison & Trends", "⚙️ Vendor Mapping Manager", "🔍 Transaction Explorer"])

with tab1:
    # ----------------- METRICS -----------------
    inflow = df[df['AmountNumeric'] > 0]['AmountNumeric'].sum()
    # Outflow is negative, so sum of negative is negative. Make it positive for display
    outflow = abs(df[df['AmountNumeric'] < 0]['AmountNumeric'].sum())
    net_savings = inflow - outflow
    savings_rate = (net_savings / inflow * 100) if inflow > 0 else 0.0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card(
            title="Total Outflow (Expense)",
            value=f"₹{outflow:,.2f}",
            value_type="expense",
            subtitle=f"{df[df['AmountNumeric'] < 0].shape[0]} transactions"
        )
    with col2:
        render_metric_card(
            title="Total Inflow (Income)",
            value=f"₹{inflow:,.2f}",
            value_type="income",
            subtitle=f"{df[df['AmountNumeric'] > 0].shape[0]} transactions"
        )
    with col3:
        render_metric_card(
            title="Net Cashflow",
            value=f"₹{net_savings:,.2f}" if net_savings >= 0 else f"-₹{abs(net_savings):,.2f}",
            value_type="net" if net_savings >= 0 else "expense",
            subtitle="Inflow - Outflow",
            delta=f"{'+' if net_savings >= 0 else ''}₹{net_savings:,.0f}",
            delta_positive=(net_savings >= 0)
        )
    with col4:
        render_metric_card(
            title="Savings Rate",
            value=f"{savings_rate:.1f}%",
            value_type="savings",
            subtitle="Percentage of income saved",
            delta=f"Positive Cashflow" if savings_rate >= 0 else "Net Deficit",
            delta_positive=(savings_rate >= 0)
        )
        
    st.markdown("---")
    
    # ----------------- CHARTS -----------------
    chart_col1, chart_col2 = st.columns(2)
    
    # Chart 1: Monthly Income vs Expense
    with chart_col1:
        st.markdown("### 📈 Monthly Cashflow Trend")
        df_monthly = df.copy()
        df_monthly['YearMonth'] = df_monthly['ParsedDate'].dt.to_period('M').astype(str)
        
        monthly_summary = df_monthly.groupby('YearMonth').agg(
            Income=('AmountNumeric', lambda x: x[x > 0].sum()),
            Expense=('AmountNumeric', lambda x: abs(x[x < 0].sum()))
        ).reset_index()
        
        fig_monthly = go.Figure()
        fig_monthly.add_trace(go.Bar(
            x=monthly_summary['YearMonth'],
            y=monthly_summary['Income'],
            name='Income',
            marker_color='#10b981'
        ))
        fig_monthly.add_trace(go.Bar(
            x=monthly_summary['YearMonth'],
            y=monthly_summary['Expense'],
            name='Expense',
            marker_color='#f43f5e'
        ))
        
        fig_monthly.update_layout(
            barmode='group',
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False),
            yaxis=dict(title='Amount in ₹', gridcolor='#334155'),
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", y=1.05, x=0.01)
        )
        st.plotly_chart(fig_monthly, use_container_width=True)

    # Chart 2: Category Breakdown
    with chart_col2:
        st.markdown("### 🛍️ Expenses by Category")
        df_expenses = df[df['AmountNumeric'] < 0]
        category_summary = df_expenses.groupby('CleanTag')['AmountNumeric'].agg(lambda x: abs(x.sum())).reset_index()
        category_summary = category_summary.rename(columns={'AmountNumeric': 'Spent'})
        category_summary = category_summary.sort_values(by='Spent', ascending=False)
        
        if not category_summary.empty:
            fig_pie = px.pie(
                category_summary,
                values='Spent',
                names='CleanTag',
                color_discrete_sequence=px.colors.qualitative.Pastel,
                hole=0.4
            )
            fig_pie.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(orientation="v", y=0.5, x=0.85)
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No expense data available for the selected filters.")

    st.markdown("---")
    
    # Chart 3: Top Vendors
    st.markdown("### 🏢 Top Vendors by Expense")
    df_vendors = df[df['AmountNumeric'] < 0]
    vendor_summary = df_vendors.groupby('Vendor')['AmountNumeric'].agg(lambda x: abs(x.sum())).reset_index()
    vendor_summary = vendor_summary.rename(columns={'AmountNumeric': 'Spent'})
    vendor_summary = vendor_summary.sort_values(by='Spent', ascending=True).tail(15) # Ascending for horizontal bar
    
    if not vendor_summary.empty:
        fig_vendor = px.bar(
            vendor_summary,
            x='Spent',
            y='Vendor',
            orientation='h',
            color='Spent',
            color_continuous_scale=['#818cf8', '#6366f1', '#4f46e5'],
            labels={'Spent': 'Total Spent (₹)', 'Vendor': 'Merchant / Vendor'}
        )
        fig_vendor.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='#334155'),
            yaxis=dict(showgrid=False),
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_vendor, use_container_width=True)
    else:
        st.info("No vendor spend data available.")

with tab2:
    st.markdown("### 🔍 Hierarchical Spend Breakdown")
    st.write("Drill down into your spending by month, then by category, and finally by vendor.")
    
    df_exp = df[df['AmountNumeric'] < 0].copy()
    if not df_exp.empty:
        df_exp['YearMonth'] = df_exp['ParsedDate'].dt.to_period('M').astype(str)
        
        # Get unique months in sorted order (newest first)
        available_months = sorted(df_exp['YearMonth'].unique(), reverse=True)
        
        selected_month = st.selectbox("📅 Select Month", options=available_months, key="drilldown_month_sel")
        
        # Filter for selected month
        df_month = df_exp[df_exp['YearMonth'] == selected_month]
        total_month_spend = abs(df_month['AmountNumeric'].sum())
        
        st.markdown(f"#### Total Spending in {selected_month}: **₹{total_month_spend:,.2f}**")
        
        # Hierarchical Sunburst Chart
        st.markdown("##### 🎯 Category & Vendor Sunburst")
        fig_sun = px.sunburst(
            df_month,
            path=['CleanTag', 'Vendor'],
            values=df_month['AmountNumeric'].abs(),
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_sun.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig_sun, use_container_width=True)
        
        st.markdown("---")
        
        # Step-by-Step Drilldown Columns
        st.markdown("##### 🗂️ Step-by-Step Analysis")
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.markdown("**1. Category Breakdown**")
            cat_spend = df_month.groupby('CleanTag')['AmountNumeric'].agg(lambda x: abs(x.sum())).reset_index()
            cat_spend = cat_spend.rename(columns={'AmountNumeric': 'Spent'})
            cat_spend['% of Month'] = (cat_spend['Spent'] / total_month_spend) * 100
            cat_spend = cat_spend.sort_values(by='Spent', ascending=False)
            
            st.dataframe(
                cat_spend,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Spent": st.column_config.NumberColumn("Spent", format="₹%.2f"),
                    "% of Month": st.column_config.NumberColumn("% of Month", format="%.1f%%")
                }
            )
            
            # Select Category to drill down
            selected_cat = st.selectbox(
                "Select Category to view Vendors",
                options=cat_spend['CleanTag'].unique(),
                key="drilldown_cat_sel"
            )
            
        with col_d2:
            st.markdown(f"**2. Vendor Spend in *{selected_cat}***")
            df_cat = df_month[df_month['CleanTag'] == selected_cat]
            
            vendor_spend = df_cat.groupby('Vendor').agg(
                Spent=('AmountNumeric', lambda x: abs(x.sum())),
                Count=('AmountNumeric', 'count')
            ).reset_index()
            
            total_cat_spend = abs(df_cat['AmountNumeric'].sum())
            vendor_spend['% of Category'] = (vendor_spend['Spent'] / total_cat_spend) * 100
            vendor_spend = vendor_spend.sort_values(by='Spent', ascending=False)
            
            st.markdown(f"Total spent in {selected_cat}: **₹{total_cat_spend:,.2f}**")
            st.dataframe(
                vendor_spend,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Spent": st.column_config.NumberColumn("Spent", format="₹%.2f"),
                    "% of Category": st.column_config.NumberColumn("% of Category", format="%.1f%%"),
                    "Count": "Txn Count"
                }
            )
    else:
        st.info("No expense data available for hierarchical spend breakdown.")

with tab3:
    st.markdown("### 🔄 Comparison & Trends")
    st.write("Compare category-wise and vendor-wise expenses over past months, or perform a direct comparison between two specific months.")
    
    df_comp = df[df['AmountNumeric'] < 0].copy()
    if not df_comp.empty:
        df_comp['YearMonth'] = df_comp['ParsedDate'].dt.to_period('M').astype(str)
        available_months = sorted(df_comp['YearMonth'].unique(), reverse=True)
        
        comp_mode = st.radio("Select Comparison Mode", ["📈 Item Trend (Historical)", "🆚 Month vs Month (Audit)"], horizontal=True)
        
        if comp_mode == "📈 Item Trend (Historical)":
            st.markdown("#### Analyze Category or Vendor over Time")
            col_t1, col_t2 = st.columns([1, 2])
            
            with col_t1:
                item_type = st.selectbox("Analyze by", ["Category", "Vendor"], key="trend_item_type")
                if item_type == "Category":
                    item_list = sorted(df_comp['CleanTag'].unique())
                    selected_item = st.selectbox("Select Category", options=item_list, key="trend_selected_cat")
                    filter_col = 'CleanTag'
                else:
                    item_list = sorted(df_comp['Vendor'].unique())
                    selected_item = st.selectbox("Select Vendor", options=item_list, key="trend_selected_vendor")
                    filter_col = 'Vendor'
            
            # Filter data for selected category/vendor
            df_item = df_comp[df_comp[filter_col] == selected_item]
            
            # Group by Month
            item_monthly = df_item.groupby('YearMonth')['AmountNumeric'].agg(
                Spent=lambda x: abs(x.sum()),
                Count='count'
            ).reset_index()
            
            # Ensure all available months are represented (even if 0 spend)
            all_months_df = pd.DataFrame({'YearMonth': available_months})
            item_monthly = pd.merge(all_months_df, item_monthly, on='YearMonth', how='left').fillna(0.0)
            item_monthly = item_monthly.sort_values(by='YearMonth', ascending=True) # Chronological for charts
            
            # Calculate Month-over-Month changes
            item_monthly['Change (₹)'] = item_monthly['Spent'].diff()
            item_monthly['% Change'] = item_monthly['Spent'].pct_change() * 100
            
            with col_t2:
                # Plotly Chart
                fig_trend = px.bar(
                    item_monthly,
                    x='YearMonth',
                    y='Spent',
                    text_auto='.0f',
                    labels={'Spent': 'Amount Spent (₹)', 'YearMonth': 'Month'},
                    color='Spent',
                    color_continuous_scale=['#818cf8', '#6366f1', '#4f46e5']
                )
                fig_trend.update_layout(
                    template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False),
                    yaxis=dict(gridcolor='#334155'),
                    margin=dict(l=0, r=0, t=10, b=0),
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_trend, use_container_width=True)
                
            st.markdown("##### 📜 Historical Comparison Details")
            # Sort back for table (newest first)
            table_display = item_monthly.sort_values(by='YearMonth', ascending=False)
            st.dataframe(
                table_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Spent": st.column_config.NumberColumn("Spent", format="₹%.2f"),
                    "Change (₹)": st.column_config.NumberColumn("MoM Change (₹)", format="₹%.2f"),
                    "% Change": st.column_config.NumberColumn("MoM Change (%)", format="%.1f%%"),
                    "Count": "Txn Count"
                }
            )
            
        else: # Month vs Month Audit
            st.markdown("#### Direct Comparison of Two Specific Months")
            col_a1, col_a2, col_a3 = st.columns([1, 1, 1])
            
            with col_a1:
                base_month = st.selectbox("Select Base Month (Past)", options=available_months, index=min(1, len(available_months)-1), key="audit_base_month")
            with col_a2:
                target_month = st.selectbox("Select Target Month (Recent)", options=available_months, index=0, key="audit_target_month")
            with col_a3:
                audit_type = st.selectbox("Compare by", ["Category", "Vendor"], key="audit_type_sel")
                
            # Filter data for both months
            df_base = df_comp[df_comp['YearMonth'] == base_month]
            df_target = df_comp[df_comp['YearMonth'] == target_month]
            
            group_col = 'CleanTag' if audit_type == "Category" else 'Vendor'
            
            # Aggregate spent for base month
            base_agg = df_base.groupby(group_col)['AmountNumeric'].agg(lambda x: abs(x.sum())).reset_index()
            base_agg = base_agg.rename(columns={'AmountNumeric': f'Spent_{base_month}'})
            
            # Aggregate spent for target month
            target_agg = df_target.groupby(group_col)['AmountNumeric'].agg(lambda x: abs(x.sum())).reset_index()
            target_agg = target_agg.rename(columns={'AmountNumeric': f'Spent_{target_month}'})
            
            # Merge both aggregations
            audit_df = pd.merge(base_agg, target_agg, on=group_col, how='outer').fillna(0.0)
            
            # Calculate changes
            audit_df['Change (₹)'] = audit_df[f'Spent_{target_month}'] - audit_df[f'Spent_{base_month}']
            
            def safe_pct(row):
                base_val = row[f'Spent_{base_month}']
                tgt_val = row[f'Spent_{target_month}']
                if base_val == 0.0:
                    return 100.0 if tgt_val > 0 else 0.0
                return (row['Change (₹)'] / base_val) * 100
                
            audit_df['% Change'] = audit_df.apply(safe_pct, axis=1)
            
            # Sort by absolute difference
            audit_df = audit_df.sort_values(by=f'Spent_{target_month}', ascending=False)
            
            # Chart Comparison
            # Melt for grouped bar chart
            melted_df = audit_df.melt(
                id_vars=[group_col],
                value_vars=[f'Spent_{base_month}', f'Spent_{target_month}'],
                var_name='MonthGroup',
                value_name='Spent'
            )
            melted_df['MonthGroup'] = melted_df['MonthGroup'].apply(lambda x: base_month if base_month in x else target_month)
            
            fig_compare = px.bar(
                melted_df.head(30), # limit to top 15 pairs for readability
                x=group_col,
                y='Spent',
                color='MonthGroup',
                barmode='group',
                labels={'Spent': 'Amount Spent (₹)', group_col: audit_type},
                color_discrete_map={base_month: '#818cf8', target_month: '#10b981'}
            )
            fig_compare.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(tickangle=-45, gridcolor='rgba(0,0,0,0)'),
                yaxis=dict(gridcolor='#334155'),
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", y=1.05, x=0.01)
            )
            st.plotly_chart(fig_compare, use_container_width=True)
            
            st.markdown(f"##### 📊 Comparison Table: {base_month} vs {target_month}")
            st.dataframe(
                audit_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    f"Spent_{base_month}": st.column_config.NumberColumn(f"Spent in {base_month} (₹)", format="₹%.2f"),
                    f"Spent_{target_month}": st.column_config.NumberColumn(f"Spent in {target_month} (₹)", format="₹%.2f"),
                    "Change (₹)": st.column_config.NumberColumn("Difference (₹)", format="₹%.2f"),
                    "% Change": st.column_config.NumberColumn("Difference (%)", format="%.1f%%")
                }
            )
    else:
        st.info("No expense data available for comparison analysis.")

with tab4:
    st.markdown("### ⚙️ UPI-to-Vendor Mapping Manager")
    st.write(
        "Paytm UPI statements often list different payment IDs for the same merchant "
        "(for example, multiple temporary UPI IDs for *Shri Datta Mart*). "
        "Use this tab to map those duplicate IDs or text patterns to a unified merchant name."
    )
    
    # Form to add new mapping
    st.markdown("#### ➕ Add New Mapping Rule")
    mapping_type = st.radio("Mapping Method", ["Exact UPI Match", "Keyword / Pattern Match"], horizontal=True)
    
    col_m1, col_m2, col_m3 = st.columns([2, 2, 1])
    
    with col_m1:
        if mapping_type == "Exact UPI Match":
            input_val = st.text_input("UPI ID (e.g. `paytm.s15cg9m@pty`)", placeholder="Exact UPI ID")
        else:
            input_val = st.text_input("Pattern / Keyword (e.g. `datta` or `blinkit`)", placeholder="Keyword to search in UPI/Details")
            
    with col_m2:
        target_vendor = st.text_input("Map to Vendor Name (e.g. `Shri Datta Mart`)", placeholder="Unified Vendor Name")
        
    with col_m3:
        st.write("") # Spacing
        st.write("") # Spacing
        save_mapping = st.button("💾 Save Rule", use_container_width=True)
        
    if save_mapping:
        if not input_val or not target_vendor:
            st.error("Please fill in both the input value and the target vendor name.")
        else:
            if mapping_type == "Exact UPI Match":
                mapping_manager.add_exact_mapping(input_val, target_vendor)
                st.success(f"Success! Exact match mapping added: `{input_val}` ➡️ `{target_vendor}`")
            else:
                mapping_manager.add_pattern_mapping(input_val, target_vendor)
                st.success(f"Success! Pattern match mapping added: containing `{input_val}` ➡️ `{target_vendor}`")
            
            # Clear cache and reload
            st.cache_data.clear()
            st.rerun()
            
    st.markdown("---")
    
    # Display Current Rules
    st.markdown("#### 📜 Active Mapping Rules")
    
    rule_col1, rule_col2 = st.columns(2)
    
    with rule_col1:
        st.markdown("**Exact UPI Mappings**")
        if mapping_manager.exact_mappings:
            exact_df = pd.DataFrame([
                {"UPI ID": k, "Unified Vendor": v} 
                for k, v in mapping_manager.exact_mappings.items()
            ])
            st.dataframe(exact_df, use_container_width=True, hide_index=True)
            
            # Delete exact mapping
            to_delete_exact = st.selectbox("Select Exact Mapping to Delete", options=list(mapping_manager.exact_mappings.keys()), key="del_exact_sel")
            if st.button("🗑️ Delete Exact Rule", key="del_exact_btn"):
                if mapping_manager.remove_exact_mapping(to_delete_exact):
                    st.success("Rule deleted.")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("No exact mappings defined.")
            
    with rule_col2:
        st.markdown("**Keyword / Pattern Mappings**")
        if mapping_manager.pattern_mappings:
            pattern_df = pd.DataFrame([
                {"Pattern": k, "Unified Vendor": v} 
                for k, v in mapping_manager.pattern_mappings.items()
            ])
            st.dataframe(pattern_df, use_container_width=True, hide_index=True)
            
            # Delete pattern mapping
            to_delete_pattern = st.selectbox("Select Pattern Mapping to Delete", options=list(mapping_manager.pattern_mappings.keys()), key="del_pattern_sel")
            if st.button("🗑️ Delete Pattern Rule", key="del_pattern_btn"):
                if mapping_manager.remove_pattern_mapping(to_delete_pattern):
                    st.success("Rule deleted.")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("No pattern mappings defined.")

    st.markdown("---")
    
    # UPI ID Stats and Auto-grouping Helper
    st.markdown("#### 🕵️ UPI ID Inspector")
    st.write(
        "Here are all unique UPI IDs found in your statement along with their count, "
        "total spent/received, and their current resolved Vendor. Use this to identify mappings."
    )
    
    upi_col = 'Other Transaction Details (UPI ID or A/c No)'
    # Group by UPI ID and count
    upi_df_list = []
    unique_upis = df_raw[upi_col].unique()
    for upi in unique_upis:
        if pd.isna(upi) or not str(upi).strip():
            continue
        sub = df_raw[df_raw[upi_col] == upi]
        
        # Clean amount
        cleaned_amounts_info = sub['Amount'].apply(clean_amount)
        sub_amounts = [info[0] for info in cleaned_amounts_info]
        
        total_spent = sum([a for a in sub_amounts if a < 0])
        total_recv = sum([a for a in sub_amounts if a > 0])
        count = len(sub)
        
        default_det = list(sub['DefaultVendor'].unique())[:2]
        current_resolved = mapping_manager.resolve_vendor(upi, sub['DefaultVendor'].iloc[0] if not sub.empty else "")
        
        upi_df_list.append({
            "UPI ID": upi,
            "Count": count,
            "Total Spent": total_spent,
            "Total Received": total_recv,
            "Default Details": ", ".join(default_det),
            "Current Resolved Vendor": current_resolved
        })
        
    upi_stats_df = pd.DataFrame(upi_df_list).sort_values(by="Count", ascending=False)
    st.dataframe(
        upi_stats_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Total Spent": st.column_config.NumberColumn(format="₹%.2f"),
            "Total Received": st.column_config.NumberColumn(format="₹%.2f")
        }
    )

with tab5:
    st.markdown("### 🔍 Transaction Explorer")
    st.write("Browse and filter all parsed transactions.")
    
    # Search Box
    search_q = st.text_input("🔍 Search by Vendor, UPI ID, or Transaction Details", "")
    
    # Filter by Tag
    tag_options = ["All"] + list(df['CleanTag'].unique())
    selected_tag = st.selectbox("Filter by Category Tag", options=tag_options)
    
    # Filter by Type
    type_option = st.radio("Transaction Type", ["All", "Debits (Expenses)", "Credits (Income)"], horizontal=True)
    
    # Filter data
    df_exp = df.copy()
    
    if search_q:
        search_q = search_q.lower()
        df_exp = df_exp[
            df_exp['Vendor'].str.lower().str.contains(search_q, na=False) |
            df_exp['Other Transaction Details (UPI ID or A/c No)'].str.lower().str.contains(search_q, na=False) |
            df_exp['Transaction Details'].str.lower().str.contains(search_q, na=False)
        ]
        
    if selected_tag != "All":
        df_exp = df_exp[df_exp['CleanTag'] == selected_tag]
        
    if type_option == "Debits (Expenses)":
        df_exp = df_exp[df_exp['AmountNumeric'] < 0]
    elif type_option == "Credits (Income)":
        df_exp = df_exp[df_exp['AmountNumeric'] > 0]
        
    # Columns to show
    show_cols = [
        'ParsedDate', 'Time', 'Vendor', 'AmountNumeric', 'CleanTag', 
        'Other Transaction Details (UPI ID or A/c No)', 'Your Account', 'Transaction Details', 'SourceFile'
    ]
    
    st.markdown(f"**Showing {df_exp.shape[0]} transactions**")
    
    # Safe column selection to prevent KeyError if any column is missing
    available_cols = [col for col in show_cols if col in df_exp.columns]
    
    st.dataframe(
        df_exp[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "ParsedDate": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "AmountNumeric": st.column_config.NumberColumn("Amount", format="₹%.2f"),
            "Other Transaction Details (UPI ID or A/c No)": "UPI ID / Account",
            "CleanTag": "Category Tag"
        }
    )

# Footer
st.markdown(
    '<div class="footer">UPI Spending Analyzer | Built with Streamlit & UV package manager</div>', 
    unsafe_allow_html=True
)
