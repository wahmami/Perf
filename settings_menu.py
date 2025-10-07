import streamlit as st
from settings.config_editor import render as config_render

def settings_menu():
    st.header("⚙️ Settings")
    # Only Config now; it will internally show Teachers
    return config_render()