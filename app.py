import streamlit as st
from attendance import attendance
from journal import journal
from cahiers import cahiers_menu
from settings_menu import settings_menu  # or settings_menu.py if reverted

st.set_page_config(layout="wide", page_title="PerfMan Lite")

MAIN_MENUS = [
    "Attendance",
    "Journal",
    "Cahiers",
    "Materials",
    "Devoirs",
    "Rapports",
    "Settings"
]

main = st.sidebar.radio("Menu", MAIN_MENUS)
messages = []

if main == "Attendance":
    messages = attendance() or []
elif main == "Journal":
    messages = journal() or []
elif main == "Cahiers":
    messages = cahiers_menu() or []
elif main == "Materials":
    from materials import materials_page
    messages = materials_page() or []
elif main == "Devoirs":
    from devoirs import devoirs as devoirs_page
    messages = devoirs_page() or []
elif main == "Rapports":
    from rapports import rapports as rapports_page
    messages = rapports_page() or []
elif main == "Settings":
    messages = settings_menu() or []

st.sidebar.header("Messages")
for t, msg in (messages or []):
    getattr(st.sidebar, t if t in ("success","warning","info","error") else "info")(msg)