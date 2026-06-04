import streamlit as st
import os
import db
from collections import defaultdict

# Check authorization (safety fallback)
if not st.session_state.get("logged_in", False) or st.session_state.get("user_role") != "vendor":
    st.warning("Please log in as a vendor to access this portal.")
    st.stop()

vendor_code = st.session_state.vendor_code

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

# Header Banner
st.markdown(
    f"""
    <div class="brand-banner" style="background: linear-gradient(90deg, rgba(234,88,12,0.15) 0%, rgba(219,39,119,0.15) 100%); border-left-color: #ea580c;">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #fff;">🏭 Vendor Order Portal</h1>
        <p style="margin: 5px 0 0 0; color: #fce8e6; font-size: 1rem;">Order management and invoice uploading panel for Vendor <strong>{vendor_code}</strong></p>
    </div>
    """,
    unsafe_allow_html=True
)

# Fetch records
records = db.get_vendor_records(vendor_code)

# Sort records:
# 1. Primary: Ageing bucket (rank 1 to 4)
# 2. Secondary: PO number (ascending)
# 3. Tertiary: Article code (ascending)
records.sort(key=lambda r: (get_bucket_rank(r['days']), r['po_number'], r['article']))

total_records = len(records)

# Filter lists based on status (they inherit the sorted order)
requested_records = [r for r in records if r['store_invoice_status'] == 'Requested' and r['is_goods_received'] == 0]
issue_records = [r for r in records if r['goods_received_status'] in ['No', 'Partially received', 'Have complaint in the work done'] and r['is_goods_received'] == 0]
completed_records = [r for r in records if r['is_goods_received'] == 1]

# Metrics Panel
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(label="Total PO Lines", value=total_records)
    st.markdown('</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(label="Invoice Requested", value=len(requested_records), help="Outstanding invoices requested by store managers")
    st.markdown('</div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(label="Store Issues & Shortages", value=len(issue_records), help="PO lines with shortages, complaints, or rejected deliveries")
    st.markdown('</div>', unsafe_allow_html=True)
with col4:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(label="GRNed (Completed)", value=len(completed_records), help="PO lines fully received and GRNed in system")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("### 📋 Purchase Order List")

# Render Tabs
tab_all, tab_req, tab_issues, tab_completed = st.tabs([
    "📂 All Orders", 
    "🚨 Invoice Requested", 
    "⚠️ Store Issues / Shortages", 
    "✅ Completed GRN"
])

def group_records(record_list):
    po_groups = defaultdict(list)
    for row in record_list:
        po_groups[row['po_number']].append(row)
    return po_groups

def render_po_list(po_list, display_type="all"):
    po_groups = group_records(po_list)
    
    if not po_groups:
        st.info("No purchase orders found in this category.")
        return
        
    st.markdown(f"Showing **{len(po_groups)}** PO groups (Total {len(po_list)} items):")
        
    for po_number, items in po_groups.items():
        r = items[0] # Representative row
        
        # Determine status label / styling
        status_label = ""
        badge_html = ""
        
        # Ageing status flags
        max_days = max(item['days'] for item in items)
        ageing_badge = " [🚨 Danger: >60 Days]" if max_days > 60 and r['is_goods_received'] == 0 else ""
        
        # 1. Check Goods Received Status first
        gr_status = r['goods_received_status']
        if r['is_goods_received'] == 1:
            status_label = f"GRNed (GRN: {r['grn_number']})"
            badge_html = f'<span class="badge-success">✅ GRNed: {r["grn_number"]}</span>'
        elif gr_status == 'No':
            status_label = "Goods NOT Received"
            badge_html = '<span class="badge-not-received">❌ Goods NOT Received</span>'
        elif gr_status == 'Partially received':
            status_label = "Partially Received"
            badge_html = '<span class="badge-partial">⚠️ Partially Received</span>'
        elif gr_status == 'Have complaint in the work done':
            status_label = "Complaint Logged"
            badge_html = '<span class="badge-complaint">🚨 Complaint Logged</span>'
        elif r['store_invoice_status'] == 'Requested':
            status_label = "Invoice Requested"
            badge_html = '<span class="badge-requested">🚨 Action Required: Invoice Requested</span>'
        elif r['store_invoice_status'] == 'Not Received':
            status_label = "Invoice Not Received"
            badge_html = '<span class="badge-not-received">❌ Store Reported: Invoice Not Received</span>'
        else:
            status_label = "Pending Store GRN"
            badge_html = '<span class="badge-pending">⏳ Status: Pending Store GRN</span>'
            
        expander_title = (
            f"📄 PO: {po_number} | Store: {r['site']} | "
            f"Items: {len(items)}{ageing_badge} | {status_label}"
        )
        
        with st.expander(expander_title):
            # Display PO Details
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.write(f"**PO Header Details:** {r['po_header_text']}")
                st.write(f"**PO Date:** {r['po_date']}")
            with col_b:
                st.write(f"**Delivery Date:** {r['delivery_dt']}")
                st.write(f"**RMM:** {r.get('rmm', '')} | **CM:** {r.get('cm', '')}")
            with col_c:
                # Sum total value across all items
                total_val = sum(item['net_value'] for item in items)
                st.write(f"**Total Value:** ₹{total_val:,.2f}")
                st.write(f"**Max Days Ageing:** {max_days} days")
                
            st.markdown("#### Line Items")
            item_data = []
            for item in items:
                item_data.append({
                    "Article": item['article'],
                    "Description": item['article_description'],
                    "Store": item['site'],
                    "Pending Qty": item['pending_qty'],
                    "Net Value (₹)": f"{item['net_value']:,.2f}"
                })
            st.table(item_data)
                
            # Badge Status
            st.markdown(f"**Current Status:** {badge_html}", unsafe_allow_html=True)
            
            # Conversation History View
            st.markdown("##### 💬 Comment History")
            if isinstance(r['comments_log'], str) and r['comments_log'].strip():
                # Render conversation log using chat bubbles
                for line in r['comments_log'].strip().split("\\n"):
                    if ":" in line:
                        sender, text = line.split(":", 1)
                        sender = sender.strip()
                        text = text.strip()
                        
                        # Determine avatar by sender
                        if sender == r['site']:
                            avatar = "🏪"
                        elif sender == vendor_code:
                            avatar = "🏭"
                        else:
                            avatar = "💼"
                            
                        with st.chat_message(sender, avatar=avatar):
                            st.write(f"**{sender}**: {text}")
            else:
                st.info("No comment history registered yet.")
                
            # Form actions (Disabled if already GRNed)
            if r['is_goods_received'] == 1:
                st.success("✅ This PO line has been fully GRNed. No further updates can be made.")
                if r['vendor_invoice_path'] and os.path.exists(r['vendor_invoice_path']):
                    st.write(f"**Uploaded Invoice:** `{os.path.basename(r['vendor_invoice_path'])}`")
            else:
                st.markdown("<hr style='border: 0.5px solid rgba(255,255,255,0.1); margin: 15px 0;'>", unsafe_allow_html=True)
                st.markdown("##### 📝 Upload Invoice & Leave Comments")
                
                # Form inputs - Unified remarks and comments box
                vendor_remarks = st.text_area(
                    "Issue Reporting & Comments",
                    placeholder="Enter details about your invoice delivery, corrections, or quality complaints...",
                    key=f"v_rem_{po_number}",
                    height=100
                )
                
                # Check for existing upload
                existing_file = r['vendor_invoice_path']
                if existing_file and os.path.exists(existing_file):
                    st.info(f"📁 Currently uploaded invoice: `{os.path.basename(existing_file)}` (You can upload a new one to replace it)")
                    
                uploaded_file = st.file_uploader(
                    "Upload Invoice Document (PDF, PNG, JPG)",
                    type=["pdf", "png", "jpg", "jpeg"],
                    key=f"v_file_{po_number}"
                )
                
                # Submit changes
                if st.button("Save Remarks & Upload Invoice", key=f"v_submit_{po_number}", use_container_width=True):
                    try:
                        file_path = None
                        if uploaded_file:
                            # Save invoice
                            os.makedirs("invoices", exist_ok=True)
                            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                            
                            filename = f"{po_number}-{r['site']}_vendor{file_ext}"
                            file_path = os.path.join("invoices", filename)
                            
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                                
                        # Save database updates
                        success = db.update_vendor_invoice_and_comments(
                            po_number,
                            vendor=vendor_code,
                            sender=vendor_code,
                            vendor_invoice_path=file_path,
                            new_comment=vendor_remarks.strip()
                        )
                        
                        if success:
                            st.success("Successfully saved invoice and remarks!")
                            st.toast("Remarks saved successfully! 💾", icon="✅")
                            st.rerun()
                        else:
                            st.error("Failed to update database records.")
                    except Exception as e:
                        st.error(f"An error occurred: {e}")

# Render under each tab
with tab_all:
    render_po_list(records, "all")
    
with tab_req:
    render_po_list(requested_records, "requested")
    
with tab_issues:
    render_po_list(issue_records, "issues")
    
with tab_completed:
    render_po_list(completed_records, "completed")
