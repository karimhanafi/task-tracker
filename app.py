import streamlit as st
import pandas as pd
import sqlite3
import time
import pytz # For Egypt Time
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
    div[data-testid="stExpander"] { background-color: #262730; border-radius: 10px; }
    .stButton>button { border-radius: 20px; font-weight: bold; }
    .format-note { font-size: 0.8rem; color: #ffbd45; margin-top: -10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONSTANTS ---
BRANCH_OPTIONS = ["HQ", "SUZ", "HUR", "SSH", "LXR", "ASW", "ALX", "CAI", "GIZA", "MANS", "OTHERS"]
TASK_OPTIONS = [
    "Cash Count", "Operation Audit", "Stock Count", "ATM Review", 
    "Log Review", "Documentation Check", "Customer Service Review", "Other"
]
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# --- 3. DATABASE FUNCTIONS ---

def get_current_time():
    """Returns current time in Egypt Timezone."""
    return datetime.now(EGYPT_TZ)

def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        tasks_df = conn.read(worksheet="Tasks", ttl=0)
        users_df = conn.read(worksheet="Users", ttl=0)
        
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        
        cols_needed = [
            'Employee', 'Task Description', 'Branch', 'Assigned Date', 'Assigned Time',
            'Completion Status', 'Completion Date', 'Completion Time', 'Duration', 'Progress %',
            'Journal Date', 'Number of Findings', 'Number of Transaction'
        ]
        for col in cols_needed:
            if col not in tasks_df.columns: tasks_df[col] = ""
            
        return conn, tasks_df, users_df
    except Exception as e:
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    try:
        # FORCE FORMATTING: Ensure Dates are saved as DD/MMM/YYYY String to prevent Sheet corruption
        date_cols = ['Assigned Date', 'Completion Date', 'Journal Date']
        for col in date_cols:
            if col in df.columns:
                # If it's a datetime object, convert to String '27/Dec/2025'
                # If it's already a string, keep it.
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%d/%b/%Y').fillna(df[col])

        df = df.fillna("") 
        conn.update(worksheet=worksheet_name, data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠️ Save Error: {e}")
        return False

# --- FIXED CALCULATION LOGIC ---
def calculate_duration(start_date, start_time, end_date, end_time):
    try:
        # 1. Handle Start Date (Can be Timestamp OR String)
        if isinstance(start_date, pd.Timestamp) or isinstance(start_date, datetime):
            s_date = start_date
        else:
            s_date = datetime.strptime(str(start_date), '%d/%b/%Y')

        # 2. Handle End Date (Usually String, but be safe)
        if isinstance(end_date, pd.Timestamp) or isinstance(end_date, datetime):
            e_date = end_date
        else:
            e_date = datetime.strptime(str(end_date), '%d/%b/%Y')

        # 3. Parse Times (e.g., "10:30:00 AM")
        s_time_obj = datetime.strptime(str(start_time), '%I:%M:%S %p').time()
        e_time_obj = datetime.strptime(str(end_time), '%I:%M:%S %p').time()
        
        # 4. Combine to Full Datetime
        dt_start = datetime.combine(s_date.date(), s_time_obj)
        dt_end = datetime.combine(e_date.date(), e_time_obj)
        
        # 5. Calculate Difference
        diff = dt_end - dt_start
        secs = diff.total_seconds()
        
        if secs < 0: return "0h 0m"
        return f"{int(secs // 3600)}h {int((secs % 3600) // 60)}m"
    except Exception as e:
        # If anything fails, return 0h 0m instead of crashing
        return "0h 0m"

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

    users_df['Username'] = users_df['Username'].astype(str)
    users_df['Password'] = users_df['Password'].astype(str)
    
    # Logic DataFrame (with Real Dates for Filtering)
    tasks_df_logic = tasks_df.copy()
    if not tasks_df_logic.empty:
        if 'Number of Findings' in tasks_df_logic.columns:
            tasks_df_logic['Number of Findings'] = pd.to_numeric(tasks_df_logic['Number of Findings'], errors='coerce').fillna(0)
        if 'Number of Transaction' in tasks_df_logic.columns:
            tasks_df_logic['Number of Transaction'] = pd.to_numeric(tasks_df_logic['Number of Transaction'], errors='coerce').fillna(0)
        
        # Parse Dates for Filtering Logic
        if 'Journal Date' in tasks_df_logic.columns:
            tasks_df_logic['Journal Date'] = pd.to_datetime(tasks_df_logic['Journal Date'], format='%d/%b/%Y', errors='coerce')
        if 'Assigned Date' in tasks_df_logic.columns:
            tasks_df_logic['Assigned Date'] = pd.to_datetime(tasks_df_logic['Assigned Date'], format='%d/%b/%Y', errors='coerce')

    # --- LOGIN ---
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

    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### 👋 {user['Username']}")
        st.caption(f"Role: {user['Role']}")
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()

    # --- ADMIN VIEW ---
    if user['Role'] == 'Admin':
        st.title("📊 Executive Dashboard")
        tabs = st.tabs(["📈 Analytics", "📝 Manage Tasks", "➕ Assign Task", "💻 SQL Tool", "👥 User Mgmt", "📑 Custom Report"])

        # TAB 1: Analytics
        with tabs[0]:
            st.header("Drill-Down Analysis")
            if tasks_df_logic.empty:
                st.info("No data available.")
            else:
                col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
                df_filtered = tasks_df_logic.copy()
                
                with col_f1:
                    if 'Journal Date' in df_filtered.columns:
                        all_j_dates = sorted(df_filtered['Journal Date'].dropna().dt.date.unique())
                        if all_j_dates:
                            sel_j_date = st.selectbox("Journal Date", all_j_dates)
                            df_filtered = df_filtered[df_filtered['Journal Date'].dt.date == sel_j_date]

                with col_f2:
                    if 'Assigned Date' in df_filtered.columns:
                        all_a_dates = sorted(df_filtered['Assigned Date'].dropna().dt.date.unique())
                        if all_a_dates:
                            sel_a_date = st.selectbox("Assigned Date", all_a_dates)
                            df_filtered = df_filtered[df_filtered['Assigned Date'].dt.date == sel_a_date]

                with col_f3:
                    all_branches = list(df_filtered['Branch'].unique()) if 'Branch' in df_filtered.columns else []
                    sel_branches = st.multiselect("Branch", all_branches, default=all_branches)
                    if sel_branches: df_filtered = df_filtered[df_filtered['Branch'].isin(sel_branches)]

                with col_f4:
                    all_tasks = list(df_filtered['Task Description'].unique()) if 'Task Description' in df_filtered.columns else []
                    sel_tasks = st.multiselect("Task", all_tasks, default=all_tasks)
                    if sel_tasks: df_filtered = df_filtered[df_filtered['Task Description'].isin(sel_tasks)]

                with col_f5:
                    all_emps = list(df_filtered['Employee'].unique()) if 'Employee' in df_filtered.columns else []
                    sel_emps = st.multiselect("Employee", all_emps, default=all_emps)
                    if sel_emps: df_filtered = df_filtered[df_filtered['Employee'].isin(sel_emps)]

                st.divider()
                tot_trans = df_filtered['Number of Transaction'].sum() if 'Number of Transaction' in df_filtered.columns else 0
                tot_find = df_filtered['Number of Findings'].sum() if 'Number of Findings' in df_filtered.columns else 0
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total Audits", len(df_filtered))
                k2.metric("Total Findings", int(tot_find))
                k3.metric("Transactions", f"{int(tot_trans):,}")
                k4.metric("Branches", df_filtered['Branch'].nunique() if 'Branch' in df_filtered.columns else 0)

                st.subheader("Hierarchy: User → Branch → Task Type")
                if not df_filtered.empty:
                    cols_to_group = ['Employee', 'Branch', 'Task Description']
                    cols_to_sum = ['Number of Transaction', 'Number of Findings']
                    available_group = [c for c in cols_to_group if c in df_filtered.columns]
                    if available_group:
                        grouped = df_filtered.groupby(available_group)[cols_to_sum].sum().reset_index()
                        count = df_filtered.groupby(available_group).size().reset_index(name='Count')
                        final = pd.merge(grouped, count, on=available_group)
                        st.dataframe(final, use_container_width=True)

        # TAB 2: Edit
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
                        val_trans = int(float(row['Number of Transaction'])) if row['Number of Transaction']!='' else 0
                        val_find = int(float(row['Number of Findings'])) if row['Number of Findings']!='' else 0
                        
                        n_trans = c1.number_input("Transactions", value=val_trans)
                        n_find = c2.number_input("Findings", value=val_find)
                        
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

        # TAB 3: Assign
        with tabs[2]:
            st.markdown("#### ➕ Assign New Audit")
            with st.form("admin_assign"):
                c1, c2 = st.columns(2)
                tgt = c1.selectbox("User", users_df['Username'].unique()) if not users_df.empty else c1.text_input("User")
                brn = c2.selectbox("Branch", BRANCH_OPTIONS)
                typ = c1.selectbox("Task", TASK_OPTIONS)
                jdt = c2.date_input("Journal Date")
                
                if st.form_submit_button("🚀 Assign Now", type="primary"):
                    now = get_current_time()
                    new_row = {
                        'Employee': tgt, 'Task Description': typ, 'Branch': brn,
                        'Assigned Date': now.strftime('%d/%b/%Y'), 'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': jdt.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 'Number of Findings': 0, 'Completion Status': 'In Progress',
                        'Completion Date': '', 'Completion Time': '', 'Duration': '', 'Progress %': ''
                    }
                    updated_df = pd.concat([tasks_df, pd.DataFrame([new_row])], ignore_index=True)
                    if update_data(conn, updated_df, "Tasks"):
                        st.success("✅ Task Assigned! Waiting 5s...")
                        time.sleep(5)
                        st.rerun()

        # TAB 4: SQL
        with tabs[3]:
            st.header("SQL Query Tool")
            st.markdown("Use `df` as table name.")
            query = st.text_area("SQL", value='SELECT Branch, SUM("Number of Transaction") FROM df GROUP BY Branch', height=100)
            if st.button("Run SQL"):
                try:
                    sql_conn = sqlite3.connect(':memory:')
                    tasks_df.to_sql('df', sql_conn, index=False, if_exists='replace')
                    result = pd.read_sql_query(query, sql_conn)
                    st.dataframe(result, use_container_width=True)
                except Exception as e: st.error(f"SQL Error: {e}")

        # TAB 5: Users
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
            with c2: st.dataframe(users_df[['Username', 'Role']], hide_index=True, use_container_width=True)

        # TAB 6: Report
        with tabs[5]:
            st.header("📑 Generate Custom Report")
            with st.expander("🔻 Report Filters", expanded=True):
                with st.form("report_form"):
                    c1, c2 = st.columns(2)
                    use_ad = c1.checkbox("Filter Assigned Date?"); r_ad = c1.date_input("Assigned Date")
                    use_jd = c2.checkbox("Filter Journal Date?"); r_jd = c2.date_input("Journal Date")
                    c3, c4 = st.columns(2)
                    use_em = c3.checkbox("Filter Employee?"); r_em = c3.selectbox("Employee", users_df['Username'].unique())
                    use_st = c4.checkbox("Filter Status?"); r_st = c4.selectbox("Status", ["Completed", "In Progress"])
                    submitted = st.form_submit_button("🚀 Generate Report", type="primary")

            if submitted:
                report_df = tasks_df_logic.copy()
                if use_ad: report_df = report_df[report_df['Assigned Date'].dt.date == r_ad]
                if use_jd: report_df = report_df[report_df['Journal Date'].dt.date == r_jd]
                if use_em: report_df = report_df[report_df['Employee'] == r_em]
                if use_st: report_df = report_df[report_df['Completion Status'] == r_st]
                
                # Format Dates for Export
                if 'Assigned Date' in report_df.columns: report_df['Assigned Date'] = report_df['Assigned Date'].dt.strftime('%d/%b/%Y')
                if 'Journal Date' in report_df.columns: report_df['Journal Date'] = report_df['Journal Date'].dt.strftime('%d/%b/%Y')

                final_cols = [c for c in ['Employee','Task Description','Branch','Assigned Date','Completion Status','Journal Date','Number of Transaction','Number of Findings'] if c in report_df.columns]
                report_df = report_df[final_cols]
                st.dataframe(report_df, use_container_width=True)
                st.download_button("📥 Download CSV", report_df.to_csv(index=False).encode('utf-8'), "report.csv", "text/csv")

    # --- USER VIEW ---
    else:
        st.title("✅ My Audit Space")
        u_tabs = st.tabs(["Dashboard", "Active Tasks", "New Log"])

        with u_tabs[0]:
            if not tasks_df.empty:
                my_df = tasks_df[tasks_df['Employee'] == user['Username']]
                c1, c2 = st.columns(2)
                c1.metric("Completed", len(my_df[my_df['Completion Status']=='Completed']))
                c2.metric("Pending", len(my_df[my_df['Completion Status']!='Completed']))

        with u_tabs[1]:
            mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            active = tasks_df[mask].copy()
            if active.empty: st.success("🎉 All caught up!")
            for idx, row in active.iterrows():
                with st.expander(f"📌 {row['Task Description']} @ {row['Branch']}", expanded=True):
                    with st.form(key=f"u_act_{idx}"):
                        c1, c2 = st.columns(2)
                        val_trans = int(float(row['Number of Transaction'])) if row['Number of Transaction']!='' else 0
                        val_find = int(float(row['Number of Findings'])) if row['Number of Findings']!='' else 0
                        nt = c1.number_input("Transactions", value=val_trans)
                        nf = c2.number_input("Findings", value=val_find)
                        if st.form_submit_button("✅ Mark Complete", type="primary"):
                            now = get_current_time()
                            cd = now.strftime('%d/%b/%Y'); ct = now.strftime('%I:%M:%S %p')
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
                    now = get_current_time()
                    new_r = {
                        'Employee': user['Username'], 'Task Description': ty, 'Branch': br,
                        'Assigned Date': now.strftime('%d/%b/%Y'), 'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': jd.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 'Number of Findings': 0, 'Completion Status': 'In Progress',
                        'Completion Date': '', 'Completion Time': '', 'Duration': '', 'Progress %': ''
                    }
                    updated_df = pd.concat([tasks_df, pd.DataFrame([new_r])], ignore_index=True)
                    if update_data(conn, updated_df, "Tasks"):
                        st.success("Started! Waiting 5s...")
                        time.sleep(5)
                        st.rerun()

if __name__ == "__main__":
    main()
