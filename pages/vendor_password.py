import streamlit as st
import db

# Check authorization (safety fallback)
if not st.session_state.get("logged_in", False) or st.session_state.get("user_role") != "vendor":
    st.warning("Please log in as a vendor to access this page.")
    st.stop()

vendor_code = st.session_state.vendor_code

# Header
st.markdown(
    f"""
    <div class="brand-banner" style="background: linear-gradient(90deg, rgba(234,88,12,0.15) 0%, rgba(219,39,119,0.15) 100%); border-left-color: #ea580c;">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #fff;">🔑 Change Password</h1>
        <p style="margin: 5px 0 0 0; color: #fce8e6; font-size: 1rem;">Update login password for Vendor <strong>{vendor_code}</strong></p>
    </div>
    """,
    unsafe_allow_html=True
)

# Centered layout using columns
col1, col2, col3 = st.columns([1, 1.5, 1])

with col2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("#### Reset Credentials Form")
    
    with st.form("change_pwd_form", clear_on_submit=True):
        current_pwd = st.text_input("Current Password", type="password", placeholder="Enter your current password")
        new_pwd = st.text_input("New Password", type="password", placeholder="Enter new password", help="Keep this secure")
        confirm_pwd = st.text_input("Confirm New Password", type="password", placeholder="Retype new password")
        
        submit_btn = st.form_submit_button("Update Password")
        
        if submit_btn:
            if not current_pwd:
                st.error("Please enter your current password.")
            elif not new_pwd:
                st.error("Please enter a new password.")
            elif new_pwd != confirm_pwd:
                st.error("Validation error: New Password and Confirm Password fields do not match.")
            elif len(new_pwd.strip()) < 4:
                st.error("Validation error: Password must be at least 4 characters long.")
            else:
                # 1. Verify that current password is correct
                valid = db.verify_vendor_login(vendor_code, current_pwd)
                if not valid:
                    st.error("Authentication failed: Current password is incorrect.")
                else:
                    # 2. Update password in database
                    success = db.update_vendor_password(vendor_code, new_pwd.strip())
                    if success:
                        st.success("🎉 Password updated successfully! Keep your new credentials safe.")
                        st.toast("Credentials updated! 💾", icon="✅")
                    else:
                        st.error("Failed to update password in database. Please try again.")
                        
    st.markdown('</div>', unsafe_allow_html=True)
