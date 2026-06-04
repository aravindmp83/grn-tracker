import streamlit as st
import db

# Centered layout using columns
col1, col2, col3 = st.columns([1, 1.8, 1])

with col2:
    # Styled header container
    st.markdown(
        """
        <div class="login-container">
            <div class="login-title">Trends Portal</div>
            <div class="login-subtitle">GRN & Invoice Verification System</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    with st.form("unified_login_form", clear_on_submit=False):
        user_id_input = st.text_input(
            "Username or ID (e.g. sumit, T0AH, 32612015)", 
            placeholder="Enter Username, Store Code, or Vendor Code", 
            help="Your login ID is either your Store Code, Vendor Code, or Management Username"
        )
        password_input = st.text_input(
            "Password", 
            type="password", 
            placeholder="Enter Password", 
            help="Enter your password"
        )
        
        submit_login = st.form_submit_button("Sign In")
        
        if submit_login:
            if not user_id_input.strip():
                st.error("Please enter your Username or ID.")
            elif not password_input:
                st.error("Please enter your password.")
            else:
                user_id = user_id_input.strip()
                password = password_input.strip()
                
                # Authenticate user using unified DB check
                auth_info = db.authenticate_user(user_id, password)
                
                if auth_info:
                    if isinstance(auth_info, dict) and auth_info.get("error") == "invalid_password":
                        st.error("Authentication failed: Incorrect password.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_role = auth_info['role']
                        
                        # Set role-specific session states
                        if auth_info['role'] == "store_manager":
                            st.session_state.store_code = auth_info['store_code']
                            st.toast(f"Logged in as Store Manager {auth_info['store_code']}! 🏪", icon="✅")
                        elif auth_info['role'] == "vendor":
                            st.session_state.vendor_code = auth_info['vendor_code']
                            st.toast(f"Logged in as Vendor {auth_info['vendor_code']}! 🏭", icon="✅")
                        elif auth_info['role'] == "management":
                            st.session_state.management_username = auth_info['username']
                            st.session_state.management_role = auth_info['management_role']
                            st.session_state.management_territory = auth_info['management_territory']
                            st.toast(f"Welcome back, {auth_info['name']}! 💼", icon="✅")
                            
                        st.rerun()
                else:
                    st.error("Authentication failed: Username or ID not found in system.")

    # Bottom branding/legal footer
    st.markdown(
        """
        <div style="text-align: center; color: #718096; font-size: 0.8rem; margin-top: 20px;">
            Secure connection active. For operational issues, contact helpdesk.
        </div>
        """,
        unsafe_allow_html=True
    )
