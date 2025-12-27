import streamlit as st
import pandas as pd
import duckdb

# --- 1. PAGE CONFIGURATION & DARK MODE FIX ---
st.set_page_config(page_title="IC Task Tracker", layout="wide", initial_sidebar_state="expanded")

# This Custom CSS specifically targets the "Cards" to make them Dark Grey instead of White
st.markdown("""
<style>
    /* Force the background of metric cards to be dark grey */
    div[data-testid="metric-container"] {
        background-color: #262730;
        border: 1px solid #464b5c;
        padding: 5% 5% 5% 10%;
        border-radius: 10px;
        border-left: 0.5rem solid #E694FF; /* Purple accent to match your theme */
        color: white;
    }
    
    /* Force text inside metrics to be white */
    div[data-testid="metric-container"] label {
        color: #FAFAFA;
    }
    
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #FAFAFA;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SIDEBAR & ADMIN AUTH ---
st.sidebar.title("Navigation")
admin_password = st.sidebar.text_input("Admin Password (Try '1234')", type="password")
is_admin = admin_password == "1234"

if is_admin:
    st.sidebar.success("🔓 Admin Access Granted")
else:
    st.sidebar.info("🔒 Restricted Access")

# --- 3. MAIN APP LOGIC ---
st.title("IC Task Tracker & Analytics")

# File Uploader
uploaded_file = st.file_uploader("Upload your Task Data (Excel/CSV)", type=['csv', 'xlsx'])

if uploaded_file:
    # Load Data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # Attempt to fix dates automatically
    if 'Journal Date' in df.columns:
        df['Journal Date'] = pd.to_datetime(df['Journal Date'], format='%d/%b/%Y', errors='coerce')

    # Create Tabs for different tools
    tab1, tab2 = st.tabs(["📊 Admin Dashboard", "💻 SQL Tool"])

    # ==========================================
    # TAB 1: ADMIN DASHBOARD (Drill-Down)
    # ==========================================
    with tab1:
        if is_admin:
            st.header("Drill-Down Analysis")
            
            # A. Date Filter
            available_dates = sorted(df['Journal Date'].dropna().dt.date.unique())
            selected_date = st.selectbox("1. Select Date", available_dates)
            
            # Filter data for that day
            day_data = df[df['Journal Date'].dt.date == selected_date]
            
            # B. The Metrics (The Cards)
            # We calculate real numbers from your uploaded data
            total_trans = day_data['Number of Transaction'].sum() if 'Number of Transaction' in day_data.columns else 0
            total_findings = day_data['Number of Findings'].sum() if 'Number of Findings' in day_data.columns else 0
            active_branches = day_data['Branch'].nunique() if 'Branch' in day_data.columns else 0
            active_staff = day_data['Employee'].nunique() if 'Employee' in day_data.columns else 0

            # Display the cards (These will now be Dark Grey because of the CSS at the top)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Transactions", f"{total_trans:,.0f}")
            col2.metric("Total Findings", f"{total_findings}")
            col3.metric("Branches Active", f"{active_branches}")
            col4.metric("Staff Working", f"{active_staff}")
            
            st.divider()

            # C. Branch Drill-Down
            st.subheader("2. Detailed Branch Inspection")
            if 'Branch' in day_data.columns:
                target_branch = st.selectbox("Select Branch", day_data['Branch'].unique())
                branch_view = day_data[day_data['Branch'] == target_branch]
                
                st.write(f"Tasks for **{target_branch}**:")
                st.dataframe(branch_view, use_container_width=True)
            else:
                st.warning("Column 'Branch' not found in data.")
        
        else:
            st.warning("Please enter the Admin Password in the sidebar to view the Dashboard.")

    # ==========================================
    # TAB 2: SQL TOOL (DuckDB)
    # ==========================================
    with tab2:
        st.header("SQL Query Tool")
        st.markdown("Use `df` as your table name. Example: `SELECT * FROM df LIMIT 5`")
        
        # Default query based on your columns
        default_q = 'SELECT Branch, SUM("Number of Transaction") as Total FROM df GROUP BY Branch'
        
        query = st.text_area("Write SQL here:", value=default_q, height=150)
        
        if st.button("Run SQL Command"):
            try:
                result = duckdb.query(query).to_df()
                st.success("Query Successful")
                st.dataframe(result, use_container_width=True)
            except Exception as e:
                st.error(f"SQL Error: {e}")

else:
    st.info("👋 Please upload a CSV or Excel file to begin.")
