import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATION & VISUALS ---
st.set_page_config(page_title="IC Audit Pro", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
    /* Dark Mode Card Styling */
    div[data-testid="metric-container"] {
        background-color: #262730 !important;
        border: 1px solid #464b5c !important;
        color: #FFFFFF !important;
        border-radius: 10px;
        border-left: 5px solid #E694FF !important;
    }
    div[data-testid="metric-container"] label { color: #FFFFFF !important; }
    div[data-testid="stMetricValue"] { color: #FFFFFF !important; }
    
    /* Expander & Form Styling */
    div[data-testid="stExpander"] { background-color: #262730; border-radius: 10px; }
    .stButton>button { border-radius: 20px; font-weight: bold; }
    
    /* Helper Text Styling */
    .format-note { font-size: 0.8rem; color: #ffbd45; margin-top: -10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONSTANTS ---
BRANCH_OPTIONS = ["HQ", "SUZ", "HUR", "SSH", "LXR", "ASW", "ALX", "CAI", "GIZA", "MANS", "OTHERS"]
TASK_OPTIONS = [
    "Cash Count", "Operation Audit", "Stock Count", "ATM Review", 
    "Log Review", "Documentation Check", "Customer Service Review", "Other"
]

# --- 3. DATABASE FUNCTIONS ---

def get_data():
    """Reads data from Google Sheets with caching and error handling."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        tasks_df = conn.read(worksheet="Tasks", ttl=10)
        users_df = conn.read(worksheet="Users", ttl=10)
        
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        
        # Ensure standard columns exist (Matching your sheet headers EXACTLY)
        # Note: 'Number of Transaction' (Singular based on your screenshot)
        cols_needed = [
            'Employee', 'Task Description', 'Branch', 'Assigned Date', 'Assigned Time',
            'Completion Status', 'Completion Date', 'Completion Time', 'Duration', 'Progress %',
            'Journal Date', 'Number of Findings', 'Number of Transaction'
        ]
        
        for col in cols_needed:
            if col not in tasks_df.columns: tasks_df[col] = 0
            
        return conn, tasks_df, users_df
    except Exception as e:
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    """Safely updates Google Sheets and clears cache."""
    try:
        # 1. CLEANING: Replace "NaN" with empty string
        df = df.fillna("") 
        
        # 2. WRITING: Send data to Google
        conn.update(worksheet=worksheet_name, data=df)
        
        # 3. RESETTING: Clear memory
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠️ Save Error: {e}")
        return False

def calculate_duration(start_date, start_time, end_date, end_time):
    """Calculates time difference between assignment and completion."""
    try:
        fmt = '%d/%b/%Y %I:%M:%S %p'
        if len(str(start_time).split(':')) == 2: start_time = f"{start_time}:00"
        if len(str(end_time).split(':')) == 2: end_time = f"{end_time}:00"
        
        dt_s = datetime.strptime(f"{start_date} {start_time}", fmt)
        dt_e = datetime.strptime(f"{end_date} {end_time}", fmt)
        diff = dt_e - dt_s
        secs = diff.total_seconds()
        return f"{int(secs // 3600)}h {int((secs % 3600) // 60)}m"
    except: return "0h 0m"

# --- 4. MAIN APPLICATION ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_info = None

    conn, tasks_df, users_df = get_data()

    if users_df.empty:
        st.warning("⚠️ **System is cooling down.**")
        st.info("Please wait **60 seconds** and refresh the page to reset the Google Quota.")
        st.stop() 

    # Data Type Cleanups
    users_df['Username'] = users_df['Username'].astype(str)
    users_df['Password'] = users_df['Password'].astype(str)
    
    if not tasks_df.empty:
        # Match column names exactly from your sheet
        if 'Number of Findings' in tasks_df.columns:
            tasks_df['Number of Findings'] = pd.to_numeric(tasks_df['Number of Findings'], errors='coerce').fillna(0)
        if 'Number of Transaction' in tasks_df.columns:
            tasks_df['Number of Transaction'] = pd.to_numeric(tasks_df['Number of Transaction'], errors='coerce').fillna(0)
        
        # Parse Dates
        if 'Journal Date' in tasks_df.columns:
            tasks_df['Journal Date'] = pd.to_datetime(tasks_df['Journal Date'], format='%d/%b/%Y', errors='coerce')
        if 'Assigned Date' in tasks_df.columns:
            tasks_df['Assigned Date'] = pd.to_datetime(tasks_df['Assigned Date'], format='%d/%b/%Y', errors='coerce')

    # --- LOGIN SCREEN ---
    if not st.session_state.logged_in:
        st.markdown("<h1 style='text-align: center;'>🛡️ IC Audit Portal</h1>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login Securely", type="primary"):
                    user = users_df[(users_df['Username'] == u) & (users_df['Password'] == p)]
                    if not user.empty:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user.iloc[0]
                        st.rerun()
                    else: st.error("❌ Access Denied")
        return

    # --- LOGGED IN HEADER ---
    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### 👋 {user['Username']}")
        st.caption(f"Role: {user['Role']}")
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()

    # ==========================================
    # ROLE: ADMIN VIEW
    # ==========================================
    if user['Role'] == 'Admin':
        st.title("📊 Executive Dashboard")
        tabs = st.tabs(["📈 Analytics", "📝 Manage Tasks", "➕ Assign Task", "💻 SQL Tool", "👥 User Mgmt", "📑 Custom Report"])

        # --- TAB 1: ANALYTICS (With Employee Filter & Select All) ---
        with tabs[0]:
            st.header("Drill-Down Analysis")
            if tasks_df.empty:
                st.info("No data available.")
            else:
                # 5 columns for filters
                col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
                df_filtered = tasks_df.copy()
                
                # 1. Journal Date
                with col_f1:
                    if 'Journal Date' in df_filtered.columns:
                        all_j_dates = sorted(df_filtered['Journal Date'].dropna().dt.date.unique())
                        if all_j_dates:
                            sel_j_date = st.selectbox("Journal Date", all_j_dates)
                            df_filtered = df_filtered[df_filtered['Journal Date'].dt.date == sel_j_date]

                # 2. Assigned Date
                with col_f2:
                    if 'Assigned Date' in df_filtered.columns:
                        all_a_dates = sorted(df_filtered['Assigned Date'].dropna().dt.date.unique())
                        if all_a_dates:
                            sel_a_date = st.selectbox("Assigned Date", all_a_dates)
                            df_filtered = df_filtered[df_filtered['Assigned Date'].dt.date == sel_a_date]

                # 3. Branch (Default: All Selected)
                with col_f3:
                    if 'Branch' in df_filtered.columns:
                        all_branches = list(df_filtered['Branch'].unique())
                        sel_branches = st.multiselect("Branch", all_branches, default=all_branches)
                        if sel_branches:
                            df_filtered = df_filtered[df_filtered['Branch'].isin(sel_branches)]

                # 4. Task (Default: All Selected)
                with col_f4:
                    if 'Task Description' in df_filtered.columns:
                        all_tasks = list(df_filtered['Task Description'].unique())
                        sel_tasks = st.multiselect("Task", all_tasks, default=all_tasks)
                        if sel_tasks:
                            df_filtered = df_filtered[df_filtered['Task Description'].isin(sel_tasks)]

                # 5. Employee (Default: All Selected) - NEW ADDITION
                with col_f5:
                    if 'Employee' in df_filtered.columns:
                        all_emps = list(df_filtered['Employee'].unique())
                        sel_emps = st.multiselect("Employee", all_emps, default=all_emps)
                        if sel_emps:
                            df_filtered = df_filtered[df_filtered['Employee'].isin(sel_emps)]

                st.divider()
                
                # Cards
                tot_trans = df_filtered['Number of Transaction'].sum() if 'Number of Transaction' in df_filtered.columns else 0
                tot_find = df_filtered['Number of Findings'].sum() if 'Number of Findings' in df_filtered.columns else 0
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total Audits", len(df_filtered))
                k2.metric("Total Findings", int(tot_find))
                k3.metric("Transactions", f"{int(tot_trans):,}")
                k4.metric("Branches", df_filtered['Branch'].nunique())

                # Table
                st.subheader("Hierarchy: User → Branch → Task Type")
                if not df_filtered.empty:
                    # Grouping Logic
                    cols_to_group = ['Employee', 'Branch', 'Task Description']
                    cols_to_sum = ['Number of Transaction', 'Number of Findings']
                    
                    # Ensure columns exist before grouping
                    available_group_cols = [c for c in cols_to_group if c in df_filtered.columns]
                    available_sum_cols = [c for c in cols_to_sum if c in df_filtered.columns]
                    
                    if available_group_cols:
                        grouped_view = df_filtered.groupby(available_group_cols)[available_sum_cols].sum().reset_index()
                        count_view = df_filtered.groupby(available_group_cols).size().reset_index(name='Count')
                        final_table = pd.merge(grouped_view, count_view, on=available_group_cols)
                        st.dataframe(final_table, use_container_width=True)

        # --- TAB 2: EDIT/DELETE ---
        with tabs[1]:
            st.markdown("#### 🛠️ Edit or Delete Records")
            f_branch = st.selectbox("Filter by Branch", ["All"] + BRANCH_OPTIONS)
            df_view = tasks_df.copy()
            if f_branch != "All": df_view = df_view[df_view['Branch'] == f_branch]

            for idx, row in df_view.iterrows():
                status_icon = "✅" if row['Completion Status'] == 'Completed' else "⏳"
                lbl = f"{status_icon} **{row['Employee']}** | {row['Task Description']} @ {row['Branch']}"
                with st.expander(lbl):
                    with st.form(key=f"adm_edit_{idx}"):
                        c1, c2 = st.columns(2)
                        n_trans = c1.number_input("Transactions", value=int(row['Number of Transaction']))
                        n_find = c2.number_input("Findings", value=int(row['Number of Findings']))
                        c_act1, c_act2 = st.columns(2)
                        
                        if c_act1.form_submit_button("💾 Update"):
                            tasks_df.at[idx, 'Number of Transaction'] = n_trans
                            tasks_df.at[idx, 'Number of Findings'] = n_find
                            if update_data(conn, tasks_df, "Tasks"):
                                st.success("Updated!")
                                time.sleep(5)
                                st.rerun()
                                
                        if c_act2.form_submit_button("🗑️ DELETE", type="primary"):
                            tasks_df = tasks_df.drop(idx)
                            if update_data(conn, tasks_df, "Tasks"):
                                st.warning("Deleted!")
                                time.sleep(5)
                                st.rerun()

        # --- TAB 3: ASSIGN NEW TASK ---
        with tabs[2]:
            st.markdown("#### ➕ Assign New Audit")
            with st.form("admin_assign"):
                c1, c2 = st.columns(2)
                tgt = c1.selectbox("User", users_df['Username'].unique()) if not users_df.empty else c1.text_input("User")
                brn = c2.selectbox("Branch", BRANCH_OPTIONS)
                typ = c1.selectbox("Task", TASK_OPTIONS)
                jdt = c2.date_input("Journal Date")
                
                if st.form_submit_button("🚀 Assign Now", type="primary"):
                    now = datetime.now()
                    # CRITICAL FIX: EXACT COLUMN NAMES
                    new_row = {
                        'Employee': tgt, 
                        'Task Description': typ, 
                        'Branch': brn,
                        'Assigned Date': now.strftime('%d/%b/%Y'), 
                        'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': jdt.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 
                        'Number of Findings': 0, 
                        'Completion Status': 'In Progress',
                        'Completion Date': '',
                        'Completion Time': '',
                        'Duration': '',
                        'Progress %': ''
                    }
                    
                    # Create DataFrame with exact headers
                    new_df = pd.DataFrame([new_row])
                    updated_df = pd.concat([tasks_df, new_df], ignore_index=True)
                    
                    if update_data(conn, updated_df, "Tasks"):
                        st.success("✅ Task Assigned! Waiting 5 seconds...")
                        time.sleep(5)
                        st.rerun()

        # --- TAB 4: SQL TOOL ---
        with tabs[3]:
            st.header("SQL Query Tool")
            st.markdown("Use `df` as table name.")
            query = st.text_area("SQL", value='SELECT Branch, SUM("Number of Transaction") FROM df GROUP BY Branch', height=100)
            if st.button("Run SQL"):
                try:
                    sql_conn = sqlite3.connect(':memory:')
                    # Fix column names for SQL (remove spaces if needed or quote them)
                    tasks_df.to_sql('df', sql_conn, index=False, if_exists='replace')
                    result = pd.read_sql_query(query, sql_conn)
                    st.dataframe(result, use_container_width=True)
                except Exception as e:
                    st.error(f"SQL Error: {e}")

        # --- TAB 5: USERS ---
        with tabs[4]:
            st.markdown("#### 👥 User Directory")
            c1, c2 = st.columns(2)
            with c1:
                with st.form("add_user"):
                    nu = st.text_input("Username")
                    np = st.text_input("Password")
                    nr = st.selectbox("Role", ["User", "Admin"])
                    if st.form_submit_button("Add User"):
                        if nu not in users_df['Username'].values:
                            new_u = pd.DataFrame([{'Username': nu, 'Password': np, 'Role': nr}])
                            if update_data(conn, pd.concat([users_df, new_u], ignore_index=True), "Users"):
                                st.success("User Created")
                                time.sleep(5)
                                st.rerun()
                        else: st.error("User exists")
            with c2:
                st.dataframe(users_df[['Username', 'Role']], hide_index=True, use_container_width=True)

        # --- TAB 6: CUSTOM REPORT ---
        with tabs[5]:
            st.header("📑 Generate Custom Report")
            with st.expander("🔻 Report Filters (Click to Open)", expanded=True):
                st.info("ℹ️ Select filters below. Leave checkboxes unchecked to include ALL records.")
                with st.form("report_form"):
                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        use_assign_date = st.checkbox("Filter by Assigned Date?")
                        r_assign_date = st.date_input("Select Assigned Date")
                        st.markdown("<p class='format-note'>Format: YYYY/MM/DD</p>", unsafe_allow_html=True)
                    with col_r2:
                        use_journal_date = st.checkbox("Filter by Journal Date?")
                        r_journal_date = st.date_input("Select Journal Date")
                        st.markdown("<p class='format-note'>Format: YYYY/MM/DD</p>", unsafe_allow_html=True)
                    
                    col_r3, col_r4 = st.columns(2)
                    with col_r3:
                        use_emp = st.checkbox("Filter by Employee?")
                        r_emp = st.selectbox("Select Employee", users_df['Username'].unique())
                    with col_r4:
                        use_status = st.checkbox("Filter by Status?")
                        r_status = st.selectbox("Select Status", ["Completed", "In Progress"])

                    submitted = st.form_submit_button("🚀 Generate Report", type="primary")

            if submitted:
                report_df = tasks_df.copy()
                if use_assign_date and 'Assigned Date' in report_df.columns:
                    report_df = report_df[report_df['Assigned Date'].dt.date == r_assign_date]
                if use_journal_date and 'Journal Date' in report_df.columns:
                    report_df = report_df[report_df['Journal Date'].dt.date == r_journal_date]
                if use_emp:
                    report_df = report_df[report_df['Employee'] == r_emp]
                if use_status:
                    report_df = report_df[report_df['Completion Status'] == r_status]

                # Filter specific columns
                target_cols = ['Employee', 'Task Description', 'Branch', 'Assigned Date', 'Completion Status', 'Journal Date', 'Number of Transaction', 'Number of Findings']
                final_cols = [c for c in target_cols if c in report_df.columns]
                report_df = report_df[final_cols]

                st.success(f"Found {len(report_df)} records.")
                st.dataframe(report_df, use_container_width=True)
                csv = report_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, "custom_report.csv", "text/csv")

    # ==========================================
    # ROLE: USER VIEW
    # ==========================================
    else:
        st.title("✅ My Audit Space")
        u_tabs = st.tabs(["Dashboard", "Active Tasks", "New Log"])

        with u_tabs[0]:
            if not tasks_df.empty:
                my_df = tasks_df[tasks_df['Employee'] == user['Username']]
                if not my_df.empty:
                    c1, c2 = st.columns(2)
                    c1.metric("Tasks Completed", len(my_df[my_df['Completion Status']=='Completed']))
                    c2.metric("Pending", len(my_df[my_df['Completion Status']!='Completed']))
                else: st.info("No activity yet.")

        with u_tabs[1]:
            mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            active = tasks_df[mask].copy()
            if active.empty:
                st.success("🎉 All caught up!")
            else:
                for idx, row in active.iterrows():
                    with st.expander(f"📌 {row['Task Description']} @ {row['Branch']}", expanded=True):
                        with st.form(key=f"u_act_{idx}"):
                            c1, c2 = st.columns(2)
                            nt = c1.number_input("Transactions", value=int(row['Number of Transaction']))
                            nf = c2.number_input("Findings", value=int(row['Number of Findings']))
                            
                            if st.form_submit_button("✅ Mark Complete", type="primary"):
                                now = datetime.now()
                                cd, ct = now.strftime('%d/%b/%Y'), now.strftime('%I:%M:%S %p')
                                dur = calculate_duration(row['Assigned Date'], row['Assigned Time'], cd, ct)
                                
                                tasks_df.at[idx, 'Number of Transaction'] = nt
                                tasks_df.at[idx, 'Number of Findings'] = nf
                                tasks_df.at[idx, 'Completion Status'] = 'Completed'
                                tasks_df.at[idx, 'Completion Date'] = cd
                                tasks_df.at[idx, 'Completion Time'] = ct
                                tasks_df.at[idx, 'Duration'] = dur
                                tasks_df.at[idx, 'Progress %'] = 1
                                
                                if update_data(conn, tasks_df, "Tasks"):
                                    st.balloons()
                                    time.sleep(5)
                                    st.rerun()

        with u_tabs[2]:
            st.markdown("#### ⚡ Quick Log")
            with st.form("u_new"):
                c1, c2 = st.columns(2)
                br = c1.selectbox("Branch", BRANCH_OPTIONS)
                ty = c2.selectbox("Task", TASK_OPTIONS)
                jd = c1.date_input("Journal Date")
                
                if st.form_submit_button("Start Timer", type="primary"):
                    now = datetime.now()
                    new_r = {
                        'Employee': user['Username'], 'Task Description': ty, 'Branch': br,
                        'Assigned Date': now.strftime('%d/%b/%Y'), 
                        'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': jd.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 
                        'Number of Findings': 0, 
                        'Completion Status': 'In Progress',
                        'Completion Date': '',
                        'Completion Time': '',
                        'Duration': '',
                        'Progress %': ''
                    }
                    
                    new_df = pd.DataFrame([new_r])
                    updated_df = pd.concat([tasks_df, new_df], ignore_index=True)
                    if update_data(conn, updated_df, "Tasks"):
                        st.success("Started! Waiting 5 seconds...")
                        time.sleep(5)
                        st.rerun()

if __name__ == "__main__":
    main()
