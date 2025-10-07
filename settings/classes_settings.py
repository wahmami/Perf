import streamlit as st
from .config_utils import load_current, save_list

def render():
    messages = []
    st.subheader("Classes")
    cfg = load_current()
    current = list(cfg.classes)

    st.write("Current:", ", ".join(current) or "(none)")
    new_class = st.text_input("Add Class")
    if st.button("Add Class"):
        if new_class.strip() and new_class.strip() not in current:
            current.append(new_class.strip())
            save_list("classes", current)
            messages.append(("success", f"Added {new_class.strip()}"))
        else:
            messages.append(("warning", "Empty or exists."))

    edited = st.text_area("Edit (comma separated)", ", ".join(current))
    if st.button("Save Classes"):
        final = [c.strip() for c in edited.split(",") if c.strip()]
        save_list("classes", final)
        messages.append(("success", "Classes updated (restart app)."))
    return messages