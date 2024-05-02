import streamlit as st

if "selected_postcard" not in st.session_state:
    st.session_state.selected_postcard = None

st.markdown("# Main page 🎈")
st.sidebar.markdown("# Main page 🎈")