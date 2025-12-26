import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="IC Task Tracker Pro", layout="wide")

# --- DATABASE CONNECTION ---
def get_data():
    # Use the connection we will configure in Streamlit Secrets
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Read data with ttl=0 (Time To Live = 0) so it doesn't cache old data
    try:
        tasks_df = conn.read(worksheet="Tasks", ttl=0)
        users_df = conn.read(worksheet="Users", ttl=0)
        # Ensure dataframes aren't empty/None
        if tasks_df is None: tasks_df = pd.DataFrame()
        if users_df is None: users_df = pd.DataFrame()
        return conn, tasks_df, users_df
    except Exception as e:
        st.error(f"Error connecting to Google Sheets. Check your Secrets configuration. Error: {e}")
        return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)

def calculate_duration(start_date, start_time, end_date, end_time):
    try:
        # Standardize format
        fmt = '%d/%b/%Y %I:%M:%S %p'
        # Add seconds if missing
        if len(str(start_time).split(':')) == 2: start_time = f"{start_time}:00"
        if len(str(end_time).split(':')) == 2: end_time = f"{end_time}:00"
        
        dt_start = datetime.strptime(f"{start_date} {start_time}", fmt)
        dt_end = datetime.strptime(f"{end_date} {end_time}", fmt)
        
        diff = dt_end - dt_start
        total_seconds = diff.total_seconds()
        
        if total_seconds < 0: return "0h 0m"
        return f"{int(total_seconds // 3600)}h {int((total_seconds % 3600) // 60)}m"
    except:
        return "0h 0m"

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_info = None

    # Load Data LIVE from Google Sheets
    conn, tasks_df, users_df = get_data()

    # Clean user data types for login check
    if not users_df.empty:
        users_df['Username'] = users_df['Username'].astype(str)
        users_df['Password'] = users_df['Password'].astype(str)

    # --- LOGIN SCREEN ---
    if not st.session_state.logged_in:
        st.title("🔒 Login")
        c1, c2 = st.columns([1, 2])
        with c1:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if users_df.empty:
                    st.error("Database connection failed or Users sheet is empty.")
                else:
                    user_row = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
                    if not user_row.empty:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user_row.iloc[0]
                        st.rerun()
                    else:
                        st.error("Invalid Username or Password")
        return

    # --- DASHBOARD ---
    user = st.session_state.user_info
    st.sidebar.title(f"👤 {user['Username']}")
    st.sidebar.info(f"Role: {user['Role']}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("✅ Task Tracker Cloud")
    
    # Define Tabs
    if user['Role'] == 'Admin':
        tabs = st.tabs(["📝 Task Management", "➕ Assign Task", "📊 Reports", "⚙️ User Management"])
    else:
        tabs = st.tabs(["📝 My Tasks", "➕ Add Task"])

    # === TAB 1: VIEW & COMPLETE ===
    with tabs[0]:
        st.subheader("Active Tasks")
        
        # Filter Logic
        if not tasks_df.empty:
            if user['Role'] == 'Admin':
                # Admin sees all tasks not completed
                mask = tasks_df['Completion Status'] != 'Completed'
            else:
                # User sees only their own tasks not completed
                mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            
            active_tasks = tasks_df[mask].copy()
            
            if active_tasks.empty:
                st.info("No active tasks found.")
            else:
                # Iterate through filtered tasks
                for idx, row in active_tasks.iterrows():
                    with st.expander(f"{row['Employee']}: {row['Task Description']} ({row['Branch']})"):
                        c1, c2 = st.columns(2)
                        d = c1.date_input("Done Date", datetime.now(), key=f"d{idx}")
                        t = c1.time_input("Done Time", datetime.now(), key=f"t{idx}")
                        
                        if c2.button("Mark Complete", key=f"btn{idx}"):
                            c_d_str = d.strftime('%d/%b/%Y')
                            c_t_str = t.strftime('%I:%M:%S %p')
                            dur = calculate_duration(row['Assigned Date'], row['Assigned Time'], c_d_str, c_t_str)
                            
                            # Update the original DataFrame using the index
                            tasks_df.at[idx, 'Completion Status'] = 'Completed'
                            tasks_df.at[idx, 'Completion Date'] = c_d_str
                            tasks_df.at[idx, 'Completion Time'] = c_t_str
                            tasks_df.at[idx, 'Duration'] = dur
                            tasks_df.at[idx, 'Progress %'] = 1
                            
                            # Push update to Google Sheets
                            update_data(conn, tasks_df, "Tasks")
                            st.success("Task updated successfully!")
                            st.rerun()
        else:
            st.warning("Task database is empty.")

    # === TAB 2: ADD TASK ===
    with tabs[1]:
        st.subheader("New Task")
        with st.form("new_task"):
            c1, c2 = st.columns(2)
            
            # Target User Selection
            if user['Role'] == 'Admin' and not users_df.empty:
                target = c1.selectbox("Assign To", users_df['Username'].unique())
            else:
                target = c1.text_input("Assign To", value=user['Username'], disabled=True)
                
            desc = c2.text_input("Description")
            branch = c1.text_input("Branch (e.g. SUZ, HUR)", value="HQ")
            
            a_date = c2.date_input("Assigned Date", datetime.now())
            a_time = c2.time_input("Assigned Time", datetime.now())

            if st.form_submit_button("Create Task"):
                new_data = {
                    'Employee': target,
                    'Task Description': desc,
                    'Branch': branch,
                    'Assigned Date': a_date.strftime('%d/%b/%Y'),
                    'Assigned Time': a_time.strftime('%I:%M:%S %p'),
                    'Completion Status': 'In Progress',
                    'Progress %': 0
                }
                # Add new row
                new_df = pd.DataFrame([new_data])
                updated_df = pd.concat([tasks_df, new_df], ignore_index=True)
                
                update_data(conn, updated_df, "Tasks")
                st.success("Task created!")
                st.rerun()

    # === TAB 3: REPORTS (ADMIN ONLY) ===
    if user['Role'] == 'Admin':
        with tabs[2]:
            st.subheader("Analytics")
            if not tasks_df.empty:
                # Helper to parse minutes
                def parse_mins(d_str):
                    try:
                        import re
                        if pd.isna(d_str): return 0
                        h = int(re.search(r'(\d+)h', str(d_str)).group(1)) if 'h' in str(d_str) else 0
                        m = int(re.search(r'(\d+)m', str(d_str)).group(1)) if 'm' in str(d_str) else 0
                        return h*60 + m
                    except: return 0

                tasks_df['Mins'] = tasks_df['Duration'].apply(parse_mins)
                
                # Simple pivot table
                report = tasks_df.groupby(['Employee', 'Branch']).agg(
                    Count=('Task Description', 'count'),
                    Avg_Mins=('Mins', 'mean')
                ).reset_index()
                report['Avg_Mins'] = report['Avg_Mins'].round(1)
                
                st.dataframe(report, use_container_width=True)
            else:
                st.info("No data to report.")

    # === TAB 4: USER MGMT (ADMIN ONLY) ===
    if user['Role'] == 'Admin':
        with tabs[3]:
            st.subheader("Add User")
            u = st.text_input("New Username")
            p = st.text_input("New Password")
            r = st.selectbox("Role", ["User", "Admin"])
            
            if st.button("Create User"):
                if u in users_df['Username'].values:
                    st.error("User already exists!")
                else:
                    new_user = pd.DataFrame([{'Username': u, 'Password': p, 'Role': r}])
                    updated_users = pd.concat([users_df, new_user], ignore_index=True)
                    update_data(conn, updated_users, "Users")
                    st.success(f"User {u} created!")
                    st.rerun()

if __name__ == "__main__":
    main()
