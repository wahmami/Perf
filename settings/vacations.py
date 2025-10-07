# filepath: d:\Zad\WORK\Projects\PerfMan\settings\vacations.py
import streamlit as st
from datetime import date as _date, timedelta
from database import (
    add_calendar_override,
    delete_calendar_override,
    load_overrides_range,
)

def vacations_menu():
    messages = []
    def add_msg(level, text): messages.append((level, text))

    st.caption("Manage global vacation days and weekend working overrides.")

    today = _date.today()
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1, day=1)
    month_end = next_month - timedelta(days=1)

    # --- Single Vacation Day ---
    with st.expander("Add Single Vacation Day"):
        vac_date = st.date_input("Vacation Date", today, key="vac_single_date")
        label = st.text_input("Label (optional)", key="vac_single_label")
        if st.button("Add Vacation Day"):
            try:
                add_calendar_override("VACATION", vac_date.isoformat(), vac_date.isoformat(), label or None)
                add_msg("success", "Vacation day added.")
            except Exception as e:
                add_msg("error", f"Add failed: {e}")

    # --- Vacation Range ---
    with st.expander("Add Vacation Range"):
        c1, c2 = st.columns(2)
        with c1:
            r_start = st.date_input("Start Date", month_start, key="vac_range_start")
        with c2:
            r_end = st.date_input("End Date", month_end, key="vac_range_end")
        r_label = st.text_input("Range Label", key="vac_range_label")
        if st.button("Add Vacation Range"):
            if r_end < r_start:
                add_msg("error", "End date must be after or equal start date.")
            else:
                try:
                    add_calendar_override("VACATION", r_start.isoformat(), r_end.isoformat(), r_label or None)
                    add_msg("success", "Vacation range added.")
                except Exception as e:
                    add_msg("error", f"Add failed: {e}")

    # --- Weekend Working Override ---
    with st.expander("Add Weekend Working Override"):
        wk_date = st.date_input("Weekend Date", today, key="wk_override_date")
        wk_label = st.text_input("Override Label", key="wk_label")
        if st.button("Add Working Override"):
            if wk_date.weekday() < 5:
                add_msg("error", "Pick Saturday or Sunday.")
            else:
                try:
                    add_calendar_override("WORKING", wk_date.isoformat(), wk_date.isoformat(), wk_label or None)
                    add_msg("success", "Working override added.")
                except Exception as e:
                    add_msg("error", f"Add failed: {e}")

    # --- List Overrides ---
    st.markdown("**Overrides List**")
    list_start = st.date_input("List Start", month_start, key="ov_list_start")
    list_end = st.date_input("List End", month_end, key="ov_list_end")

    if list_end < list_start:
        add_msg("error", "End must be >= Start.")
        return messages

    rows = load_overrides_range(list_start.isoformat(), list_end.isoformat()) or []
    if not rows:
        add_msg("info", "No overrides in range.")
        return messages

    pending_key = "pending_delete_override"

    for r in rows:
        kind = r["kind"]
        sd = r["start_date"]
        ed = r["end_date"]
        label = r.get("label") or ""
        c1, c2, c3, c4, c5 = st.columns([1.2,1.8,1.8,3,0.8])
        with c1: st.write(kind)
        with c2: st.write(sd)
        with c3: st.write(ed)
        with c4: st.write(label)
        with c5:
            if st.button("✕", key=f"del_ov_{r['id']}"):
                st.session_state[pending_key] = r["id"]

    pid = st.session_state.get(pending_key)
    if pid:
        st.warning("Confirm delete this override?")
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button("Confirm Delete"):
                try:
                    delete_calendar_override(pid)
                    add_msg("success", "Override deleted.")
                except Exception as e:
                    add_msg("error", f"Delete failed: {e}")
                finally:
                    st.session_state.pop(pending_key, None)
                    st.rerun()
        with dc2:
            if st.button("Cancel Delete"):
                st.session_state.pop(pending_key, None)
                add_msg("info", "Deletion canceled.")

    return messages