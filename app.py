import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
BRANCH_OPTIONS = ["HQ", "SUZ", "HUR", "SSH", "LXR", "ASW", "ALX", "CAI", "GIZA", "MANS", "OTHERS"]
TASK_OPTIONS = [
    "Cash Count", "Operation Audit", "Stock Count", "ATM Review", 
    "Log Review", "Documentation Check", "Customer Service Review", "Other"
]

# --- MODERN UI SETUP ---
st.set_page_config(page_title="IC Audit Pro", layout="wide", page_icon="🛡️")

# Custom CSS for "Modern Look"
st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #4b7bff;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    div[data-testid="stExpander"] {
        background-color: #262730;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    h1 {color: #2c3e50;}
    h2, h3 {color: #34495e;}
    .stButton>button {
        border-radius: 20px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # ttl=5 prevents quota errors
        tasks_df = conn.read(worksheet="Tasks", ttl=5)
        users_df = conn.read(worksheet="Users", ttl=5)
        
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        
        # Ensure standard columns exist
        cols_needed = ['Number of Findings', 'Number of Transaction', 'Branch', 'Employee', 'Completion Status', 'Assigned Date', 'Assigned Time']
        for col in cols_needed:
            if col not in tasks_df.columns: tasks_df[col] = 0
            
        return conn, tasks_df, users_df
    except Exception as e:
        st.error(f"⚠️ Connection Error: {e}")
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear()

def calculate_duration(start_date, start_time, end_date, end_time):
    try:
        fmt = '%d/%b/%Y %I:%M:%S %p'
        if len(str(start_time).split(':')) == 2: start_time = f"{start_time}:00"
        if len(str(end_time).split(':')) == 2: end_time = f"{end_time}:00"
        
        dt_s = datetime.strptime(f"{start_date} {start_time}", fmt)
        dt_e = datetime.strptime(f"{end_date} {end_time}", fmt)
        diff = dt_e - dt_s
        secs = diff.total_seconds()
        if secs < 0: return "0h 0m"
        return f"{int(secs // 3600)}h {int((secs % 3600) // 60)}m"
    except: return "0h 0m"

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_info = None

    conn, tasks_df, users_df = get_data()

    if not users_df.empty:
        users_df['Username'] = users_df['Username'].astype(str)
        users_df['Password'] = users_df['Password'].astype(str)
    
    if not tasks_df.empty:
        tasks_df['Number of Findings'] = pd.to_numeric(tasks_df['Number of Findings'], errors='coerce').fillna(0)
        tasks_df['Number of Transaction'] = pd.to_numeric(tasks_df['Number of Transaction'], errors='coerce').fillna(0)

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
        st.markdown(f"### 👋 Welcome, {user['Username']}")
        st.caption(f"Role: {user['Role']}")
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()
        st.caption("Powered by Streamlit Cloud")

    # --- TABS LAYOUT ---
    if user['Role'] == 'Admin':
        st.title("📊 Executive Dashboard")
        tabs = st.tabs(["📈 Reports & Analytics", "📝 Task Master List", "➕ Assign Task", "👥 User Mgmt"])
    else:
        st.title("✅ My Audit Space")
        tabs = st.tabs(["🏠 Dashboard", "⚡ Active Tasks", "➕ New Log"])

    # ==========================================
    # ROLE: ADMIN VIEW
    # ==========================================
    if user['Role'] == 'Admin':
        # --- TAB 1: REPORTS ---
        with tabs[0]:
            if tasks_df.empty:
                st.info("No data available.")
            else:
                # Top KPIs
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total Audits", len(tasks_df), border=True)
                k2.metric("Total Findings", int(tasks_df['Number of Findings'].sum()), "High Risk", border=True)
                k3.metric("Transactions Checked", int(tasks_df['Number of Transaction'].sum()), border=True)
                k4.metric("Branches Covered", tasks_df['Branch'].nunique(), border=True)

                st.markdown("### 🔍 Drill-Down Analysis")
                st.info("Hierarchy: User → Branch → Task Type")

                # HIERARCHICAL REPORT GENERATION
                # We group by the specific order requested
                drill_df = tasks_df.groupby(['Employee', 'Branch', 'Task Description']).agg(
                    Count=('Task Description', 'count'),
                    Total_Transactions=('Number of Transaction', 'sum'),
                    Total_Findings=('Number of Findings', 'sum')
                )
                
                # Display as a styled table
                st.dataframe(
                    drill_df.style.background_gradient(cmap="Reds", subset=['Total_Findings']), 
                    use_container_width=True,
                    height=500
                )

                # Export
                csv = drill_df.to_csv().encode('utf-8')
                st.download_button("📥 Download Drill-Down Report", csv, "Audit_Hierarchy_Report.csv", "text/csv")

                st.divider()
                
                # Visuals
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**🚨 Findings by Branch**")
                    st.bar_chart(tasks_df.groupby('Branch')['Number of Findings'].sum(), color="#ff4b4b")
                with c2:
                    st.markdown("**📊 Workload Distribution**")
                    st.bar_chart(tasks_df['Employee'].value_counts(), color="#4b7bff")

        # --- TAB 2: EDIT/DELETE ---
        with tabs[1]:
            st.markdown("#### 🛠️ Manage Records")
            c_fil1, c_fil2 = st.columns(2)
            f_status = c_fil1.selectbox("Status Filter", ["Active Only", "All History"])
            f_branch = c_fil2.selectbox("Branch Filter", ["All"] + BRANCH_OPTIONS)

            df_view = tasks_df.copy()
            if f_status == "Active Only": df_view = df_view[df_view['Completion Status'] != 'Completed']
            if f_branch != "All": df_view = df_view[df_view['Branch'] == f_branch]

            if df_view.empty:
                st.warning("No records found.")
            else:
                for idx, row in df_view.iterrows():
                    status_icon = "✅" if row['Completion Status'] == 'Completed' else "⏳"
                    lbl = f"{status_icon} **{row['Employee']}** | {row['Task Description']} @ {row['Branch']}"
                    
                    with st.expander(lbl):
                        with st.form(key=f"adm_edit_{idx}"):
                            c1, c2, c3 = st.columns(3)
                            n_trans = c1.number_input("Transactions", value=int(row['Number of Transaction']))
                            n_find = c2.number_input("Findings", value=int(row['Number of Findings']))
                            
                            c_act1, c_act2 = st.columns(2)
                            is_save = c_act1.form_submit_button("💾 Update Data")
                            is_del = c_act2.form_submit_button("🗑️ DELETE Task", type="primary")

                            if is_save:
                                tasks_df.at[idx, 'Number of Transaction'] = n_trans
                                tasks_df.at[idx, 'Number of Findings'] = n_find
                                update_data(conn, tasks_df, "Tasks")
                                st.success("Updated!")
                                st.rerun()
                            
                            if is_del:
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

        # --- TAB 4: USERS ---
        with tabs[3]:
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
        # --- TAB 1: DASHBOARD ---
        with tabs[0]:
            if not tasks_df.empty:
                my_df = tasks_df[tasks_df['Employee'] == user['Username']]
                if not my_df.empty:
                    c1, c2 = st.columns(2)
                    c1.metric("Tasks Completed", len(my_df[my_df['Completion Status']=='Completed']))
                    c2.metric("Pending", len(my_df[my_df['Completion Status']!='Completed']))
                    st.bar_chart(my_df['Task Description'].value_counts())
                else: st.info("No activity yet.")

        # --- TAB 2: ACTIVE TASKS ---
        with tabs[1]:
            mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            active = tasks_df[mask].copy()
            
            if active.empty:
                st.success("🎉 All caught up! No pending tasks.")
            else:
                for idx, row in active.iterrows():
                    with st.expander(f"📌 {row['Task Description']} @ {row['Branch']}", expanded=True):
                        st.caption(f"Started: {row['Assigned Time']}")
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

        # --- TAB 3: NEW LOG ---
        with tabs[2]:
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
