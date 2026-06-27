import streamlit as st

def apply_custom_styles():
    """
    Applies custom CSS styling to the Streamlit app to create a premium,
    visually stunning dark interface.
    """
    custom_css = """
    <style>
        /* Import Google Font */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
        
        /* Apply Font Globally */
        html, body, [class*="css"], .stApp {
            font-family: 'Outfit', sans-serif;
            background-color: #0b0f19;
            color: #e2e8f0;
        }
        
        /* Style Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #0f172a;
            border-right: 1px solid #1e293b;
        }
        
        /* Style Main Cards */
        .premium-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.3);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .premium-card:hover {
            transform: translateY(-2px);
            border-color: #6366f1;
        }
        
        /* Titles and Headers */
        .main-title {
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(to right, #818cf8, #3b82f6, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
            letter-spacing: -0.05em;
        }
        .subtitle {
            font-size: 1.1rem;
            color: #94a3b8;
            margin-bottom: 30px;
            font-weight: 300;
        }
        
        /* Custom Metric Cards */
        .metric-title {
            font-size: 0.9rem;
            color: #94a3b8;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 6px;
            letter-spacing: -0.03em;
        }
        .metric-value.income {
            color: #10b981;
        }
        .metric-value.expense {
            color: #f43f5e;
        }
        .metric-value.savings {
            color: #3b82f6;
        }
        .metric-value.net {
            color: #f59e0b;
        }
        .metric-subtitle {
            font-size: 0.85rem;
            color: #64748b;
        }
        .metric-delta {
            display: inline-flex;
            align-items: center;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 9999px;
            margin-top: 5px;
        }
        .delta-positive {
            background-color: rgba(16, 185, 129, 0.1);
            color: #10b981;
        }
        .delta-negative {
            background-color: rgba(244, 63, 94, 0.1);
            color: #f43f5e;
        }
        .delta-neutral {
            background-color: rgba(100, 116, 139, 0.1);
            color: #94a3b8;
        }
        
        /* Streamlit Tabs Customization */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #0f172a;
            padding: 8px;
            border-radius: 12px;
            border: 1px solid #1e293b;
        }
        .stTabs [data-baseweb="tab"] {
            height: 40px;
            padding: 0 16px;
            border-radius: 8px;
            color: #94a3b8;
            font-weight: 500;
            background-color: transparent;
            transition: all 0.2s ease;
        }
        .stTabs [aria-selected="true"] {
            background-color: #6366f1 !important;
            color: white !important;
            font-weight: 600;
        }
        
        /* Footer */
        .footer {
            text-align: center;
            color: #475569;
            font-size: 0.85rem;
            margin-top: 60px;
            border-top: 1px solid #1e293b;
            padding-top: 20px;
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

def render_metric_card(title, value, value_type="net", subtitle="", delta=None, delta_positive=True):
    """
    Renders an HTML-styled premium metric card.
    value_type can be: 'income', 'expense', 'savings', 'net'
    """
    delta_html = ""
    if delta:
        delta_class = "delta-positive" if delta_positive else "delta-negative"
        sign = "+" if delta_positive and not str(delta).startswith('+') else ""
        delta_html = f'<div class="metric-delta {delta_class}">{sign}{delta}</div>'
        
    card_html = f"""
    <div class="premium-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value {value_type}">{value}</div>
        <div class="metric-subtitle">{subtitle}</div>
        {delta_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
