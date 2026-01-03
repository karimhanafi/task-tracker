import streamlit as st
import pandas as pd
import sqlite3
import time
import pytz
import io
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
</style>
""", unsafe_allow_html=True)

# --- 2. CONSTANTS ---
BRANCH_OPTIONS = ["NAL","PET","DMP","MND","ADT","BRG","MIN","KSH","RSH","DMN","BNH","ALX","XND","SAN","SMO","TNT","ZGZ"]
TASK_OPTIONS = ["Cash", "Operation", "C.S"]
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# --- 3. SMART DATE FUNCTIONS ---
def get_current_time():
    return datetime.now(EGYPT_TZ)

def parse_date_robustly(date_val):
    if pd.isna(date_val) or date_val == "": return None
    if isinstance(date_val, (pd.Timestamp, datetime)): return date_val
    date_str = str(date_val).strip()
    for fmt in ['%d/%b/%Y', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d']:
        try: return datetime.strptime(date_str, fmt)
        except ValueError: continue
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
        cols_needed = ["Employee", "Task Description", "Branch", "Assigned Date", "Assigned Time", "Completion Status", "Completion Date", "Completion Time", "Duration", "Progress %", "Journal Date", "Number of Findings", "Number of Transaction"]
        for col in cols_needed:
            if col not in tasks_df.columns: tasks_df[col] = ""
        return conn, tasks_df, users_df
    except: return conn, pd.DataFrame(), pd.DataFrame()

def update_data(conn, df, worksheet_name):
    try:
        for col in ['Assigned Date', 'Completion Date', 'Journal Date']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: parse_date_robustly(x).strftime('%d/%b/%Y') if parse_date_robustly(x) else x)
        df = df.fillna("") 
        conn.update(worksheet=worksheet_name, data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"⚠️ Save Error: {e}"); return False

# --- 5. VISUAL STYLING (STREAMLIT) ---
def color_status(val):
    if val == 'Completed': return 'background-color: #90EE90; color: black; font-weight: bold;'
    elif val == 'In Progress': return 'background-color: #FFB347; color: black; font-weight: bold;'
    return ''

def excel_color_status(val):
    if val == 'Completed': return 'background-color: #C6EFCE; color: #006100;'
    elif val == 'In Progress': return 'background-color: #FFEB9C; color: #9C0006;'
    return ''

# --- 6. MAIN APPLICATION ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_info = None

    conn, tasks_df, users_df = get_data()

    if users_df.empty:
        st.warning("⚠️ **System Cooling Down**"); st.info("Please wait 60s."); st.stop() 

    users_df['Username'] = users_df['Username'].astype(str)
    users_df['Password'] = users_df['Password'].astype(str)
    
    tasks_df_logic = tasks_df.copy()
    if not tasks_df_logic.empty:
        for col in ['Number of Findings', 'Number of Transaction']:
            if col in tasks_df_logic.columns: tasks_df_logic[col] = pd.to_numeric(tasks_df_logic[col], errors='coerce').fillna(0)
        for col in ['Journal Date', 'Assigned Date']:
            if col in tasks_df_logic.columns: tasks_df_logic[col] = tasks_df_logic[col].apply(parse_date_robustly)

    # LOGIN
    if not st.session_state.logged_in:
        st.markdown("<h1 style='text-align: center;'>🛡️ IC Audit Portal</h1>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            with st.form("login_form"):
                u = st.text_input("Username"); p = st.text_input("Password", type="password")
                if st.form_submit_button("Login Securely", type="primary"):
                    user = users_df[(users_df['Username'] == u) & (users_df['Password'] == p)]
                    if not user.empty:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user.iloc[0]; st.rerun()
                    else: st.error("❌ Access Denied")
        return

    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### 👋 {user['Username']}")
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()
        st.divider()

    # ADMIN
    if user['Role'] == 'Admin':
        st.title("📊 Executive Dashboard")
        tabs = st.tabs(["📈 Analytics", "⚡ My Tasks", "📝 Manage Tasks", "➕ Assign Task", "💻 SQL Tool", "👥 User Mgmt", "📑 Custom Report"])

        # 1. Analytics
        with tabs[0]:
            st.header("Drill-Down Analysis")
            if tasks_df_logic.empty: st.info("No data available.")
            else:
                c1, c2, c3, c4, c5 = st.columns(5)
                df_f = tasks_df_logic.copy()
                with c1: 
                    d = sorted(df_f['Journal Date'].dropna().dt.date.unique()) if 'Journal Date' in df_f else []
                    if d: 
                        s = st.multiselect("Journal Date", d); 
                        if s: df_f = df_f[df_f['Journal Date'].dt.date.isin(s)]
                with c2:
                    d = sorted(df_f['Assigned Date'].dropna().dt.date.unique()) if 'Assigned Date' in df_f else []
                    if d:
                        s = st.multiselect("Assigned Date", d)
                        if s: df_f = df_f[df_f['Assigned Date'].dt.date.isin(s)]
                with c3:
                    o = list(df_f['Branch'].unique()) if 'Branch' in df_f else []
                    s = st.multiselect("Branch", o)
                    if s: df_f = df_f[df_f['Branch'].isin(s)]
                with c4:
                    o = list(df_f['Task Description'].unique()) if 'Task Description' in df_f else []
                    s = st.multiselect("Task", o)
                    if s: df_f = df_f[df_f['Task Description'].isin(s)]
                with c5:
                    o = list(df_f['Employee'].unique()) if 'Employee' in df_f else []
                    s = st.multiselect("Employee", o)
                    if s: df_f = df_f[df_f['Employee'].isin(s)]

                st.divider()
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Audits", len(df_f))
                k2.metric("Findings", int(df_f['Number of Findings'].sum() if 'Number of Findings' in df_f else 0))
                k3.metric("Transactions", f"{int(df_f['Number of Transaction'].sum() if 'Number of Transaction' in df_f else 0):,}")
                k4.metric("Branches", df_f['Branch'].nunique() if 'Branch' in df_f else 0)

                st.subheader("Detailed Audit List")
                if not df_f.empty:
                    cols = ['Employee', 'Branch', 'Task Description', 'Assigned Date', 'Assigned Time', 'Journal Date', 'Completion Date', 'Completion Time', 'Duration', 'Number of Transaction', 'Number of Findings']
                    disp = df_f[[c for c in cols if c in df_f.columns]].copy()
                    for c in ['Assigned Date', 'Journal Date']:
                        if c in disp.columns: disp[c] = disp[c].dt.strftime('%d/%b/%Y')
                    disp.index = range(1, len(disp)+1)
                    st.dataframe(disp, use_container_width=True)

        # 2. My Tasks
        with tabs[1]:
            st.header("⚡ My Active Tasks")
            mask = (tasks_df['Completion Status'] != 'Completed') & (tasks_df['Employee'] == user['Username'])
            my_act = tasks_df[mask].copy()
            if my_act.empty: st.success("No pending tasks.")
            for idx, row in my_act.iterrows():
                with st.expander(f"📌 {row['Task Description']} @ {row['Branch']}", expanded=True):
                    with st.form(key=f"adm_tsk_{idx}"):
                        c1, c2 = st.columns(2)
                        nt = c1.number_input("Trans", value=int(float(row.get('Number of Transaction',0) or 0)))
                        nf = c2.number_input("Finds", value=int(float(row.get('Number of Findings',0) or 0)))
                        if st.form_submit_button("✅ Complete", type="primary"):
                            now = get_current_time()
                            cd, ct = now.strftime('%d/%b/%Y'), now.strftime('%I:%M:%S %p')
                            dur = calculate_duration(row.get('Assigned Date'), row.get('Assigned Time'), cd, ct)
                            tasks_df.loc[idx, ['Number of Transaction','Number of Findings','Completion Status','Completion Date','Completion Time','Duration','Progress %']] = [nt, nf, 'Completed', cd, ct, dur, 1]
                            if update_data(conn, tasks_df, "Tasks"): st.balloons(); time.sleep(2); st.rerun()

        # 3. Edit
        with tabs[2]:
            st.markdown("#### 🛠️ Manage Tasks")
            fb = st.selectbox("Filter Branch", ["All"] + BRANCH_OPTIONS)
            dv = tasks_df.copy()
            if fb != "All": dv = dv[dv['Branch'] == fb]
            for idx, row in dv.iterrows():
                with st.expander(f"{'✅' if row['Completion Status']=='Completed' else '⏳'} {row['Employee']} | {row['Task Description']} @ {row['Branch']}"):
                    with st.form(key=f"edt_{idx}"):
                        c1, c2 = st.columns(2)
                        nt = c1.number_input("Trans", value=int(float(row.get('Number of Transaction',0) or 0)))
                        nf = c2.number_input("Finds", value=int(float(row.get('Number of Findings',0) or 0)))
                        c3, c4 = st.columns(2)
                        if c3.form_submit_button("💾 Save"):
                            tasks_df.loc[idx, ['Number of Transaction','Number of Findings']] = [nt, nf]
                            if update_data(conn, tasks_df, "Tasks"): st.success("Saved"); time.sleep(2); st.rerun()
                        if c4.form_submit_button("🗑️ Delete"):
                            tasks_df = tasks_df.drop(idx)
                            if update_data(conn, tasks_df, "Tasks"): st.warning("Deleted"); time.sleep(2); st.rerun()

        # 4. Assign
        with tabs[3]:
            st.markdown("#### ➕ Assign")
            with st.form("new_task"):
                c1, c2 = st.columns(2)
                tgt = c1.selectbox("User", users_df['Username'].unique())
                brn = c2.selectbox("Branch", BRANCH_OPTIONS)
                typ = c1.selectbox("Task", TASK_OPTIONS)
                jdt = c2.date_input("Journal Date")
                if st.form_submit_button("Assign", type="primary"):
                    now = get_current_time()
                    nr = {'Employee': tgt, 'Task Description': typ, 'Branch': brn, 
                          'Assigned Date': now.strftime('%d/%b/%Y'), 'Assigned Time': now.strftime('%I:%M:%S %p'),
                          'Journal Date': jdt.strftime('%d/%b/%Y'), 'Completion Status': 'In Progress', 
                          'Number of Findings': 0, 'Number of Transaction': 0}
                    if update_data(conn, pd.concat([tasks_df, pd.DataFrame([nr])], ignore_index=True), "Tasks"):
                        st.success("Assigned!"); time.sleep(2); st.rerun()

        # 5. SQL
        with tabs[4]:
            q = st.text_area("SQL", "SELECT * FROM df")
            if st.button("Run"):
                try:
                    c = sqlite3.connect(':memory:'); tasks_df.to_sql('df', c, index=False)
                    st.dataframe(pd.read_sql_query(q, c))
                except Exception as e: st.error(e)

        # 6. Users
        with tabs[5]:
            with st.form("new_usr"):
                u = st.text_input("User"); p = st.text_input("Pass"); r = st.selectbox("Role", ["User", "Admin"])
                if st.form_submit_button("Add"):
                    if update_data(conn, pd.concat([users_df, pd.DataFrame([{'Username':u,'Password':p,'Role':r}])], ignore_index=True), "Users"):
                        st.success("Added"); st.rerun()
            st.dataframe(users_df)

        # 7. REPORT (RESTORED ALL FILTERS)
        with tabs[6]:
            st.header("📑 One-Sheet Report Generator")
            with st.expander("🔻 Report Filters (Leave blank to select ALL)", expanded=True):
                with st.form("rep_form"):
                    # Row 1: Dates
                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        d1 = sorted(tasks_df_logic['Journal Date'].dropna().dt.date.unique()) if 'Journal Date' in tasks_df_logic else []
                        s_jd = st.multiselect("Journal Date", d1)
                    with col_r2:
                        d2 = sorted(tasks_df_logic['Assigned Date'].dropna().dt.date.unique()) if 'Assigned Date' in tasks_df_logic else []
                        s_ad = st.multiselect("Assigned Date", d2)

                    # Row 2: Branch & Task
                    col_r3, col_r4 = st.columns(2)
                    with col_r3:
                        opts = list(tasks_df_logic['Branch'].unique()) if 'Branch' in tasks_df_logic else []
                        s_br = st.multiselect("Branch", opts)
                    with col_r4:
                        opts = list(tasks_df_logic['Task Description'].unique()) if 'Task Description' in tasks_df_logic else []
                        s_tk = st.multiselect("Task", opts)

                    # Row 3: Employee & Status
                    col_r5, col_r6 = st.columns(2)
                    with col_r5:
                        opts = list(tasks_df_logic['Employee'].unique()) if 'Employee' in tasks_df_logic else []
                        s_em = st.multiselect("Employee", opts)
                    with col_r6:
                        opts = ["Completed", "In Progress"]
                        s_st = st.multiselect("Status", opts)

                    submitted = st.form_submit_button("🚀 Generate Report", type="primary")

            if submitted:
                rep_df = tasks_df_logic.copy()
                
                # Apply Filters
                if s_jd: rep_df = rep_df[rep_df['Journal Date'].dt.date.isin(s_jd)]
                if s_ad: rep_df = rep_df[rep_df['Assigned Date'].dt.date.isin(s_ad)]
                if s_br: rep_df = rep_df[rep_df['Branch'].isin(s_br)]
                if s_tk: rep_df = rep_df[rep_df['Task Description'].isin(s_tk)]
                if s_em: rep_df = rep_df[rep_df['Employee'].isin(s_em)]
                if s_st: rep_df = rep_df[rep_df['Completion Status'].isin(s_st)]

                # Format Dates
                for c in ['Assigned Date', 'Journal Date']:
                    if c in rep_df.columns: rep_df[c] = rep_df[c].dt.strftime('%d/%b/%Y')

                # Create Summary
                summ = rep_df.groupby('Employee').apply(lambda x: pd.Series({
                    'Completed': (x['Completion Status']=='Completed').sum(),
                    'Pending': (x['Completion Status']!='Completed').sum(),
                    'Total': len(x)
                })).reset_index()
                summ['Progress %'] = (summ['Completed'] / summ['Total']).fillna(0)

                # Show Preview
                st.subheader("Preview: Summary")
                st.dataframe(summ.style.bar(subset=['Progress %'], color='#90EE90', vmin=0, vmax=1), use_container_width=True)
                
                st.subheader("Preview: Detailed Data")
                cols = ['Assigned Date','Employee','Branch','Task Description','Journal Date','Completion Status','Number of Transaction','Number of Findings']
                det_df = rep_df[[c for c in cols if c in rep_df.columns]].copy()
                st.dataframe(det_df.style.map(color_status, subset=['Completion Status']), use_container_width=True)

                # GENERATE EXCEL (ONE SHEET)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    wb = writer.book
                    ws = wb.add_worksheet('Audit Report')
                    writer.sheets['Audit Report'] = ws

                    # Formats
                    fmt_green = wb.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
                    fmt_orange = wb.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C0006'})

                    # Write Summary
                    ws.write_string(0, 0, "EXECUTIVE SUMMARY", wb.add_format({'bold':True, 'font_size':14}))
                    summ.to_excel(writer, sheet_name='Audit Report', startrow=2, index=False)
                    ws.conditional_format(3, 4, 3+len(summ), 4, {'type': 'data_bar', 'bar_color': '#63C384'})

                    # Write Detail
                    start_row = len(summ) + 6
                    ws.write_string(start_row, 0, "DETAILED AUDIT LOG", wb.add_format({'bold':True, 'font_size':14}))
                    det_df.to_excel(writer, sheet_name='Audit Report', startrow=start_row+2, index=False)

                    # Highlight Status
                    if 'Completion Status' in det_df.columns:
                        status_col_idx = det_df.columns.get_loc('Completion Status')
                        ws.conditional_format(start_row+3, status_col_idx, start_row+3+len(det_df), status_col_idx,
                                              {'type': 'cell', 'criteria': '==', 'value': '"Completed"', 'format': fmt_green})
                        ws.conditional_format(start_row+3, status_col_idx, start_row+3+len(det_df), status_col_idx,
                                              {'type': 'cell', 'criteria': '==', 'value': '"In Progress"', 'format': fmt_orange})

                    for i, col in enumerate(summ.columns): ws.set_column(i, i, 15)

                st.download_button("📥 Download One-Sheet Excel", buffer.getvalue(), "Audit_Report_Merged.xlsx", "application/vnd.ms-excel")

    # USER
    else:
        st.title("✅ My Audit Space")
        tabs = st.tabs(["Dashboard", "Active Tasks", "New Log"])
        with tabs[0]:
            mydf = tasks_df[tasks_df['Employee'] == user['Username']]
            c1,c2 = st.columns(2)
            c1.metric("Done", (mydf['Completion Status']=='Completed').sum())
            c2.metric("Pending", (mydf['Completion Status']!='Completed').sum())

        with tabs[1]:
            act = tasks_df[(tasks_df['Employee']==user['Username']) & (tasks_df['Completion Status']!='Completed')]
            if act.empty: st.success("Caught up!")
            for idx, row in act.iterrows():
                with st.expander(f"{row['Task Description']} @ {row['Branch']}"):
                    with st.form(key=f"usr_{idx}"):
                        c1,c2 = st.columns(2)
                        nt = c1.number_input("Trans", value=0); nf = c2.number_input("Finds", value=0)
                        if st.form_submit_button("✅ Done"):
                            now = get_current_time()
                            cd, ct = now.strftime('%d/%b/%Y'), now.strftime('%I:%M:%S %p')
                            dur = calculate_duration(row.get('Assigned Date'), row.get('Assigned Time'), cd, ct)
                            tasks_df.loc[idx, ['Number of Transaction','Number of Findings','Completion Status','Completion Date','Completion Time','Duration','Progress %']] = [nt, nf, 'Completed', cd, ct, dur, 1]
                            if update_data(conn, tasks_df, "Tasks"): st.balloons(); time.sleep(2); st.rerun()
        
        with tabs[2]:
            with st.form("quick_log"):
                c1,c2 = st.columns(2)
                b = c1.selectbox("Branch", BRANCH_OPTIONS); t = c2.selectbox("Task", TASK_OPTIONS); d = c1.date_input("Journal Date")
                if st.form_submit_button("Start"):
                    now = get_current_time()
                    nr = {'Employee': user['Username'], 'Task Description': t, 'Branch': b, 
                          'Assigned Date': now.strftime('%d/%b/%Y'), 'Assigned Time': now.strftime('%I:%M:%S %p'),
                          'Journal Date': d.strftime('%d/%b/%Y'), 'Completion Status': 'In Progress', 
                          'Number of Findings': 0, 'Number of Transaction': 0}
                    if update_data(conn, pd.concat([tasks_df, pd.DataFrame([nr])], ignore_index=True), "Tasks"):
                        st.success("Started"); time.sleep(2); st.rerun()

if __name__ == "__main__":
    main()
