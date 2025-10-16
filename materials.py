import streamlit as st
import pandas as pd
from datetime import date
from config import materials as CONFIG_MATERIALS
from database import (
    load_teachers,
    add_material_entry,
    list_material_entries_for_teacher,
    list_material_group_for_teacher,
)

def materials_page():
    messages = []
    def add_msg(level, text): messages.append((level, text))

    st.header("📚 Materials")

    day = st.date_input("Day", value=date.today(), key="mat_day")
    teacher_list = load_teachers() or []
    teacher = st.selectbox("Teacher", teacher_list, key="mat_teacher")

    mat = st.selectbox("Material taken", CONFIG_MATERIALS, key="mat_material", index=(0 if CONFIG_MATERIALS else None))

    can_save = bool(day and teacher and mat)
    if st.button("Save", key="mat_save", disabled=not can_save):
        try:
            add_material_entry(day.isoformat(), teacher, mat)
            add_msg("success", f"Saved material {mat} for {teacher} on {day}")
        except Exception as e:
            add_msg("error", f"Save failed: {e}")

    st.markdown("---")
    if not teacher:
        st.info("Select a teacher to view history.")
        return messages

    entries = list_material_entries_for_teacher(teacher)
    if entries:
        df = pd.DataFrame([
            {"Date": r["day"], "Material": r["material"]}
            for r in entries
        ])
        st.subheader("Recent materials")
        st.dataframe(df, width="stretch", height=min(600, 38 + 35 * max(1, len(df))))
