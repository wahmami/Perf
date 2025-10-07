from datetime import datetime
from database import (
    get_all_teachers,
    add_rapport_delivery,
    get_rapports,
    get_rapport_deliveries
)
from config import classes
import streamlit as st
import pandas as pd

def rapport_menu():
    messages = []
    st.header("📊 Rapport (Summary & Reports)")

    # --- Record Delivery ---
    st.subheader("Record Delivery")
    rapports = get_rapports()
    if rapports:
        rapport_options = [f"{r[1]} (Due: {r[2]})" for r in rapports]
        rapport_map = {f"{r[1]} (Due: {r[2]})": r for r in rapports}
        selected_rapport_display = st.selectbox("Select Rapport for Delivery", rapport_options, key="delivery_rapport")
        selected_rapport = rapport_map[selected_rapport_display]
        rapport_id = selected_rapport[0]
        rapport_due_date = datetime.strptime(selected_rapport[2], "%Y-%m-%d").date()
        rapport_classes = selected_rapport[3].split(", ")

        teacher_names = [t[1] for t in get_all_teachers()]
        teacher = st.selectbox("Teacher", teacher_names)
        delivered_day = st.date_input("Delivered Day", datetime.today(), key="delivered_day")
        delivered_classes = st.multiselect("Delivered Classes", rapport_classes)

        days_late = (delivered_day - rapport_due_date).days if delivered_day > rapport_due_date else 0
        st.info(f"Days late: {days_late} day(s)" if days_late > 0 else "Not late.")

        if st.button("Save Delivery"):
            if not delivered_classes:
                messages.append(("warning", "Select at least one delivered class."))
            else:
                add_rapport_delivery(
                    rapport_id,
                    teacher,
                    str(delivered_day),
                    ", ".join(delivered_classes),
                    days_late
                )
                messages.append(("success", "Delivery saved."))

    else:
        st.info("No rapports found. Please create a rapport first in Settings.")

    # --- View Summary ---
    st.subheader("Rapport Deliveries Summary")
    deliveries = get_rapport_deliveries()
    if deliveries:
        df = pd.DataFrame(deliveries, columns=[
            "Rapport Title", "Due Date", "Teacher", "Delivered Day", "Delivered Classes", "Days Late"
        ])
        st.dataframe(df)
    else:
        st.info("No deliveries recorded yet.")

    return messages