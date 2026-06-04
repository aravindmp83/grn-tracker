import streamlit as st
import os
import db
from collections import defaultdict
import pandas as pd

# Check authorization (safety fallback)
if not st.session_state.get("logged_in", False):
    st.warning("Please log in first to access the dashboard.")
    st.stop()

store_code = st.session_state.store_code

# Header / Branding Banner
st.markdown(
    f"""
    <div class="brand-banner">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #fff;">🏪 Store Dashboard</h1>
        <p style="margin: 5px 0 0 0; color: #fce8e6; font-size: 1rem;">GRN tracking and verification panel for Store Site <strong>{store_code}</strong></p>
    </div>
    """,
    unsafe_allow_html=True
)

# Fetch data
pending_records = db.get_pending_grns(store_code)
total_pending = len(pending_records)

# 1. High-Level Metrics
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(
        label="Pending GRN Line Items", 
        value=total_pending, 
        help="Count of PO lines where Goods Receipt has not been updated yet (is_goods_received == 0)"
    )
    st.markdown('</div>', unsafe_allow_html=True)

# Calculate total pending value
total_pending_value = sum(row['pending_value'] for row in pending_records)
with col2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.metric(
        label="Pending Value", 
        value=f"₹{total_pending_value:,.2f}", 
        help="Sum of pending values across all pending records"
    )
    st.markdown('</div>', unsafe_allow_html=True)

# Calculate danger GRNs (>60 days ageing)
danger_grns_count = len([row for row in pending_records if row['days'] > 60])
with col3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    danger_label = "🚨 Danger GRNs (>60d)" if danger_grns_count > 0 else "Danger GRNs (>60d)"
    st.metric(
        label=danger_label, 
        value=danger_grns_count, 
        help="Count of pending GRN records that are over 60 days old and require immediate action"
    )
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("## 🔍 Actionable Pending GRN Records")

# 2. Search and Filter Panel
search_query = st.text_input(
    "Search records", 
    placeholder="Type PO Number, Vendor Name, PO Header text, or Article...",
    label_visibility="collapsed"
)

# Filter records based on search query
filtered_records = []
if search_query:
    q = search_query.lower().strip()
    for row in pending_records:
        if (q in str(row['po_number']).lower() or
            q in str(row['vendor_name']).lower() or
            q in str(row['po_header_text']).lower() or
            q in str(row['article']).lower() or
            q in str(row['article_description']).lower()):
            filtered_records.append(row)
else:
    filtered_records = pending_records

# Group records by PO number
po_groups = defaultdict(list)
for row in filtered_records:
    po_groups[row['po_number']].append(row)

# Display list of pending records
if not po_groups:
    if total_pending == 0:
        st.success("🎉 Outstanding! No pending GRN records found for your store.")
    else:
        st.info("No matching records found for your search query.")
else:
    st.markdown(f"Showing **{len(po_groups)}** PO groups (Total {len(filtered_records)} line items):")
    
    # Render interactive list of cards/expanders
    for po_number, items in po_groups.items():
        row = items[0] # Representative row for header and status
        
        # Construct status displays for expander headers
        status_badges = []
        
        # Ageing threat highlights
        max_days = max(item['days'] for item in items)
        if max_days > 60:
            status_badges.append("[🚨 Danger: >60 Days]")
        
        # 4-option receipt status display
        gr_status = row['goods_received_status']
        if gr_status == 'No':
            status_badges.append("[❌ Goods NOT Received]")
        elif gr_status == 'Partially received':
            status_badges.append("[⚠️ Partially Received]")
        elif gr_status == 'Have complaint in the work done':
            status_badges.append("[🚨 Complaint Logged]")
            
        # Invoice status display
        if row['store_invoice_status'] == 'Requested':
            status_badges.append("[⚠️ Invoice Requested]")
        elif row['store_invoice_status'] == 'Not Received':
            status_badges.append("[❌ Invoice Not Received]")
            
        status_badges_str = " " + " ".join(status_badges) if status_badges else ""
            
        expander_title = (
            f"📄 PO: {po_number} | {row['vendor_name']} | "
            f"{len(items)} Item(s){status_badges_str}"
        )
        
        with st.expander(expander_title, expanded=False):
            # Display row details inside the expander
            st.markdown("### PO Details")
            
            d_col1, d_col2, d_col3 = st.columns(3)
            with d_col1:
                st.write(f"**PO Header text:** {row['po_header_text']}")
                st.write(f"**PO Date:** {row['po_date']}")
            with d_col2:
                st.write(f"**Vendor Name:** {row['vendor_name']}")
                st.write(f"**Max Ageing:** {max_days} days")
            with d_col3:
                st.write(f"**RMM:** {row.get('rmm', '')} | **CM:** {row.get('cm', '')}")
                
            st.markdown("#### Line Items")
            
            # Show items in a table
            item_data = []
            total_net_value = 0
            for item in items:
                item_data.append({
                    "Article": item['article'],
                    "Description": item['article_description'],
                    "HSN/SAC": item['hsn_sac_code'],
                    "Delivery Date": item['delivery_dt'],
                    "Pending Qty": item['pending_qty'],
                    "Net Value (₹)": f"{item['net_value']:,.2f}"
                })
                total_net_value += item['net_value']
                
            st.table(item_data)
            st.write(f"**Total Net Value:** ₹{total_net_value:,.2f}")
                
            # Conversation History View
            st.markdown("##### 💬 Comment History")
            if isinstance(row['comments_log'], str) and row['comments_log'].strip():
                # Render conversation log using chat bubbles
                for line in row['comments_log'].strip().split("\\n"):
                    if ":" in line:
                        sender, text = line.split(":", 1)
                        sender = sender.strip()
                        text = text.strip()
                        
                        # Determine avatar by sender
                        if sender == store_code:
                            avatar = "🏪"
                        elif sender == row['vendor']:
                            avatar = "🏭"
                        else:
                            avatar = "💼"
                            
                        with st.chat_message(sender, avatar=avatar):
                            st.write(f"**{sender}**: {text}")
            else:
                st.info("No comment history registered yet.")
            
            st.markdown("<hr style='border: 0.5px solid rgba(255,255,255,0.1); margin: 15px 0;'>", unsafe_allow_html=True)
            st.markdown("### ✏️ Update Status Form")
            
            # Goods receipt 4 options selection
            receipt_options = ["Yes", "No", "Partially received", "Have complaint in the work done"]
            current_gr_status = row['goods_received_status']
            default_gr_idx = receipt_options.index(current_gr_status) if current_gr_status in receipt_options else 0
            
            goods_received = st.radio(
                "Are goods received for this PO?",
                options=receipt_options,
                index=default_gr_idx,
                key=f"goods_rec_{po_number}"
            )
            
            # Flow for NON-YES options: No, Partially received, Have complaint
            if goods_received != "Yes":
                st.markdown("<br><strong>Issue Reporting & Comments</strong>", unsafe_allow_html=True)
                
                # Combined Issue Details & Comments (unified box)
                issue_remarks = st.text_area(
                    "Enter issue details and comments for the vendor",
                    placeholder="Shortage details, complaints description, or work incomplete details. Mandatory for Partially received and Complaints.",
                    key=f"store_issue_rem_{po_number}",
                    height=100
                )
                
                if st.button("Save Issue Status & Comments", key=f"save_issue_{po_number}", use_container_width=True):
                    # Validation: Issue details mandatory for Partial and Complaints
                    if goods_received in ["Partially received", "Have complaint in the work done"] and not issue_remarks.strip():
                        st.error(f"Please fill out the Issue Reporting & Comments describing the discrepancy for '{goods_received}'.")
                    else:
                        # Write to database (resets is_goods_received to 0, appends comment prefixed with status)
                        success = db.update_store_goods_received_issue(
                            po_number, 
                            store_code,
                            goods_received, 
                            store_code,
                            issue_remarks.strip()
                        )
                        if success:
                            st.success(f"Status updated to '{goods_received}' and comments appended!")
                            st.toast("Discrepancy logged! 📡", icon="✅")
                            st.rerun()
                        else:
                            st.error("Failed to save discrepancy status details.")
                            
            # Flow for YES option
            elif goods_received == "Yes":
                invoice_received = st.radio(
                    "Is the invoice received?",
                    options=["No", "Yes"],
                    index=0 if row['store_invoice_status'] != 'Received' else 1,
                    key=f"inv_rec_{po_number}",
                    horizontal=True
                )
                
                # Cascading Logic: Invoice Received is NO
                if invoice_received == "No":
                    st.markdown("<br><strong>Issue Reporting & Comments</strong>", unsafe_allow_html=True)
                    
                    # Single box for Comments/Remarks
                    store_remarks = st.text_area(
                        "Enter remarks or correction instructions for the vendor",
                        placeholder="State why the invoice is not received, or what corrections are required...",
                        key=f"store_rem_{po_number}",
                        height=100
                    )
                    
                    # Check if vendor uploaded an invoice
                    vendor_inv = row['vendor_invoice_path']
                    if vendor_inv and os.path.exists(vendor_inv):
                        st.success("💾 An invoice file has been uploaded by the vendor.")
                        with open(vendor_inv, "rb") as f:
                            file_bytes = f.read()
                        
                        file_ext = os.path.splitext(vendor_inv)[1].lower()
                        download_name = f"{po_number}-{store_code}{file_ext}"
                        
                        st.download_button(
                            label="📥 Download Invoice",
                            data=file_bytes,
                            file_name=download_name,
                            mime="application/octet-stream",
                            key=f"dl_vendor_{po_number}",
                            help=f"Downloads invoice uploaded by vendor as '{download_name}'"
                        )
                    else:
                        st.warning("⚠️ No invoice has been uploaded by the vendor yet.")
                    
                    invoice_status_option = st.selectbox(
                        "Report Invoice Status to Vendor Portal",
                        options=["Not Received", "Requested"],
                        index=0 if row['store_invoice_status'] == 'Not Received' else 1,
                        key=f"status_opt_{po_number}"
                    )
                    
                    if st.button("Save Remarks & Report Status", key=f"save_status_{po_number}", use_container_width=True):
                        # Save remarks and report status
                        success = db.update_store_invoice_status(
                            po_number, 
                            store_code,
                            invoice_status_option, 
                            store_code,
                            store_remarks.strip()
                        )
                        if success:
                            st.success(f"Invoice reported as '{invoice_status_option}'!")
                            st.toast("Status sent to vendor portal! 📡", icon="✅")
                            st.rerun()
                        else:
                            st.error("Failed to update status details.")
                            
                # Cascading Logic: Invoice Received is YES
                elif invoice_received == "Yes":
                    grn_number = st.text_input(
                        "Enter GRN Number",
                        placeholder="e.g. GRN12345678",
                        key=f"grn_num_{po_number}"
                    )
                    
                    store_remarks = st.text_area(
                        "Enter final comments/remarks (optional)",
                        placeholder="Add any final store-level remarks...",
                        key=f"store_rem_yes_inv_{po_number}",
                        height=100
                    )
                    
                    # Once GRN Number is provided -> show Save button
                    if grn_number.strip():
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        if st.button("Submit GRN Update", key=f"submit_{po_number}", use_container_width=True):
                            try:
                                # Update Database record (is_goods_received = 1, invoice path is None)
                                success = db.update_grn_record(
                                    po_number,
                                    store_code,
                                    grn_number.strip(), 
                                    None, 
                                    store_code,
                                    store_remarks.strip() if store_remarks.strip() else None
                                )
                                
                                if success:
                                    st.success(f"Successfully completed GRN for PO {po_number}!")
                                    st.toast("GRN status updated successfully! 💾", icon="✅")
                                    st.rerun()
                                else:
                                    st.error("Failed to update database record.")
                            except Exception as e:
                                st.error(f"An error occurred: {e}")
