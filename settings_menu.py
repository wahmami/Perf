from settings.config_editor import render as config_render
import streamlit as st

def settings_menu():
    st.header("⚙️ Settings")
    return config_render() or []