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
    
    # Tabs for different portals
    tab1, tab2, tab3 = st.tabs(["🏪 Store Manager", "🏭 Vendor Portal", "💼 Management"])
    
    # Store Manager Login Tab
    with tab1:
        with st.form("store_login_form", clear_on_submit=False):
            store_code_input = st.text_input(
                "Store Code (e.g. T0AH)", 
                placeholder="Enter Store Code", 
                help="Enter your alphanumeric Store Code"
            )
            password_input = st.text_input(
                "Password", 
                type="password", 
                placeholder="Enter Password", 
                help="Default password matches your Store Code"
            )
            
            submit_store = st.form_submit_button("Sign In as Manager")
            
            if submit_store:
                if not store_code_input.strip():
                    st.error("Please enter a Store Code.")
                elif not password_input:
                    st.error("Please enter your password.")
                else:
                    clean_store = store_code_input.strip().upper()
                    clean_password = password_input.strip()
                    
                    # Password matches Store Code exactly
                    if clean_password.upper() != clean_store:
                        st.error("Authentication failed: Password must exactly match the Store Code.")
                    else:
                        exists = db.verify_store_code(clean_store)
                        if exists:
                            st.session_state.logged_in = True
                            st.session_state.user_role = "store_manager"
                            st.session_state.store_code = clean_store
                            st.toast(f"Logged in as Store Manager {clean_store}! 🏪", icon="✅")
                            st.rerun()
                        else:
                            st.error(f"Authentication failed: Store Code '{clean_store}' not found in database.")
                            
    # Vendor Login Tab
    with tab2:
        with st.form("vendor_login_form", clear_on_submit=False):
            vendor_code_input = st.text_input(
                "Vendor Code (e.g. 32612015)", 
                placeholder="Enter Vendor Code", 
                help="Check your PO details for the vendor code"
            )
            vendor_password_input = st.text_input(
                "Password", 
                type="password", 
                placeholder="Enter Password", 
                help="Default password matches your Vendor Code"
            )
            
            submit_vendor = st.form_submit_button("Sign In as Vendor")
            
            if submit_vendor:
                if not vendor_code_input.strip():
                    st.error("Please enter a Vendor Code.")
                elif not vendor_password_input:
                    st.error("Please enter your password.")
                else:
                    clean_vendor = vendor_code_input.strip().upper()
                    clean_pwd = vendor_password_input.strip()
                    
                    # Verify vendor credentials in DB
                    valid = db.verify_vendor_login(clean_vendor, clean_pwd)
                    if valid:
                        st.session_state.logged_in = True
                        st.session_state.user_role = "vendor"
                        st.session_state.vendor_code = clean_vendor
                        st.toast(f"Logged in as Vendor {clean_vendor}! 🏭", icon="✅")
                        st.rerun()
                    else:
                        st.error("Authentication failed: Invalid Vendor Code or Password.")
                        
    # Management Login Tab
    with tab3:
        with st.form("mgmt_login_form", clear_on_submit=False):
            mgmt_user_input = st.text_input(
                "Username (e.g. cm_chennai or rm_north)",
                placeholder="Enter Username",
                help="Management username"
            )
            mgmt_pwd_input = st.text_input(
                "Password",
                type="password",
                placeholder="Enter Password",
                help="Default password matches your Username"
            )
            
            submit_mgmt = st.form_submit_button("Sign In as Executive")
            
            if submit_mgmt:
                if not mgmt_user_input.strip():
                    st.error("Please enter a Username.")
                elif not mgmt_pwd_input:
                    st.error("Please enter your password.")
                else:
                    clean_user = mgmt_user_input.strip().lower()
                    clean_pwd = mgmt_pwd_input.strip()
                    
                    # Verify management credentials in DB
                    mgmt_info = db.verify_management_login(clean_user, clean_pwd)
                    if mgmt_info:
                        st.session_state.logged_in = True
                        st.session_state.user_role = "management"
                        st.session_state.management_username = clean_user
                        st.session_state.management_role = mgmt_info['role']
                        st.session_state.management_territory = mgmt_info['territory']
                        
                        st.toast(f"Welcome back, {mgmt_info['name']}! 💼", icon="✅")
                        st.rerun()
                    else:
                        st.error("Authentication failed: Invalid Username or Password.")
                        
    # Bottom branding/legal footer
    st.markdown(
        """
        <div style="text-align: center; color: #718096; font-size: 0.8rem; margin-top: 20px;">
            Secure connection active. For operational issues, contact helpdesk.
        </div>
        """,
        unsafe_allow_html=True
    )
