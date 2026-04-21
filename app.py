import streamlit as st


st.set_page_config(page_title="PawPal+ Pet Care AI", page_icon="🐾", layout="wide")

planner_page = st.Page("planner.py", title="Planner", icon="🐾", url_path="", default=True)
results_page = st.Page("pages/Results.py", title="Results", icon="📋", url_path="results")
chat_page = st.Page("pages/Chat.py", title="Chat", icon="💬", url_path="chat")

navigation = st.navigation([planner_page, results_page, chat_page], position="hidden")
navigation.run()
