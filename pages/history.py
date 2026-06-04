import streamlit as st
import os
import db
from collections import defaultdict

# Check authorization (safety fallback)
if not st.session_state.get("logged_in", False):
    st.warning("Please log in first to access the portal history.")
    st.stop()

store_code = st.session_state.store_code

# Header Banner
st.markdown(
    f"""
    <div class="brand-banner">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #fff;">📜 Update History</h1>
        <p style="margin: 5px 0 0 0; color: #fce8e6; font-size: 1rem;">Log of completed Goods Receipt Notes (GRN) for Store <strong>{store_code}</strong></p>
    </div>
    """,
    unsafe_allow_html=True
)

# Fetch completed records
completed_records = db.get_completed_grns(store_code)

if not completed_records:
    st.info("No completed GRN updates found for your store code yet.")
    st.markdown(
        """
        <div style="text-align: center; margin-top: 50px; color: #a0aec0;">
            <p style="font-size: 1.2rem;">Head over to the <strong>Pending GRNs</strong> page to start updating receipts.</p>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    # Group by PO Number
    po_groups = defaultdict(list)
    for row in completed_records:
        po_groups[row['po_number']].append(row)
        
    st.markdown(f"Total completed POs: **{len(po_groups)}** (Total {len(completed_records)} line items)")
    
    # Display expanding detailed logs
    for po_number, items in po_groups.items():
        r = items[0] # Representative row
        
        card_title = f"✅ PO: {po_number} | GRN: {r['grn_number']} | {r['vendor_name']}"
        
        with st.expander(card_title, expanded=False):
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.markdown("### PO Details")
                st.write(f"**PO Number:** {po_number}")
                st.write(f"**Vendor Name:** {r['vendor_name']}")
                st.write(f"**PO Header Text:** {r['po_header_text']}")
                st.write(f"**GRN Number assigned:** `{r['grn_number']}`")
                
                st.markdown("#### Line Items")
                item_data = []
                for item in items:
                    item_data.append({
                        "Article": item['article'],
                        "Description": item['article_description'],
                        "Quantity Updated": item['quantity'],
                        "Value": f"₹{item['net_value']:,.2f}"
                    })
                st.table(item_data)
                
                # Check file path details
                if r['invoice_file_path']:
                    st.write(f"**Saved Invoice File:** `{os.path.basename(r['invoice_file_path'])}`")
                elif r.get('vendor_invoice_path'):
                    st.write(f"**Vendor Invoice:** `{os.path.basename(r['vendor_invoice_path'])}`")
                else:
                    st.write("**Saved Invoice File:** No file path recorded.")
                    
            with col_right:
                st.markdown("### Invoice Actions")
                
                # File Actions
                file_path = r['invoice_file_path'] if r['invoice_file_path'] else r.get('vendor_invoice_path')
                if file_path and os.path.exists(file_path):
                    # Download button
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                    
                    st.download_button(
                        label="📥 Download Invoice",
                        data=file_bytes,
                        file_name=os.path.basename(file_path),
                        mime="application/octet-stream",
                        key=f"download_po_{po_number}",
                        use_container_width=True
                    )
                    
                    # Preview inline images
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext in ['.png', '.jpg', '.jpeg']:
                        st.markdown("<br><strong>Invoice Preview:</strong>", unsafe_allow_html=True)
                        st.image(file_path, use_container_width=True)
                    elif file_ext == '.pdf':
                        st.info("📄 PDF Invoice uploaded. Click download above to review.")
                else:
                    st.warning("⚠️ Local invoice file not found on disk.")
                    
            st.markdown("<hr style='border: 0.5px solid rgba(255,255,255,0.1); margin: 5px 0;'>", unsafe_allow_html=True)
