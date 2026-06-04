import streamlit as st
import pandas as pd
import db

# Check authorization (safety fallback)
if not st.session_state.get("logged_in", False) or st.session_state.get("user_role") != "management":
    st.warning("Please log in as an executive to access this dashboard.")
    st.stop()

username = st.session_state.management_username
role = st.session_state.management_role
territory = st.session_state.management_territory

# Helper function to classify and rank POs by ageing buckets
def get_bucket_rank(days):
    if days > 90:
        return 1  # More than 90 days (highest risk)
    elif days >= 60:
        return 2  # 60 - 90 days
    elif days >= 30:
        return 3  # 30 - 60 days
    else:
        return 4  # Below 30 days

# Set proper header labels
if role == "cluster_manager":
    role_label = "Cluster Manager"
elif role == "regional_manager":
    role_label = "Regional Manager"
else:
    role_label = "MIS Executive"

banner_color = "#3b82f6"  # Blue accent for management

st.markdown(
    f"""
    <div class="brand-banner" style="background: linear-gradient(90deg, rgba(59,130,246,0.15) 0%, rgba(219,39,119,0.15) 100%); border-left-color: {banner_color};">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #fff;">💼 Executive Performance Portal</h1>
        <p style="margin: 5px 0 0 0; color: #fce8e6; font-size: 1rem;">Territory tracking for {role_label}: <strong>{territory}</strong></p>
    </div>
    """,
    unsafe_allow_html=True
)

# MIS Executive Upload Panel
if role == "mis_executive":
    st.markdown("### 📤 HO Pendency Excel/CSV Upload")
    st.info("As the MIS Executive, you can upload the latest weekly or ad-hoc GRN pendency spreadsheet to update the system. The upload will automatically update ageing details, add new POs, and close those that are completed at HO.")
    
    uploaded_file = st.file_uploader(
        "Upload latest HO GRN Pendency File", 
        type=["xlsx", "csv"], 
        key="mis_upload_file"
    )
    
    if uploaded_file is not None:
        if st.button("🚀 Process & Synchronize Database", use_container_width=True):
            try:
                # Load file into DataFrame
                if uploaded_file.name.endswith(".csv"):
                    df_up = pd.read_csv(uploaded_file)
                else:
                    xl = pd.ExcelFile(uploaded_file)
                    sheet_to_read = 'GRN' if 'GRN' in xl.sheet_names else xl.sheet_names[0]
                    df_up = xl.parse(sheet_to_read)
                
                with st.spinner("Processing spreadsheet and syncing database..."):
                    ins, upd, auto_c = db.sync_ho_pendency_data(df_up)
                    
                st.success(f"🎉 Database Sync Completed successfully!")
                st.markdown(
                    f"""
                    <div style='background: rgba(16,185,129,0.1); padding: 15px; border-radius: 8px; border: 1px solid rgba(16,185,129,0.3); margin-top: 10px;'>
                        <ul style='margin: 0; padding-left: 20px; color: #d1fae5;'>
                            <li><strong>New PO Lines Inserted:</strong> {ins}</li>
                            <li><strong>Existing Pending POs Updated:</strong> {upd}</li>
                            <li><strong>HO Closed/Cleared POs (Auto-completed):</strong> {auto_c}</li>
                        </ul>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.toast("Database updated successfully! 💾", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Error processing upload: {e}")

# Fetch pending records for manager's territory
records = db.get_management_pending_records(role, territory)
total_pending = len(records)

# Metrics calculation
total_value = sum(r['pending_value'] for r in records)
danger_grns_count = len([r for r in records if r['days'] > 60])

# 1. Metric Cards Row
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(label="Pending GRNs in Territory", value=total_pending)
    st.markdown('</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(label="Total Pending Value", value=f"₹{total_value:,.2f}")
    st.markdown('</div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    danger_label = "🚨 Danger GRNs (>60d)" if danger_grns_count > 0 else "Danger GRNs (>60d)"
    st.metric(
        label=danger_label, 
        value=danger_grns_count,
        help="Count of pending GRN records that are over 60 days old and require immediate intervention"
    )
    st.markdown('</div>', unsafe_allow_html=True)

if total_pending == 0:
    st.success("🎉 Excellent! There are no pending GRNs in your territory.")
else:
    # Convert records list to Pandas DataFrame for calculations
    df = pd.DataFrame(records)
    
    # Sort DataFrame: 
    # 1. Primary: Ageing bucket rank (1 = >90 days, 4 = <30 days)
    # 2. Secondary: Days (descending, oldest first within bucket)
    # 3. Tertiary: Site store code (ascending)
    # 4. Quaternary: PO number (ascending)
    df['bucket_rank'] = df['days'].apply(get_bucket_rank)
    df = df.sort_values(
        by=['bucket_rank', 'days', 'site', 'po_number'], 
        ascending=[True, False, True, True]
    ).reset_index(drop=True)
    
    # 2. Breakdowns Row
    st.markdown("### 📊 Territory Breakdowns")
    breakdown_col1, breakdown_col2 = st.columns(2)
    
    with breakdown_col1:
        st.markdown('<div class="glass-card" style="min-height: 250px;">', unsafe_allow_html=True)
        st.markdown("##### 🏪 Pending GRNs by Store")
        
        # Group by Site
        store_group = df.groupby(['site', 'site_name']).size().reset_index(name='count').sort_values(by='count', ascending=False)
        store_group.columns = ['Store Code', 'Store Name', 'Pending Lines']
        
        # Display as styled table
        st.dataframe(store_group, hide_index=True, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with breakdown_col2:
        st.markdown('<div class="glass-card" style="min-height: 250px;">', unsafe_allow_html=True)
        st.markdown("##### 📈 Pending GRNs by Receipt Status")
        
        # Group by goods status
        status_group = df.groupby('goods_received_status').size().reset_index(name='count').sort_values(by='count', ascending=False)
        status_group.columns = ['Receipt Status', 'Pending Lines']
        
        st.dataframe(status_group, hide_index=True, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # 3. Interactive Detail List
    st.markdown("### 🔍 Territory Pending Details")
    
    # Site Filters
    unique_sites = sorted(list(df['site'].unique()))
    selected_site = st.selectbox("Filter by Store Code", options=["All Stores"] + unique_sites)
    
    # Filter by receipt status
    unique_statuses = sorted(list(df['goods_received_status'].unique()))
    selected_status = st.selectbox("Filter by Receipt Status", options=["All Statuses"] + unique_statuses)
    
    # Apply filters (Note: sorting is already preserved from df)
    filtered_df = df
    if selected_site != "All Stores":
        filtered_df = filtered_df[filtered_df['site'] == selected_site]
    if selected_status != "All Statuses":
        filtered_df = filtered_df[filtered_df['goods_received_status'] == selected_status]
        
    st.markdown(f"Showing **{len(filtered_df)}** records matching filter criteria:")
    
    # Loop and display PO details
    for idx, r in filtered_df.iterrows():
        # Status labels mapping
        status_label = r['goods_received_status']
        badge_html = ""
        
        # Ageing status flags
        ageing_badge = " [🚨 Danger: >60 Days]" if r['days'] > 60 else ""
        
        if status_label == 'No':
            badge_html = '<span class="badge-not-received">❌ Goods NOT Received</span>'
        elif status_label == 'Partially received':
            badge_html = '<span class="badge-partial">⚠️ Partially Received</span>'
        elif status_label == 'Have complaint in the work done':
            badge_html = '<span class="badge-complaint">🚨 Complaint Logged</span>'
        else:
            badge_html = f'<span class="badge-pending">⏳ Status: {status_label}</span>'
            
        expander_title = (
            f"🏪 Store: {r['site']} | PO: {r['po_number']} | "
            f"Article: {r['article']} (Qty: {r['quantity']}){ageing_badge} | {status_label}"
        )
        
        with st.expander(expander_title):
            # Record details
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.write(f"**Store Name:** {r['site_name']}")
                st.write(f"**PO Header Details:** {r['po_header_text']}")
                st.write(f"**PO Date:** {r['po_date']}")
            with col_b:
                st.write(f"**Vendor Name:** {r['vendor_name']} (Code: {r['vendor']})")
                st.write(f"**Article Description:** {r['article_description']}")
                st.write(f"**Delivery Date:** {r['delivery_dt']}")
                st.write(f"**RMM:** {r.get('rmm', '')} | **CM:** {r.get('cm', '')}")
            with col_c:
                st.write(f"**Net PO Value:** ₹{r['net_value']:,.2f}")
                st.write(f"**Pending Value:** ₹{r['pending_value']:,.2f}")
                st.write(f"**Days Ageing:** {r['days']} days ({r['ageing']})")
                
            # Badge Status
            st.markdown(f"**Goods Receipt Status:** {badge_html}", unsafe_allow_html=True)
            
            # Conversation History View
            st.markdown("##### 💬 Comment History")
            if isinstance(r['comments_log'], str) and r['comments_log'].strip():
                for line in r['comments_log'].strip().split("\n"):
                    if ":" in line:
                        sender, text = line.split(":", 1)
                        sender = sender.strip()
                        text = text.strip()
                        
                        if sender == r['site']:
                            avatar = "🏪"
                        elif sender == r['vendor']:
                            avatar = "🏭"
                        else:
                            avatar = "💼"
                            
                        with st.chat_message(sender, avatar=avatar):
                            st.write(f"**{sender}**: {text}")
            else:
                st.info("No comment history registered yet.")
                
            st.markdown("<hr style='border: 0.5px solid rgba(255,255,255,0.1); margin: 5px 0;'>", unsafe_allow_html=True)
