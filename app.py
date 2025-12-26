import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
BRANCH_OPTIONS = ["HQ", "SUZ", "HUR", "SSH", "LXR", "ASW", "ALX", "CAI", "GIZA", "MANS", "OTHERS"]
TASK_OPTIONS = [
    "Cash ", "Operation", "C.S"
]

st.set_page_config(page_title="IC Audit Manager Pro", layout="wide", page_icon="🛡️")

# --- DATABASE CONNECTION ---
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        tasks_df = conn.read(worksheet="Tasks", ttl=0)
        users_df = conn.read(worksheet="Users", ttl=0)
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        # Ensure standard columns exist
        for col in ['Number of Findings', 'Number of Transaction', 'Branch', 'Employee', 'Completion Status']:
            if col not in tasks_df.columns: tasks_df[col] = 0
        return conn, tasks_df, users_df
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)

def calculate_duration(start_date, start_time, end_date, end_time):
    try:
        fmt = '%d/%b/%Y %I:%M:%S %p'
        # Fix missing seconds
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

    # Data Type Safety
    if not users_df.empty:
        users_df['Username'] = users_df['Username'].astype(str)
        users_df['Password'] = users_df['Password'].astype(str)
    
    if not tasks_df.empty:
        # Ensure numbers are actual numbers for charts
        tasks_df['Number of Findings'] = pd.to_numeric(tasks_df['Number of Findings'], errors='coerce').fillna(0)
        tasks_df['Number of Transaction'] = pd.to_numeric(tasks_df['Number of Transaction'], errors='coerce').fillna(0)

    # --- LOGIN SCREEN ---
    if not st.session_state.logged_in:
        st.title("🛡️ Audit Portal Login")
        c1, c2 = st.columns([1, 2])
        with c1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Login"):
                user = users_df[(users_df['Username'] == u) & (users_df['Password'] == p)]
                if not user.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_info = user.iloc[0]
                    st.rerun()
                else: st.error("Access Denied")
        return

    # --- DASHBOARD ---
    user = st.session_state.user_info
    st.sidebar.title(f"👤 {user['Username']}")
    st.sidebar.caption(f"Role: {user['Role']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("✅ IC Audit Task Tracker")

    if user['Role'] == 'Admin':
        tabs = st.tabs(["📊 Executive Dashboard", "📝 Task Master List (Edit/Delete)", "➕ Assign Task", "⚙️ Users"])
    else:
        tabs = st.tabs(["📈 My Progress", "📝 My Active Tasks", "➕ New Task"])

    # ==========================================
    # ROLE: USER VIEW
    # ==========================================
    if user['Role'] != 'Admin':
        # --- TAB 1: USER PROGRESS CHART ---
        with tabs[0]:
            st.subheader(f"Performance Review: {user['Username']}")
            if not tasks_df.empty:
                my_tasks = tasks_df[tasks_df['Employee'] == user['Username']].copy()
                
                if not my_tasks.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Tasks Status**")
                        status_counts = my_tasks['Completion Status'].value_counts()
                        st.bar_chart(status_counts)
                    
                    with col2:
                        st.markdown("**Your Findings vs Transactions**")
                        # Simple aggregate for the user
                        totals = pd.DataFrame({
                            'Metric': ['Findings', 'Transactions'],
                            'Count': [my_tasks['Number of Findings'].sum(), my_tasks['Number of Transaction'].sum()]
                        })
                        st.bar_chart(totals, x='Metric', y='Count', color='Metric')
                    
                    st.metric("Total Completed Tasks", len(my_tasks[my_tasks['Completion Status']=='Completed']))
                else:
                    st.info("No stats available yet.")

        # --- TAB 2: MY ACTIVE TASKS ---
        with tabs[1]:
            st.subheader("Pending Action")
            active_mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            active_tasks = tasks_df[active_mask].copy()

            if active_tasks.empty:
                st.info("🎉 You have no pending tasks.")
            else:
                for idx, row in active_tasks.iterrows():
                    with st.expander(f"📌 {row['Task Description']} ({row['Branch']}) - Started {row['Assigned Time']}"):
                        c1, c2, c3 = st.columns([1, 1, 1])
                        # Inputs
                        curr_t = int(row['Number of Transaction'])
                        curr_f = int(row['Number of Findings'])
                        new_t = c1.number_input("Transactions", value=curr_t, min_value=0, key=f"ut_{idx}")
                        new_f = c2.number_input("Findings", value=curr_f, min_value=0, key=f"uf_{idx}")
                        
                        if c3.button("✅ Complete", key=f"ubtn_{idx}"):
                            now = datetime.now()
                            c_d = now.strftime('%d/%b/%Y')
                            c_t = now.strftime('%I:%M:%S %p')
                            dur = calculate_duration(row['Assigned Date'], row['Assigned Time'], c_d, c_t)
                            
                            tasks_df.at[idx, 'Number of Transaction'] = new_t
                            tasks_df.at[idx, 'Number of Findings'] = new_f
                            tasks_df.at[idx, 'Completion Status'] = 'Completed'
                            tasks_df.at[idx, 'Completion Date'] = c_d
                            tasks_df.at[idx, 'Completion Time'] = c_t
                            tasks_df.at[idx, 'Duration'] = dur
                            tasks_df.at[idx, 'Progress %'] = 1
                            
                            update_data(conn, tasks_df, "Tasks")
                            st.success("Completed!")
                            st.rerun()

        # --- TAB 3: NEW TASK ---
        with tabs[2]:
            st.subheader("Log New Audit")
            with st.form("user_new_task"):
                c1, c2 = st.columns(2)
                branch = c1.selectbox("Branch", BRANCH_OPTIONS)
                task_type = c2.selectbox("Task Type", TASK_OPTIONS)
                j_date = c1.date_input("Journal Date", datetime.now())
                
                if st.form_submit_button("Start Timer"):
                    now = datetime.now()
                    new_row = {
                        'Employee': user['Username'],
                        'Task Description': task_type,
                        'Branch': branch,
                        'Assigned Date': now.strftime('%d/%b/%Y'),
                        'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': j_date.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 'Number of Findings': 0,
                        'Completion Status': 'In Progress'
                    }
                    updated_df = pd.concat([tasks_df, pd.DataFrame([new_row])], ignore_index=True)
                    update_data(conn, updated_df, "Tasks")
                    st.success("Task Started!")
                    st.rerun()

    # ==========================================
    # ROLE: ADMIN VIEW
    # ==========================================
    else:
        # --- TAB 1: EXECUTIVE DASHBOARD ---
        with tabs[0]:
            st.subheader("📊 Audit Command Center")
            if not tasks_df.empty:
                # 1. KPI Row
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total Audits", len(tasks_df))
                k2.metric("Total Findings", int(tasks_df['Number of Findings'].sum()))
                k3.metric("Total Transactions", int(tasks_df['Number of Transaction'].sum()))
                k4.metric("Active Branches", tasks_df['Branch'].nunique())
                
                st.divider()
                
                # 2. Advanced Visuals
                c1, c2 = st.columns(2)
                
                with c1:
                    st.markdown("##### 🚨 Findings Risk by Branch")
                    # Chart: Total Findings per Branch
                    risk_data = tasks_df.groupby('Branch')['Number of Findings'].sum().sort_values(ascending=False)
                    st.bar_chart(risk_data, color="#ff4b4b")
                
                with c2:
                    st.markdown("##### 👥 User Productivity (Tasks)")
                    # Chart: Total Tasks per User
                    prod_data = tasks_df['Employee'].value_counts()
                    st.bar_chart(prod_data, color="#4b7bff")

                c3, c4 = st.columns(2)
                
                with c3:
                    st.markdown("##### 🌍 Branch Coverage by User")
                    # Chart: How many UNIQUE branches did each user visit?
                    coverage = tasks_df.groupby('Employee')['Branch'].nunique().sort_values(ascending=False)
                    st.bar_chart(coverage)
                    
                with c4:
                     st.markdown("##### 📝 Task Types Distribution")
                     type_dist = tasks_df['Task Description'].value_counts()
                     st.bar_chart(type_dist)

                # Export
                with st.expander("📥 Download Raw Data"):
                    st.dataframe(tasks_df)
                    csv = tasks_df.to_csv(index=False).encode('utf-8')
                    st.download_button("Download CSV", csv, "Full_Audit_Data.csv", "text/csv")
            else:
                st.info("No data to visualize.")

        # --- TAB 2: MASTER TASK LIST (EDIT/DELETE) ---
        with tabs[1]:
            st.subheader("📝 Master Task Manager (Edit/Delete)")
            
            # Filter Controls
            col_f1, col_f2 = st.columns(2)
            filter_status = col_f1.radio("Filter Status:", ["Active Only", "All Tasks (History)"], horizontal=True)
            search_branch = col_f2.selectbox("Filter by Branch (Optional)", ["All"] + BRANCH_OPTIONS)
            
            # Apply Filters
            if not tasks_df.empty:
                df_view = tasks_df.copy()
                
                if filter_status == "Active Only":
                    df_view = df_view[df_view['Completion Status'] != 'Completed']
                
                if search_branch != "All":
                    df_view = df_view[df_view['Branch'] == search_branch]
                
                if df_view.empty:
                    st.info("No tasks found matching filters.")
                else:
                    # Show list
                    for idx, row in df_view.iterrows():
                        # Color code headers
                        icon = "🟢" if row['Completion Status'] == 'Completed' else "Oo"
                        header = f"{icon} {row['Employee']} | {row['Task Description']} | {row['Branch']} | Findings: {row['Number of Findings']}"
                        
                        with st.expander(header):
                            c_edit1, c_edit2, c_edit3 = st.columns(3)
                            
                            # ALLOW EDITING OF CRITICAL FIELDS
                            new_trans = c_edit1.number_input("Transactions", value=int(row['Number of Transaction']), key=f"adm_t_{idx}")
                            new_find = c_edit2.number_input("Findings", value=int(row['Number of Findings']), key=f"adm_f_{idx}")
                            
                            # DELETE BUTTON
                            if c_edit3.button("🗑️ DELETE PERMANENTLY", key=f"adm_del_{idx}"):
                                tasks_df = tasks_df.drop(idx)
                                update_data(conn, tasks_df, "Tasks")
                                st.warning("Task Deleted.")
                                st.rerun()
                                
                            # UPDATE BUTTON
                            if st.button("💾 Save Changes", key=f"adm_save_{idx}"):
                                tasks_df.at[idx, 'Number of Transaction'] = new_trans
                                tasks_df.at[idx, 'Number of Findings'] = new_find
                                update_data(conn, tasks_df, "Tasks")
                                st.success("Record Updated.")
                                st.rerun()

        # --- TAB 3: ASSIGN TASK ---
        with tabs[2]:
            st.subheader("Assign Task to User")
            with st.form("admin_assign"):
                c1, c2 = st.columns(2)
                target = c1.selectbox("Assign To", users_df['Username'].unique()) if not users_df.empty else c1.text_input("User")
                branch = c2.selectbox("Branch", BRANCH_OPTIONS)
                task_type = c1.selectbox("Task Type", TASK_OPTIONS)
                j_date = c2.date_input("Journal Date", datetime.now())
                
                if st.form_submit_button("Assign Task"):
                    now = datetime.now()
                    new_row = {
                        'Employee': target,
                        'Task Description': task_type,
                        'Branch': branch,
                        'Assigned Date': now.strftime('%d/%b/%Y'),
                        'Assigned Time': now.strftime('%I:%M:%S %p'),
                        'Journal Date': j_date.strftime('%d/%b/%Y'),
                        'Number of Transaction': 0, 'Number of Findings': 0,
                        'Completion Status': 'In Progress'
                    }
                    updated_df = pd.concat([tasks_df, pd.DataFrame([new_row])], ignore_index=True)
                    update_data(conn, updated_df, "Tasks")
                    st.success(f"Assigned to {target}!")
                    st.rerun()

        # --- TAB 4: USERS ---
        with tabs[3]:
            st.subheader("User Management")
            c1, c2 = st.columns(2)
            with c1:
                new_u = st.text_input("New Username")
                new_p = st.text_input("New Password")
                new_r = st.selectbox("Role", ["User", "Admin"])
                if st.button("Create User"):
                    if new_u not in users_df['Username'].values:
                        new_data = pd.DataFrame([{'Username': new_u, 'Password': new_p, 'Role': new_r}])
                        update_data(conn, pd.concat([users_df, new_data], ignore_index=True), "Users")
                        st.success("User Added")
                        st.rerun()
                    else: st.error("User exists")
            with c2:
                st.dataframe(users_df[['Username', 'Role']], hide_index=True)

if __name__ == "__main__":
    main()
