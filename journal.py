# journal.py
import streamlit as st
from datetime import date, timedelta
import pandas as pd
from database import (
    load_teachers,
    upsert_journal_record,
    list_journal_range,
    delete_journal_record,
)

def _week_bounds(d: date):
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday

def journal():
    messages = []
    def msg(level, text): messages.append((level, text))

    st.header("📘 Journal Inspections")

    today = date.today()

    # --- Add / Update Form ---
    with st.expander("Add / Update Inspection", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            inspection_date = st.date_input("Inspection Date", today, key="ji_ins_date")
        with c2:
            teacher_list = load_teachers()
            teacher = st.selectbox("Teacher", teacher_list, key="ji_teacher")
        last_entry_date = st.date_input("Last Book Entry Date", today, key="ji_last_entry")

        if last_entry_date >= inspection_date:
            status_preview = "UPDATED"
            days_late = 0
        else:
            days_late = (inspection_date - last_entry_date).days
            status_preview = "OUTDATED"
        st.caption(f"Status: {status_preview} (Days Late: {days_late})")

        observations = st.text_area("Observations (optional)", key="ji_obs")

        if st.button("Save Inspection"):
            if not teacher:
                msg("error", "Teacher required.")
            else:
                try:
                    upsert_journal_record(
                        inspection_date.isoformat(),
                        teacher,
                        last_entry_date.isoformat(),
                        observations.strip() or None
                    )
                    msg("success", f"Saved inspection for {teacher} on {inspection_date}")
                except Exception as e:
                    msg("error", f"Save failed: {e}")

    # --- Week navigation ---
    if "journal_ref_date" not in st.session_state:
        st.session_state.journal_ref_date = today
    ref_date = st.session_state.journal_ref_date
    w_start, w_end = _week_bounds(ref_date)

    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns(4)
    with nav_c1:
        if st.button("◀ Previous Week"):
            st.session_state.journal_ref_date = ref_date - timedelta(days=7)
            st.rerun()
    with nav_c2:
        if st.button("Current Week"):
            st.session_state.journal_ref_date = today
            st.rerun()
    with nav_c3:
        if st.button("Next Week ▶"):
            st.session_state.journal_ref_date = ref_date + timedelta(days=7)
            st.rerun()
    with nav_c4:
        custom_ref = st.date_input("Ref Date", ref_date, key="ji_ref_date_picker")
        if custom_ref != ref_date:
            st.session_state.journal_ref_date = custom_ref
            st.rerun()

    st.subheader("This Week Records")
    st.caption(f"Week Window: {w_start} → {w_end}")

    rows = list_journal_range(w_start.isoformat(), w_end.isoformat())
    if not rows:
        msg("info", "No inspections this week.")
        return messages

    df = pd.DataFrame(rows)
    # Ensure date objects for editor
    for col in ("inspection_date", "last_entry_date"):
        df[col] = pd.to_datetime(df[col]).dt.date

    # Build display DF
    df_display = df[[
        "id","inspection_date","teacher_name","last_entry_date","status","days_late","observations"
    ]].rename(columns={
        "id": "ID",
        "inspection_date":"Inspection Date",
        "teacher_name":"Teacher",
        "last_entry_date":"Last Entry",
        "status":"Status",
        "days_late":"Days Late",
        "observations":"Observations"
    })

    # Indicator column (simulated highlight)
    def _indicator(row):
        outd = row["Status"] == "OUTDATED"
        obs = bool(str(row["Observations"] or "").strip())
        if outd and obs: return "🔴📝"
        if outd: return "🔴"
        if obs: return "🟡"
        return ""
    df_display.insert(1, "Indicator", df_display.apply(_indicator, axis=1))

    st.markdown("Edit Last Entry date or Observations; delete by ID. Indicators: 🔴 outdated, 🟡 observations, 🔴📝 both.")

    edited = st.data_editor(
        df_display,
        key=f"ji_editor_{w_start}",
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("ID", disabled=True),
            "Indicator": st.column_config.TextColumn("Indicator", help="Status / notes flags", disabled=True),
            "Inspection Date": st.column_config.DateColumn("Inspection Date", disabled=True),
            "Teacher": st.column_config.TextColumn("Teacher", disabled=True),
            "Last Entry": st.column_config.DateColumn("Last Entry"),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Days Late": st.column_config.NumberColumn("Days Late", disabled=True),
            "Observations": st.column_config.TextColumn("Observations"),
        }
    )

    # Detect edited rows
    original_map = {
        r["id"]: (r["last_entry_date"], (r.get("observations") or ""))
        for r in rows
    }
    changed = []
    for row in edited.to_dict(orient="records"):
        rid = row["ID"]
        new_last = row["Last Entry"]        # date object
        new_obs = row.get("Observations") or ""
        orig_last, orig_obs = original_map[rid]
        if new_last != orig_last or new_obs != orig_obs:
            changed.append((rid, new_last, new_obs))

    c_save, c_delete = st.columns(2)
    with c_save:
        if st.button("Save Edited Rows", disabled=not changed):
            saved = 0
            for rid, new_last, new_obs in changed:
                full = next(r for r in rows if r["id"] == rid)
                try:
                    upsert_journal_record(
                        full["inspection_date"],   # original inspection date (string)
                        full["teacher_name"],
                        new_last.isoformat(),
                        new_obs.strip() or None
                    )
                    saved += 1
                except Exception as e:
                    msg("error", f"Update failed (id={rid}): {e}")
            if saved:
                msg("success", f"Applied {saved} update(s).")
                st.rerun()

    with c_delete:
        del_id = st.number_input("Delete ID", min_value=0, step=1, key="ji_del_id")
        if st.button("Delete Record", disabled=del_id == 0):
            try:
                delete_journal_record(int(del_id))
                msg("success", f"Deleted record {del_id}")
                st.rerun()
            except Exception as e:
                msg("error", f"Delete failed: {e}")

    return messages

def journal_menu():
    return journal()