import streamlit as st
import db

# Check authorization (safety fallback)
if not st.session_state.get("logged_in", False):
    st.warning("Please log in first to access this page.")
    st.stop()

# Determine user identifier based on role
role = st.session_state.user_role
if role == "store_manager":
    user_id = st.session_state.store_code
    role_label = "Store Manager"
    accent_color = "#db2777"
elif role == "vendor":
    user_id = st.session_state.vendor_code
    role_label = "Vendor"
    accent_color = "#ea580c"
else:
    user_id = st.session_state.management_username
    role_label = "Management"
    accent_color = "#3b82f6"

# Header
st.markdown(
    f"""
    <div class="brand-banner" style="background: linear-gradient(90deg, rgba(234,88,12,0.15) 0%, rgba(219,39,119,0.15) 100%); border-left-color: {accent_color};">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #fff;">🔑 Change Password</h1>
        <p style="margin: 5px 0 0 0; color: #fce8e6; font-size: 1rem;">Update login password for {role_label}: <strong>{user_id}</strong></p>
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
        new_pwd = st.text_input("New Password", type="password", placeholder="Enter new password", help="Password must be at least 4 characters long")
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
                current_p = current_pwd.strip()
                new_p = new_pwd.strip()
                
                # 1. Verify current credentials using unified helper
                auth_info = db.authenticate_user(user_id, current_p)
                
                if auth_info and not (isinstance(auth_info, dict) and auth_info.get("error") == "invalid_password"):
                    # 2. Update password based on role
                    success = False
                    if role == "management":
                        success = db.update_management_password(user_id, new_p)
                    elif role == "vendor":
                        success = db.update_vendor_password(user_id, new_p)
                    elif role == "store_manager":
                        success = db.update_store_password(user_id, new_p)
                        
                    if success:
                        st.success("🎉 Password updated successfully! Keep your new credentials safe.")
                        st.toast("Credentials updated! 💾", icon="✅")
                    else:
                        st.error("Failed to update password in database. Please try again.")
                else:
                    st.error("Authentication failed: Current password is incorrect.")
                        
    st.markdown('</div>', unsafe_allow_html=True)
