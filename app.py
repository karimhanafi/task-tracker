import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION: EDIT YOUR DROPDOWN LISTS HERE ---
BRANCH_OPTIONS = [
    "HQ", "SUZ", "HUR", "SSH", "LXR", "ASW", 
    "ALX", "CAI", "GIZA", "MANS", "OTHERS"
]

TASK_OPTIONS = [
    "Cash ", 
    "Operation ", 
    "C.S"
]

st.set_page_config(page_title="IC Task Tracker Pro", layout="wide")

# --- DATABASE CONNECTION ---
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        tasks_df = conn.read(worksheet="Tasks", ttl=0)
        users_df = conn.read(worksheet="Users", ttl=0)
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        # Ensure numeric columns exist and fill NaNs
        if 'Number of Findings' not in tasks_df.columns: tasks_df['Number of Findings'] = 0
        if 'Number of Transaction' not in tasks_df.columns: tasks_df['Number of Transaction'] = 0
        return conn, tasks_df, users_df
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)

def calculate_duration(start_date, start_time, end_date, end_time):
    try:
        fmt = '%d/%b/%Y %I:%M:%S %p'
        if len(str(start_time).split(':')) == 2: start_time = f"{start_time}:00"
        if len(str(end_time).split(':')) == 2: end_time = f"{end_time}:00"
        
        dt_start = datetime.strptime(f"{start_date} {start_time}", fmt)
        dt_end = datetime.strptime(f"{end_date} {end_time}", fmt)
        
        diff = dt_end - dt_start
        total_seconds = diff.total_seconds()
        if total_seconds < 0: return "0h 0m"
        return f"{int(total_seconds // 3600)}h {int((total_seconds % 3600) // 60)}m"
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

    # --- LOGIN SCREEN ---
    if not st.session_state.logged_in:
        st.title("🔒 Audit Team Login")
        c1, c2 = st.columns([1, 2])
        with c1:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                user_row = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
                if not user_row.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_row.iloc[0]
                    st.rerun()
                else:
                    st.error("Invalid Credentials")
        return

    # --- DASHBOARD ---
    user = st.session_state.user_info
    st.sidebar.title(f"👤 {user['Username']}")
    st.sidebar.info(f"Role: {user['Role']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("✅ IC Audit Task Tracker")
    
    if user['Role'] == 'Admin':
        tabs = st.tabs(["📝 Active Tasks", "➕ New Task", "📊 Admin Reports", "⚙️ Users"])
    else:
        tabs = st.tabs(["📝 My Tasks", "➕ New Task"])

    # === TAB 1: ACTIVE TASKS (UPDATED LOGIC) ===
    with tabs[0]:
        st.subheader("Tasks In Progress")
        if not tasks_df.empty:
            if user['Role'] == 'Admin':
                mask = tasks_df['Completion Status'] != 'Completed'
            else:
                mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            
            active_tasks = tasks_df[mask].copy()
            
            if active_tasks.empty:
                st.info("No pending tasks.")
            else:
                for idx, row in active_tasks.iterrows():
                    # Card Header
                    with st.expander(f"{row['Employee']} | {row['Task Description']} ({row['Branch']})"):
                        st.caption(f"Started: {row['Assigned Date']} at {row['Assigned Time']}")
                        
                        # --- NEW: User Inputs for Findings & Transactions ---
                        c1, c2, c3 = st.columns([1, 1, 1])
                        
                        # Get existing values or default to 0
                        current_trans = int(row['Number of Transaction']) if pd.notna(row['Number of Transaction']) else 0
                        current_find = int(row['Number of Findings']) if pd.notna(row['Number of Findings']) else 0
                        
                        # Input fields (User edits these BEFORE completing)
                        new_trans = c1.number_input("Transactions", value=current_trans, min_value=0, step=1, key=f"tr_{idx}")
                        new_find = c2.number_input("Findings", value=current_find, min_value=0, step=1, key=f"fn_{idx}")
                        
                        # --- NEW: Auto-Complete Button ---
                        if c3.button("✅ Mark Complete", key=f"btn{idx}"):
                            # 1. Capture AUTO Time
                            now = datetime.now()
                            c_d_str = now.strftime('%d/%b/%Y')
                            c_t_str = now.strftime('%I:%M:%S %p')
                            
                            # 2. Calculate Duration
                            dur = calculate_duration(row['Assigned Date'], row['Assigned Time'], c_d_str, c_t_str)
                            
                            # 3. Update DataFrame
                            tasks_df.at[idx, 'Number of Transaction'] = new_trans
                            tasks_df.at[idx, 'Number of Findings'] = new_find
                            tasks_df.at[idx, 'Completion Status'] = 'Completed'
                            tasks_df.at[idx, 'Completion Date'] = c_d_str
                            tasks_df.at[idx, 'Completion Time'] = c_t_str
                            tasks_df.at[idx, 'Duration'] = dur
                            tasks_df.at[idx, 'Progress %'] = 1
                            
                            # 4. Save to Cloud
                            update_data(conn, tasks_df, "Tasks")
                            st.success(f"Task Completed at {c_t_str}!")
                            st.rerun()

    # === TAB 2: ADD NEW TASK ===
    with tabs[1]:
        st.subheader("Log Audit Task")
        with st.form("new_task"):
            c1, c2 = st.columns(2)
            
            # User Selection
            if user['Role'] == 'Admin' and not users_df.empty:
                target = c1.selectbox("Assign To", users_df['Username'].unique())
            else:
                target = c1.text_input("Assign To", value=user['Username'], disabled=True)
            
            # Standardized Inputs
            branch = c2.selectbox("Branch", BRANCH_OPTIONS)
            task_desc = c1.selectbox("Task Type", TASK_OPTIONS)
            journal_date = c2.date_input("Journal Date", datetime.now())
            
            # Note: We initialize findings/transactions to 0 here. 
            # The User will update them in Tab 1 before completing.
            
            if st.form_submit_button("Start Task"):
                now_date = datetime.now().strftime('%d/%b/%Y')
                now_time = datetime.now().strftime('%I:%M:%S %p')
                
                new_data = {
                    'Employee': target,
                    'Task Description': task_desc,
                    'Branch': branch,
                    'Assigned Date': now_date,
                    'Assigned Time': now_time,
                    'Journal Date': journal_date.strftime('%d/%b/%Y'),
                    'Number of Transaction': 0, # Default 0
                    'Number of Findings': 0,    # Default 0
                    'Completion Status': 'In Progress',
                    'Progress %': 0
                }
                
                new_df = pd.DataFrame([new_data])
                updated_df = pd.concat([tasks_df, new_df], ignore_index=True)
                update_data(conn, updated_df, "Tasks")
                st.success(f"Task Started at {now_time}!")
                st.rerun()

    # === TAB 3: REPORTS (ADMIN ONLY) ===
    if user['Role'] == 'Admin':
        with tabs[2]:
            st.subheader("Detailed Audit Report")
            if not tasks_df.empty:
                # 1. Clean Data
                tasks_df['Number of Findings'] = pd.to_numeric(tasks_df['Number of Findings'], errors='coerce').fillna(0)
                tasks_df['Number of Transaction'] = pd.to_numeric(tasks_df['Number of Transaction'], errors='coerce').fillna(0)
                
                def parse_mins(d_str):
                    try:
                        import re
                        if pd.isna(d_str): return 0
                        h = int(re.search(r'(\d+)h', str(d_str)).group(1)) if 'h' in str(d_str) else 0
                        m = int(re.search(r'(\d+)m', str(d_str)).group(1)) if 'm' in str(d_str) else 0
                        return h*60 + m
                    except: return 0

                tasks_df['Mins'] = tasks_df['Duration'].apply(parse_mins)
                
                # 2. Report Logic
                report = tasks_df.groupby(['Branch', 'Employee', 'Task Description']).agg(
                    Total_Tasks=('Task Description', 'count'),
                    Total_Findings=('Number of Findings', 'sum'),
                    Total_Transactions=('Number of Transaction', 'sum'),
                    Avg_Time_Mins=('Mins', 'mean')
                ).reset_index()
                
                report['Avg_Time_Mins'] = report['Avg_Time_Mins'].round(1)
                
                # 3. Display
                st.dataframe(report, use_container_width=True)
                csv = report.to_csv(index=False).encode('utf-8')
                st.download_button("Download Report", csv, "Audit_Report.csv", "text/csv")
            else:
                st.info("No data available.")

    # === TAB 4: USER MGMT (ADMIN ONLY) ===
    if user['Role'] == 'Admin':
        with tabs[3]:
            st.subheader("Create User")
            u = st.text_input("New Username")
            p = st.text_input("New Password")
            r = st.selectbox("Role", ["User", "Admin"])
            if st.button("Add User"):
                if u in users_df['Username'].values:
                    st.error("Exists!")
                else:
                    new_user = pd.DataFrame([{'Username': u, 'Password': p, 'Role': r}])
                    updated_users = pd.concat([users_df, new_user], ignore_index=True)
                    update_data(conn, updated_users, "Users")
                    st.success("Created!")
                    st.rerun()

if __name__ == "__main__":
    main()
