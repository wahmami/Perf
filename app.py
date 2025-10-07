import streamlit as st
from attendance_menu import attendance_menu
from journal_menu import journal_menu
from cahiers_menu import cahiers_menu
from rapports_menu import rapports_menu
from settings_menu import settings_menu

st.set_page_config(layout="wide", page_title="PerfMan Lite")

MAIN_MENUS = [
    "Attendance",
    "Journal",
    "Cahiers",
    "Rapports",
    "Settings"
]

main = st.sidebar.radio("Menu", MAIN_MENUS)
messages = []

if main == "Attendance":
    messages = attendance_menu()
elif main == "Journal":
    messages = journal_menu()
elif main == "Cahiers":
    messages = cahiers_menu()
elif main == "Rapports":
    messages = rapports_menu()
elif main == "Settings":
    messages = settings_menu()

st.sidebar.header("Messages")
for t, msg in messages:
    getattr(st.sidebar, t if t in ("success","warning","info","error") else "info")(msg)