import streamlit as st
import os
import db

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
    st.markdown(f"Total completed updates: **{len(completed_records)}**")
    
    # Display table structure or expanding detailed logs
    for idx, row in enumerate(completed_records):
        card_title = f"✅ PO: {row['po_number']} | GRN: {row['grn_number']} | {row['vendor_name']}"
        
        with st.expander(card_title, expanded=False):
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.markdown("### Record Details")
                st.write(f"**PO Number:** {row['po_number']}")
                st.write(f"**Vendor Name:** {row['vendor_name']}")
                st.write(f"**PO Header Text:** {row['po_header_text']}")
                st.write(f"**Article:** {row['article']}")
                st.write(f"**Article Description:** {row['article_description']}")
                st.write(f"**Quantity Updated:** {row['quantity']}")
                st.write(f"**GRN Number assigned:** `{row['grn_number']}`")
                
                # Check file path details
                if row['invoice_file_path']:
                    st.write(f"**Saved Invoice File:** `{os.path.basename(row['invoice_file_path'])}`")
                elif row.get('vendor_invoice_path'):
                    st.write(f"**Vendor Invoice:** `{os.path.basename(row['vendor_invoice_path'])}`")
                else:
                    st.write("**Saved Invoice File:** No file path recorded.")
                    
            with col_right:
                st.markdown("### Invoice Actions")
                
                # File Actions
                file_path = row['invoice_file_path'] if row['invoice_file_path'] else row.get('vendor_invoice_path')
                if file_path and os.path.exists(file_path):
                    # Download button
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                    
                    st.download_button(
                        label="📥 Download Invoice",
                        data=file_bytes,
                        file_name=os.path.basename(file_path),
                        mime="application/octet-stream",
                        key=f"download_{row['id']}_{idx}",
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
