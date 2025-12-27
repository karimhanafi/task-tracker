import streamlit as st
import pandas as pd

# --- 1. ADMIN AUTHENTICATION (SIDEBAR) ---
st.sidebar.header("Admin Access")
admin_password = st.sidebar.text_input("Enter Admin Password", type="password")

# Replace "1234" with whatever password you want
if admin_password == "1234":
    st.sidebar.success("Admin Mode: ON")
    
    # Check if data is loaded (assuming you loaded it into 'df' earlier)
    if 'df' in locals() and not df.empty:
        
        st.divider()
        st.header("🕵️ Admin Drill-Down Analysis")

        # --- 2. DATA PREPARATION (Fixing Dates) ---
        # We need to tell Python that "26/Dec/2025" is a date, not just text
        try:
            # Convert 'Journal Date' to datetime objects
            df['Journal Date'] = pd.to_datetime(df['Journal Date'], format='%d/%b/%Y', errors='coerce')
        except Exception as e:
            st.warning("Could not automatically fix date formats. Check your CSV.")

        # --- 3. FILTER BY DATE ---
        # Get unique dates from your data for the dropdown, or use a date picker
        available_dates = df['Journal Date'].dt.date.unique()
        selected_date = st.selectbox("Select Journal Date to Analyze:", sorted(available_dates))

        # Filter the main list to only show this date
        day_data = df[df['Journal Date'].dt.date == selected_date]

        # --- 4. HIGH-LEVEL SUMMARY (The "View from Above") ---
        st.subheader(f"Summary for {selected_date}")
        
        # Group by Branch to see totals
        summary_table = day_data.groupby('Branch')[['Number of Transaction']].sum().reset_index()
        
        # Display summary with metrics
        col1, col2 = st.columns(2)
        col1.metric("Total Transactions", day_data['Number of Transaction'].sum())
        col1.metric("Active Employees", day_data['Employee'].nunique())
        
        # Show the Branch Summary Table
        st.write("Performance by Branch:")
        st.dataframe(summary_table, hide_index=True)

        # --- 5. DRILL-DOWN (The "Magnifying Glass") ---
        st.subheader("🔍 Drill-Down Details")
        
        # Select a specific branch to inspect
        target_branch = st.selectbox("Select a Branch to inspect details:", day_data['Branch'].unique())
        
        # Filter again for that specific branch
        detailed_view = day_data[day_data['Branch'] == target_branch]
        
        # Show the specific rows
        st.write(f"Detailed tasks for **{target_branch}** on {selected_date}:")
        st.dataframe(detailed_view[['Employee', 'Task Description', 'Completion Status', 'TimeDuration']])

    else:
        st.info("Please upload a file above to activate Admin Tools.")

else:
    # If not admin, just show a message or nothing
    if admin_password:
        st.sidebar.error("Wrong Password")
