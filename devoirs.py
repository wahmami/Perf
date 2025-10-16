import streamlit as st
import pandas as pd
from datetime import date, timedelta
from database import (
    load_teachers,
    get_assigned_classes_for_teacher,
    upsert_devoir_week,
    list_devoirs_for_week,
)

def _week_thursday(d: date) -> date:
    monday = d - timedelta(days=d.weekday())
    return monday + timedelta(days=3)

def devoirs():
    messages = []
    def add_msg(level, text): messages.append((level, text))

    st.header("📘 Devoirs (Weekly Homework)")

    ref = st.date_input("Reference date", value=date.today(), key="dev_ref_date")
    thursday = _week_thursday(ref)
    st.caption(f"This week's Thursday: {thursday}")

    teacher_names = load_teachers() or []
    teacher = st.selectbox("Teacher", teacher_names, key="dev_teacher")

    classes = get_assigned_classes_for_teacher(teacher) if teacher else []
    if not classes:
        st.warning("No assigned classes found for this teacher (assigned_classes).")
        st.info("Update the 'assigned_classes' column for this teacher in the teachers table.")
        # Render disabled inputs to keep layout stable
        st.selectbox("Class", [], key="dev_class")
        posted = st.checkbox("Posted?", value=True, key="dev_posted_toggle")
        _ = st.date_input("Posted on", value=ref, key="dev_posted_on") if posted else None
        st.text_area("Observations (optional)", key="dev_obs")
        return messages

    class_name = st.selectbox("Class", classes, key="dev_class", index=0)

    posted = st.checkbox("Posted?", value=True, key="dev_posted_toggle")
    posted_on = st.date_input("Posted on", value=ref, key="dev_posted_on") if posted else None
    observations = st.text_area("Observations (optional)", key="dev_obs")

    can_save = bool(teacher and class_name)
    if st.button("Save", key="dev_save", disabled=not can_save):
        upsert_devoir_week(
            teacher,
            class_name,
            thursday.isoformat(),
            posted_on.isoformat() if posted and posted_on else None,
            observations.strip() or None
        )
        add_msg("success", f"Saved {teacher} / {class_name} for week {thursday}.")

    st.markdown("---")

    st.subheader("Review week")
    review_thu = _week_thursday(st.date_input("Week (any day)", value=ref, key="dev_review_ref"))
    rows = list_devoirs_for_week(review_thu.isoformat()) or []

    by_key = {(r["teacher_name"], r["class_name"]): r for r in rows}
    display = []
    for c in classes:
        r = by_key.get((teacher, c))
        display.append({
            "Teacher": teacher,
            "Class": c,
            "Posted": r.get("posted_at","") if r else "",
            "Status": r.get("status","NOT_POSTED") if r else "NOT_POSTED",
            "Days Late": r.get("days_late","") if r else "",
            "Observations": r.get("observations","") if r else "",
        })
    df = pd.DataFrame(display).sort_values(["Class"])
    st.dataframe(df, width='stretch')

    return messages
