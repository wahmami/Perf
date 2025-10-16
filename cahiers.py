from datetime import date, datetime, timedelta
import streamlit as st
import pandas as pd

from config import classes, modules, submodules  # assuming lists/dicts
from database import load_teachers, upsert_cahier_entry, list_cahier_range, delete_cahier_entry, get_assigned_classes_for_teacher

def _collect_known_tokens(val, known: set[str]) -> list[str]:
    """Return tokens from val that are in known (handles str/list/tuple recursively)."""
    out = []
    if isinstance(val, str):
        parts = [p.strip() for p in val.replace(";", ",").split(",")]
        out.extend([p for p in parts if p in known])
    elif isinstance(val, (list, tuple)):
        for x in val:
            out.extend(_collect_known_tokens(x, known))
    return out

def _week_bounds(d: date):
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday

def _select_teacher_and_class():
    messages = []
    teacher_names = load_teachers() or []
    teacher = st.selectbox("Teacher", teacher_names, key="cah_teacher")

    classes = get_assigned_classes_for_teacher(teacher) if teacher else []
    if not classes:
        st.warning("No assigned classes found for this teacher (assigned_classes).")
        st.info("Update the 'assigned_classes' column for this teacher in the teachers table.")
        st.selectbox("Class", [], key="cah_class")
        return None, None, messages

    class_name = st.selectbox("Class", classes, key="cah_class", index=0)
    return teacher, class_name, messages

def cahiers_menu():
    messages = []
    def add_msg(level, text): messages.append((level, text))

    st.header("📒 Cahiers (Lesson Book Checks)")

    today = date.today()

    # --- Add / Update Entry ---
    with st.expander("Add / Update Entry", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            inspection_date = st.date_input("Inspection Date", today, key="cah_ins_date")

        # Teacher select (show only name, keep full row)
        teachers = load_teachers() or []
        def _tname(t):
            if isinstance(t, dict): return t.get("name", "")
            if isinstance(t, (list, tuple)): return t[1] if len(t) > 1 else str(t)
            return str(t)

        teacher_row = st.selectbox("Teacher", teachers, format_func=_tname, key="cah_teacher")
        teacher_name = _tname(teacher_row)

        # Infer classes from teacher_row by intersecting any textual/list fields with known classes
        known_classes = set(classes)
        inferred = []
        if isinstance(teacher_row, dict):
            for v in teacher_row.values():
                inferred += _collect_known_tokens(v, known_classes)
        elif isinstance(teacher_row, (list, tuple)):
            for v in teacher_row:
                inferred += _collect_known_tokens(v, known_classes)
        class_options = sorted(set(inferred)) or classes  # fallback to all if none found

        class_name = st.selectbox("Class", class_options, key=f"cah_class_for_{teacher_name}")

        last_uncorrected = st.date_input("Last Uncorrected Lesson Date", today, key="cah_last_uncorr")
        lesson_title = st.text_input("Lesson Title", key="cah_lesson_title")

        mc1, mc2 = st.columns(2)
        with mc1:
            module_sel = st.selectbox("Module (optional)", [""] + modules, key="cah_module")
        filtered_subs = submodules.get(module_sel, []) if module_sel else []
        with mc2:
            submodule_sel = st.selectbox("Submodule (optional)", [""] + filtered_subs, key="cah_submodule")

        days_gap = (inspection_date - last_uncorrected).days
        status_preview = "GOOD" if days_gap <= 7 else ("NOT_GOOD" if days_gap <= 14 else "BAD")
        st.caption(f"Days Gap: {days_gap} → Status: {status_preview}")

        observations = st.text_area("Observations (optional)", key="cah_obs")

        can_save = bool(teacher_name and class_name and lesson_title)
        if st.button("Save Cahier Entry", disabled=not can_save):
            try:
                upsert_cahier_entry(
                    inspection_date.isoformat(),
                    teacher_name,
                    class_name,
                    last_uncorrected.isoformat(),
                    lesson_title.strip(),
                    module_sel or None,
                    submodule_sel or None,
                    observations.strip() or None
                )
                add_msg("success", f"Saved entry for {teacher_name} / {class_name} ({inspection_date})")
            except Exception as e:
                add_msg("error", f"Save failed: {e}")

    # --- Week navigation ---
    if "cahier_ref_date" not in st.session_state:
        st.session_state.cahier_ref_date = today
    ref_date = st.session_state.cahier_ref_date
    w_start, w_end = _week_bounds(ref_date)

    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        if st.button("◀ Previous Week"):
            st.session_state.cahier_ref_date = ref_date - timedelta(days=7)
            st.rerun()
    with nav2:
        if st.button("Current Week"):
            st.session_state.cahier_ref_date = today
            st.rerun()
    with nav3:
        if st.button("Next Week ▶"):
            st.session_state.cahier_ref_date = ref_date + timedelta(days=7)
            st.rerun()
    with nav4:
        custom_ref = st.date_input("Ref Date", ref_date, key="cah_ref_picker")
        if custom_ref != ref_date:
            st.session_state.cahier_ref_date = custom_ref
            st.rerun()

    st.subheader("This Week Entries")
    st.caption(f"Week Window: {w_start} → {w_end}")

    rows = list_cahier_range(w_start.isoformat(), w_end.isoformat())

    if not rows:
        add_msg("info", "No entries this week.")
        return messages

    df = pd.DataFrame(rows)
    # Convert date strings
    for col in ("inspection_date", "last_uncorrected_date"):
        df[col] = pd.to_datetime(df[col]).dt.date

    display_df = df[[
        "id","inspection_date","teacher_name","class_name","last_uncorrected_date",
        "lesson_title","module","submodule","days_gap","status","observations"
    ]].rename(columns={
        "id":"ID",
        "inspection_date":"Inspection Date",
        "teacher_name":"Teacher",
        "class_name":"Class",
        "last_uncorrected_date":"Last Uncorrected",
        "lesson_title":"Lesson",
        "module":"Module",
        "submodule":"Submodule",
        "days_gap":"Days Gap",
        "status":"Status",
        "observations":"Observations"
    })

    # Row indicator colors via extra column (editable table doesn't support row style)
    def _indicator(row):
        s = row["Status"]
        if s == "GOOD": return "✅"
        if s == "NOT_GOOD": return "⚠️"
        return "❌"  # BAD
    display_df.insert(1, "Indicator", display_df.apply(_indicator, axis=1))

    st.markdown("Edit not enabled yet (future). Indicators: ✅ GOOD | ⚠️ NOT_GOOD | ❌ BAD")
    st.dataframe(display_df, width='stretch')

    # Delete
    del_id = st.number_input("Delete ID", min_value=0, step=1, key="cah_del_id")
    if st.button("Delete Entry", disabled=del_id == 0):
        try:
            delete_cahier_entry(int(del_id))
            add_msg("success", f"Deleted entry {del_id}")
            st.rerun()
        except Exception as e:
            add_msg("error", f"Delete failed: {e}")

    return messages