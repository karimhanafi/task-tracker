import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION & DARK MODE FORCE ---
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
</style>
""", unsafe_allow_html=True)

# --- CONSTANTS ---
BRANCH_OPTIONS = ["HQ", "SUZ", "HUR", "SSH", "LXR", "ASW", "ALX", "CAI", "GIZA", "MANS", "OTHERS"]
TASK_OPTIONS = [
    "Cash Count", "Operation Audit", "Stock Count", "ATM Review", 
    "Log Review", "Documentation Check", "Customer Service Review", "Other"
]

# --- DATABASE CONNECTION (Fixed for Stability) ---
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # ERROR FIX: Increased ttl to 10 seconds to avoid hitting Google's rate limit
        tasks_df = conn.read(worksheet="Tasks", ttl=10)
        users_df = conn.read(worksheet="Users", ttl=10)
        
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        
        cols_needed = ['Number of Findings', 'Number of Transaction', 'Branch', 'Employee', 'Completion Status', 'Assigned Date', 'Assigned Time', 'Journal Date', 'Task Description']
        for col in cols_needed:
            if col not in tasks_df.columns: tasks_df[col] = 0
            
        return conn, tasks_df, users_df
    except Exception as e:
        # If quota exceeded, we return empty frames but handle it gracefully in main()
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    try:
        conn.update(worksheet=worksheet_name, data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Could not save: {e}")

def calculate_duration(start_date, start_time, end_date, end_time):
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

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_info = None

    conn, tasks_df, users_df = get_data()

    # --- ERROR FIX: SAFETY STOP ---
    # If users_df is empty, it means the Google Connection failed (Quota Error).
    # We stop here to prevent the "KeyError" crash.
    if users_df.empty:
        st.warning("⚠️ **System is cooling down.**")
        st.info("You hit the Google Sheets speed limit. Please wait **60 seconds** and refresh the page.")
        st.stop() 

    # Data Type Fixes
    users_df['Username'] = users_df['Username'].astype(str)
    users_df['Password'] = users_df['Password'].astype(str)
    
    if not tasks_df.empty:
        tasks_df['Number of Findings'] = pd.to_numeric(tasks_df['Number of Findings'], errors='coerce').fillna(0)
        tasks_df['Number of Transaction'] = pd.to_numeric(tasks_df['Number of Transaction'], errors='coerce').fillna(0)
        if 'Journal Date' in tasks_df.columns:
            tasks_df['Journal Date'] = pd.to_datetime(tasks_df['Journal Date'], format='%d/%b/%Y', errors='coerce')

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
        tabs = st.tabs(["📈 Analytics & Filters", "📝 Manage Tasks", "➕ Assign Task", "💻 SQL Tool", "👥 User Mgmt"])

        # --- TAB 1: ANALYTICS ---
        with tabs[0]:
            st.header("Drill-Down Analysis")
            
            if tasks_df.empty:
                st.info("No data available.")
            else:
                col_filter1, col_filter2, col_filter3 = st.columns(3)
                df_filtered = tasks_df.copy()
                
                if 'Journal Date' in df_filtered.columns:
                    all_dates = sorted(df_filtered['Journal Date'].dropna().dt.date.unique())
                    if all_dates:
                        selected_date = col_filter1.selectbox("Select Date", all_dates)
                        df_filtered = df_filtered[df_filtered['Journal Date'].dt.date == selected_date]

                if 'Branch' in df_filtered.columns:
                    all_branches = df_filtered['Branch'].unique()
                    selected_branches = col_filter2.multiselect("Filter Branch", all_branches, default=all_branches)
                    if selected_branches:
                        df_filtered = df_filtered[df_filtered['Branch'].isin(selected_branches)]

                if 'Task Description' in df_filtered.columns:
                    all_tasks = df_filtered['Task Description'].unique()
                    selected_tasks = col_filter3.multiselect("Filter Task", all_tasks, default=all_tasks)
                    if selected_tasks:
                        df_filtered = df_filtered[df_filtered['Task Description'].isin(selected_tasks)]

                st.divider()

                tot_trans = df_filtered['Number of Transaction'].sum()
                tot_find = df_filtered['Number of Findings'].sum()
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total Audits", len(df_filtered))
                k2.metric("Total Findings", int(tot_find))
                k3.metric("Transactions", f"{int(tot_trans):,}")
                k4.metric("Branches", df_filtered['Branch'].nunique())

                st.subheader("Hierarchy: User → Branch → Task Type")
                if not df_filtered.empty:
                    grouped_view = df_filtered.groupby(['Employee', 'Branch', 'Task Description'])[[
                        'Number of Transaction', 'Number of Findings'
                    ]].sum().reset_index()
                    count_view = df_filtered.groupby(['Employee', 'Branch', 'Task Description']).size().reset_index(name='Count')
                    final_table = pd.merge(grouped_view, count_view, on=['Employee', 'Branch', 'Task Description'])
                    final_table = final_table[['Employee', 'Branch', 'Task Description', 'Count', 'Number of Transaction', 'Number of Findings']]
                    st.dataframe(final_table, use_container_width=True)
                else:
                    st.warning("No data matches your filters.")

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
                            update_data(conn, tasks_df, "Tasks")
                            st.success("Updated!")
                            st.rerun()
                        if c_act2.form_submit_button("🗑️ DELETE", type="primary"):
                            tasks_df = tasks_df.drop(idx)
                            update_data(conn, tasks_df, "Tasks")
                            st.warning("Deleted!")
                            st.rerun()

        # --- TAB 3: ASSIGN ---
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
                    new_row = {
                        'Employee': tgt, 'Task Description': typ, 'Branch': brn,
                        'Assigned Date': now.strftime('%d/%b/%Y'), 'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': jdt.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 'Number of Findings': 0, 'Completion Status': 'In Progress'
                    }
                    update_data(conn, pd.concat([tasks_df, pd.DataFrame([new_row])], ignore_index=True), "Tasks")
                    st.success("Assigned!")
                    st.rerun()

        # --- TAB 4: SQL TOOL (SQLite) ---
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
                            update_data(conn, pd.concat([users_df, new_u], ignore_index=True), "Users")
                            st.success("User Created")
                            st.rerun()
                        else: st.error("User exists")
            with c2:
                st.dataframe(users_df[['Username', 'Role']], hide_index=True, use_container_width=True)

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
                                update_data(conn, tasks_df, "Tasks")
                                st.balloons()
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
                        'Assigned Date': now.strftime('%d/%b/%Y'), 'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': jd.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 'Number of Findings': 0, 'Completion Status': 'In Progress'
                    }
                    update_data(conn, pd.concat([tasks_df, pd.DataFrame([new_r])], ignore_index=True), "Tasks")
                    st.success("Started!")
                    st.rerun()

if __name__ == "__main__":
    main()
