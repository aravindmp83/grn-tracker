import streamlit as st
import os

# 1. Page Configuration (must be called first)
st.set_page_config(
    page_title="Trends GRN Portal",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject Custom CSS Stylesheet
CSS_FILE = "style.css"
if os.path.exists(CSS_FILE):
    with open(CSS_FILE, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 3. Initialize Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None  # 'store_manager', 'vendor', or 'management'
if "store_code" not in st.session_state:
    st.session_state.store_code = None
if "vendor_code" not in st.session_state:
    st.session_state.vendor_code = None
if "management_username" not in st.session_state:
    st.session_state.management_username = None
if "management_role" not in st.session_state:
    st.session_state.management_role = None
if "management_territory" not in st.session_state:
    st.session_state.management_territory = None

# 4. Handle Log Out Action and Profile Card in Sidebar
if st.session_state.logged_in:
    with st.sidebar:
        # Custom profile display by role
        if st.session_state.user_role == "store_manager":
            role_title = "Store Manager"
            role_icon = "🏪"
            user_id = st.session_state.store_code
            accent_color = "#db2777"
        elif st.session_state.user_role == "vendor":
            role_title = "Vendor Portal"
            role_icon = "🏭"
            user_id = st.session_state.vendor_code
            accent_color = "#ea580c"
        else: # management
            role_title = "Management Team"
            role_icon = "💼"
            user_id = f"{st.session_state.management_username} ({'Cluster' if st.session_state.management_role == 'cluster_manager' else 'Regional'})"
            accent_color = "#3b82f6"
            
        st.markdown(
            f"""
            <div style="background: rgba(255,255,255,0.04); padding: 16px; border-radius: 12px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08);">
                <div style="font-size: 0.75rem; color: #a0aec0; text-transform: uppercase; letter-spacing: 0.08em;">{role_title}</div>
                <div style="font-size: 1.15rem; font-weight: 700; color: {accent_color}; margin-top: 5px;">{role_icon} {user_id}</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
        if st.button("🚪 Log Out", key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.store_code = None
            st.session_state.vendor_code = None
            st.session_state.management_username = None
            st.session_state.management_role = None
            st.session_state.management_territory = None
            st.success("Logged out successfully!")
            st.rerun()

# 5. Define Pages for Routing
login_page = st.Page("pages/login.py", title="Portal Sign In", icon="🔒")
dashboard_page = st.Page("pages/dashboard.py", title="Pending GRNs", icon="📊")
history_page = st.Page("pages/history.py", title="GRN History", icon="📜")
vendor_dashboard_page = st.Page("pages/vendor_dashboard.py", title="PO Orders & Invoices", icon="📋")
vendor_password_page = st.Page("pages/vendor_password.py", title="Change Password", icon="🔑")
management_dashboard_page = st.Page("pages/management_dashboard.py", title="Territory Performance", icon="📈")

# 6. Run Navigation Logic based on Auth and Role
if st.session_state.logged_in:
    if st.session_state.user_role == "store_manager":
        # Store Manager Pages
        pg = st.navigation({
            "Store Operations": [dashboard_page, history_page],
            "Settings": [vendor_password_page]
        })
    elif st.session_state.user_role == "vendor":
        # Vendor Pages
        pg = st.navigation({
            "Vendor Operations": [vendor_dashboard_page],
            "Settings": [vendor_password_page]
        })
    elif st.session_state.user_role == "management":
        # Management Pages
        pg = st.navigation({
            "Executive Reports": [management_dashboard_page],
            "Settings": [vendor_password_page]
        })
    else:
        st.session_state.logged_in = False
        st.rerun()
else:
    # Public navigation (login only)
    pg = st.navigation([login_page])

pg.run()
