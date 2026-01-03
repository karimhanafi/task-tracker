import streamlit as st
import pandas as pd
import sqlite3
import time
import pytz
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATION & VISUALS ---
st.set_page_config(page_title="IC Audit Pro", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
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
BRANCH_OPTIONS = ["NAL","PET","DMP","MND","ADT","BRG","MIN","KSH","RSH","DMN","BNH","ALX","XND","SAN","SMO","TNT","ZGZ"]
TASK_OPTIONS = [
    "Cash", "Operation", "C.S"
]
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# --- 3. SMART DATE FUNCTIONS ---

def get_current_time():
    return datetime.now(EGYPT_TZ)

def parse_date_robustly(date_val):
    if pd.isna(date_val) or date_val == "":
        return None
    if isinstance(date_val, (pd.Timestamp, datetime)):
        return date_val

    date_str = str(date_val).strip()
    formats_to_try = ['%d/%b/%Y', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d']
    
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def calculate_duration(start_date, start_time, end_date, end_time):
    try:
        s_date = parse_date_robustly(start_date)
        e_date = parse_date_robustly(end_date)
        
        if not s_date or not e_date: return "0h 0m"

        s_time_str = str(start_time).strip()
        e_time_str = str(end_time).strip()
        
        if len(s_time_str.split(':')) == 2: s_time_str += ":00"
        if len(e_time_str.split(':')) == 2: e_time_str += ":00"

        dt_start = datetime.combine(s_date.date(), datetime.strptime(s_time_str, '%I:%M:%S %p').time())
        dt_end = datetime.combine(e_date.date(), datetime.strptime(e_time_str, '%I:%M:%S %p').time())
        
        diff = dt_end - dt_start
        secs = diff.total_seconds()
        
        if secs < 0: return "0h 0m"
        return f"{int(secs // 3600)}h {int((secs % 3600) // 60)}m"
    except: return "0h 0m"

# --- 4. DATABASE FUNCTIONS ---

def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        tasks_df = conn.read(worksheet="Tasks", ttl=0)
        users_df = conn.read(worksheet="Users", ttl=0)
        
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        
        cols_needed = [
            "Employee", "Task Description", "Branch", "Assigned Date", "Assigned Time",
            "Completion Status", "Completion Date", "Completion Time", "Duration", "Progress %",
            "Journal Date", "Number of Findings", "Number of Transaction"
        ]
        for col in cols_needed:
            if col not in tasks_df.columns: tasks_df[col] = ""
            
        return conn, tasks_df, users_df
    except:
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    try:
        date_cols = ['Assigned Date', 'Completion Date', 'Journal Date']
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: parse_date_robustly(x).strftime('%d/%b/%Y') if parse_date_robustly(x) else x)

        df = df.fillna("") 
        conn.update(worksheet=worksheet_name, data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠️ Save Error: {e}")
        return False

# --- 5. MAIN APPLICATION ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_info = None

    conn, tasks_df, users_df = get_data()

    if users_df.empty:
        st.warning("⚠️ **System is cooling down.**")
        st.info("Please wait **60 seconds** and refresh.")
        st.stop() 

    users_df['Username'] = users_df['Username'].astype(str)
    users_df['Password'] = users_df['Password'].astype(str)
    
    # --- LOGIC DATAFRAME ---
    tasks_df_logic = tasks_df.copy()
    if not tasks_df_logic.empty:
        for col in ['Number of Findings', 'Number of Transaction']:
            if col in tasks_df_logic.columns:
                tasks_df_logic[col] = pd.to_numeric(tasks_df_logic[col], errors='coerce').fillna(0)
        
        for col in ['Journal Date', 'Assigned Date']:
            if col in tasks_df_logic.columns:
                tasks_df_logic[col] = tasks_df_logic[col].apply(parse_date_robustly)

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
        tabs = st.tabs(["📈 Analytics", "⚡ My Tasks", "📝 Manage Tasks", "➕ Assign Task", "💻 SQL Tool", "👥 User Mgmt", "📑 Custom Report"])

        # TAB 1: Analytics (Updated for Detailed View & Serial Counting)
        with tabs[0]:
            st.header("Drill-Down Analysis")
            if tasks_df_logic.empty:
                st.info("No data available.")
            else:
                col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
                df_filtered = tasks_df_logic.copy()
                
                with col_f1:
                    dates = sorted(df_filtered['Journal Date'].dropna().dt.date.unique()) if 'Journal Date' in df_filtered else []
                    if dates:
                        sel = st.multiselect("Journal Date", dates, placeholder="All Dates")
                        if sel: df_filtered = df_filtered[df_filtered['Journal Date'].dt.date.isin(sel)]
                
                with col_f2:
                    dates = sorted(df_filtered['Assigned Date'].dropna().dt.date.unique()) if 'Assigned Date' in df_filtered else []
                    if dates:
                        sel = st.multiselect("Assigned Date", dates, placeholder="All Dates")
                        if sel: df_filtered = df_filtered[df_filtered['Assigned Date'].dt.date.isin(sel)]

                with col_f3:
                    opts = list(df_filtered['Branch'].unique()) if 'Branch' in df_filtered else []
                    sel = st.multiselect("Branch", opts, placeholder="All Branches")
                    if sel: df_filtered = df_filtered[df_filtered['Branch'].isin(sel)]

                with col_f4:
                    opts = list(df_filtered['Task Description'].unique()) if 'Task Description' in df_filtered else []
                    sel = st.multiselect("Task", opts, placeholder="All Tasks")
                    if sel: df_filtered = df_filtered[df_filtered['Task Description'].isin(sel)]

                with col_f5:
                    opts = list(df_filtered['Employee'].unique()) if 'Employee' in df_filtered else []
                    sel = st.multiselect("Employee", opts, placeholder="All Employees")
                    if sel: df_filtered = df_filtered[df_filtered['Employee'].isin(sel)]

                st.divider()
                tot_trans = df_filtered['Number of Transaction'].sum() if 'Number of Transaction' in df_filtered else 0
                tot_find = df_filtered['Number of Findings'].sum() if 'Number of Findings' in df_filtered else 0
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Audits", len(df_filtered))
                k2.metric("Findings", int(tot_find))
                k3.metric("Transactions", f"{int(tot_trans):,}")
                k4.metric("Branches", df_filtered['Branch'].nunique() if 'Branch' in df_filtered else 0)

                # --- NEW DETAILED TABLE LOGIC ---
                st.subheader("Detailed Audit List")
                if not df_filtered.empty:
                    # 1. Define exact columns requested
                    cols_to_show = [
                        'Employee', 'Branch', 'Task Description',
                        'Assigned Date', 'Assigned Time',
                        'Journal Date',
                        'Completion Date', 'Completion Time',
                        'Duration',
                        'Number of Transaction', 'Number of Findings'
                    ]
                    # Filter to ensure columns exist
                    final_cols = [c for c in cols_to_show if c in df_filtered.columns]
                    
                    # Create display dataframe
                    df_display = df_filtered[final_cols].copy()
                    
                    # 2. Format Dates back to String for Display (so they look nice)
                    if 'Assigned Date' in df_display.columns:
                        df_display['Assigned Date'] = df_display['Assigned Date'].dt.strftime('%d/%b/%Y')
                    if 'Journal Date' in df_display.columns:
                        df_display['Journal Date'] = df_display['Journal Date'].dt.strftime('%d/%b/%Y')
                        
                    # 3. FIX SERIAL COUNTING (Start from 1, not 0)
                    df_display.index = range(1, len(df_display) + 1)
                    
                    st.dataframe(df_display, use_container_width=True)

        # TAB 2: MY TASKS
        with tabs[1]:
            st.header("⚡ My Active Tasks")
            mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            my_active = tasks_df[mask].copy()
            if my_active.empty: st.success("🎉 You have no pending tasks.")
            for idx, row in my_active.iterrows():
                with st.expander(f"📌 {row['Task Description']} @ {row['Branch']}", expanded=True):
                    with st.form(key=f"adm_complete_{idx}"):
                        c1, c2 = st.columns(2)
                        try: vt = int(float(row['Number of Transaction'])) if row['Number of Transaction']!='' else 0
                        except: vt = 0
                        try: vf = int(float(row['Number of Findings'])) if row['Number of Findings']!='' else 0
                        except: vf = 0
                        nt = c1.number_input("Transactions", value=vt)
                        nf = c2.number_input("Findings", value=vf)
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
                            if update_data(conn, tasks_df, "Tasks"): st.balloons(); time.sleep(3); st.rerun()

        # TAB 3: Edit
        with tabs[2]:
            st.markdown("#### 🛠️ Edit or Delete Records")
            f_branch = st.selectbox("Filter by Branch", ["All"] + BRANCH_OPTIONS)
            df_view = tasks_df.copy()
            if f_branch != "All": df_view = df_view[df_view['Branch'] == f_branch]

            for idx, row in df_view.iterrows():
                icon = "✅" if row['Completion Status'] == 'Completed' else "⏳"
                lbl = f"{icon} **{row['Employee']}** | {row['Task Description']} @ {row['Branch']}"
                with st.expander(lbl):
                    with st.form(key=f"adm_edit_{idx}"):
                        c1, c2 = st.columns(2)
                        try: vt = int(float(row['Number of Transaction'])) if row['Number of Transaction']!='' else 0
                        except: vt = 0
                        try: vf = int(float(row['Number of Findings'])) if row['Number of Findings']!='' else 0
                        except: vf = 0
                        nt = c1.number_input("Transactions", value=vt)
                        nf = c2.number_input("Findings", value=vf)
                        c_act1, c_act2 = st.columns(2)
                        if c_act1.form_submit_button("💾 Update"):
                            tasks_df.at[idx, 'Number of Transaction'] = nt
                            tasks_df.at[idx, 'Number of Findings'] = nf
                            if update_data(conn, tasks_df, "Tasks"): st.success("Updated!"); time.sleep(3); st.rerun()
                        if c_act2.form_submit_button("🗑️ DELETE", type="primary"):
                            tasks_df = tasks_df.drop(idx)
                            if update_data(conn, tasks_df, "Tasks"): st.warning("Deleted!"); time.sleep(3); st.rerun()

        # TAB 4: Assign
        with tabs[3]:
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
                        'Completion Status': 'In Progress', 'Completion Date': '', 'Completion Time': '',
                        'Duration': '', 'Progress %': '', 'Journal Date': jdt.strftime('%d/%b/%Y'), 
                        'Number of Findings': 0, 'Number of Transaction': 0
                    }
                    updated_df = pd.concat([tasks_df, pd.DataFrame([new_row])], ignore_index=True)
                    if update_data(conn, updated_df, "Tasks"): st.success("Assigned!"); time.sleep(3); st.rerun()

        # TAB 5: SQL
        with tabs[4]:
            st.header("SQL Query Tool")
            query = st.text_area("SQL", value='SELECT Branch, SUM("Number of Transaction") FROM df GROUP BY Branch', height=100)
            if st.button("Run SQL"):
                try:
                    sql_conn = sqlite3.connect(':memory:')
                    tasks_df.to_sql('df', sql_conn, index=False, if_exists='replace')
                    st.dataframe(pd.read_sql_query(query, sql_conn), use_container_width=True)
                except Exception as e: st.error(f"SQL Error: {e}")

        # TAB 6: Users
        with tabs[5]:
            st.markdown("#### 👥 User Directory")
            c1, c2 = st.columns(2)
            with c1:
                with st.form("add_user"):
                    nu = st.text_input("Username"); np = st.text_input("Password"); nr = st.selectbox("Role", ["User", "Admin"])
                    if st.form_submit_button("Add User"):
                        if nu not in users_df['Username'].values:
                            new_u = pd.DataFrame([{'Username': nu, 'Password': np, 'Role': nr}])
                            if update_data(conn, pd.concat([users_df, new_u], ignore_index=True), "Users"): st.success("Created"); time.sleep(3); st.rerun()
                        else: st.error("Exists")
            with c2: st.dataframe(users_df[['Username', 'Role']], hide_index=True)

        # TAB 7: Report
        with tabs[6]:
            st.header("📑 Generate Custom Report")
            with st.expander("🔻 Report Filters (Leave blank to select ALL)", expanded=True):
                with st.form("report_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        dates = sorted(tasks_df_logic['Journal Date'].dropna().dt.date.unique()) if 'Journal Date' in tasks_df_logic else []
                        sel_jd = st.multiselect("Journal Date", dates, placeholder="All Dates")
                    with c2:
                        dates = sorted(tasks_df_logic['Assigned Date'].dropna().dt.date.unique()) if 'Assigned Date' in tasks_df_logic else []
                        sel_ad = st.multiselect("Assigned Date", dates, placeholder="All Dates")
                    
                    c3, c4 = st.columns(2)
                    with c3:
                        opts = list(tasks_df_logic['Branch'].unique()) if 'Branch' in tasks_df_logic else []
                        sel_br = st.multiselect("Branch", opts, placeholder="All Branches")
                    with c4:
                        opts = list(tasks_df_logic['Task Description'].unique()) if 'Task Description' in tasks_df_logic else []
                        sel_tk = st.multiselect("Task", opts, placeholder="All Tasks")
                    
                    c5, c6 = st.columns(2)
                    with c5:
                        opts = list(tasks_df_logic['Employee'].unique()) if 'Employee' in tasks_df_logic else []
                        sel_em = st.multiselect("Employee", opts, placeholder="All Employees")
                    with c6:
                        opts = ["Completed", "In Progress"]
                        sel_st = st.multiselect("Status", opts, placeholder="All Statuses")

                    submitted = st.form_submit_button("🚀 Generate Report", type="primary")

            if submitted:
                report_df = tasks_df_logic.copy()
                if sel_jd: report_df = report_df[report_df['Journal Date'].dt.date.isin(sel_jd)]
                if sel_ad: report_df = report_df[report_df['Assigned Date'].dt.date.isin(sel_ad)]
                if sel_br: report_df = report_df[report_df['Branch'].isin(sel_br)]
                if sel_tk: report_df = report_df[report_df['Task Description'].isin(sel_tk)]
                if sel_em: report_df = report_df[report_df['Employee'].isin(sel_em)]
                if sel_st: report_df = report_df[report_df['Completion Status'].isin(sel_st)]

                for col in ['Assigned Date', 'Journal Date']:
                    if col in report_df.columns: report_df[col] = report_df[col].dt.strftime('%d/%b/%Y')

                cols = ['Employee','Task Description','Branch','Assigned Date','Completion Status','Journal Date','Number of Findings','Number of Transaction']
                valid = [c for c in cols if c in report_df.columns]
                report_df = report_df[valid]
                st.success(f"Generated report with {len(report_df)} records.")
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
                        try: vt = int(float(row['Number of Transaction'])) if row['Number of Transaction']!='' else 0
                        except: vt = 0
                        try: vf = int(float(row['Number of Findings'])) if row['Number of Findings']!='' else 0
                        except: vf = 0
                        nt = c1.number_input("Transactions", value=vt)
                        nf = c2.number_input("Findings", value=vf)
                        
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
                            if update_data(conn, tasks_df, "Tasks"): st.balloons(); time.sleep(3); st.rerun()

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
                        'Completion Status': 'In Progress', 'Completion Date': '', 'Completion Time': '',
                        'Duration': '', 'Progress %': '', 'Journal Date': jd.strftime('%d/%b/%Y'), 
                        'Number of Findings': 0, 'Number of Transaction': 0
                    }
                    updated_df = pd.concat([tasks_df, pd.DataFrame([new_r])], ignore_index=True)
                    if update_data(conn, updated_df, "Tasks"): st.success("Started!"); time.sleep(3); st.rerun()

if __name__ == "__main__":
    main()
