import streamlit as st
from datetime import date as _date
import pandas as pd
from database import load_teachers, load_today_attendance, save_attendance

START_TIME = "08:00"
LATE_START = "08:31"
VERY_LATE_START = "09:00"

def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h)*60 + int(m)

def _classify(hhmm: str) -> str:
    t = _to_minutes(hhmm)
    if t < _to_minutes(LATE_START):
        return "Present"
    if t < _to_minutes(VERY_LATE_START):
        return "Late"
    return "VeryLate"

def _valid_time(s: str) -> bool:
    if not s or len(s)!=5 or s[2] != ":":
        return False
    hh, mm = s.split(":")
    if not (hh.isdigit() and mm.isdigit()): 
        return False
    h, m = int(hh), int(mm)
    return 0<=h<=23 and 0<=m<=59

def _adjust_time_str(hhmm: str, delta: int) -> str:
    if not _valid_time(hhmm):
        hhmm = START_TIME
    h, m = map(int, hhmm.split(":"))
    tot = h*60 + m + delta
    tot = max(0, min(23*60+59, tot))
    return f"{tot//60:02d}:{tot%60:02d}"

def attendance_menu():
    messages = []
    def add_msg(level, text): messages.append((level, text))

    st.header("📅 Attendance")
    selected_date = st.date_input("Date", _date.today())
    date_key = str(selected_date)

    if "attendance_time_date" not in st.session_state or st.session_state.attendance_time_date != date_key:
        st.session_state.attendance_time_date = date_key
        st.session_state.attendance_time_str = START_TIME
    if "attendance_pending" not in st.session_state:
        st.session_state.attendance_pending = None

    teachers = load_teachers()
    if not teachers:
        add_msg("info", "No teachers found (Supabase 'teachers').")
        return messages

    raw_rows = load_today_attendance(date_key) or []
    existing_map = {r["name"]: {"time": r["time"], "status": r["status"]} for r in raw_rows if r.get("name")}

    st.subheader("Add / Update Sign-in")
    teacher = st.selectbox("Teacher", teachers)

    # Time controls (-1 / textarea / +1)
    c_minus, c_time, c_plus = st.columns([1,4,1])
    with c_minus:
        if st.button("-1 minute"):
            st.session_state.attendance_time_str = _adjust_time_str(st.session_state.attendance_time_str, -1)
    with c_time:
        st.session_state.attendance_time_str = st.text_area(
            "Timestamp (HH:MM) (leave blank for Absent / Excused quick buttons)",
            value=st.session_state.attendance_time_str,
            height=70
        ).strip()
    with c_plus:
        if st.button("+1 minute"):
            st.session_state.attendance_time_str = _adjust_time_str(st.session_state.attendance_time_str, +1)

    hhmm = st.session_state.attendance_time_str
    time_blank = (hhmm == "")

    # Only flag error if non-blank & invalid
    if not time_blank and not _valid_time(hhmm):
        add_msg("error", "Invalid time format (use HH:MM).")
        auto_status = "—"
    elif time_blank:
        auto_status = "—"
        st.caption("No time entered: use quick Absent / Excused buttons below.")
    else:
        auto_status = _classify(hhmm)
        st.caption(f"Automatic status: {auto_status}")

    already = teacher in existing_map
    if already:
        ex = existing_map[teacher]
        st.caption(f"Existing record: {ex.get('time')} ({ex.get('status')})")

    # Quick mark buttons (only when no record yet)
    if not already:
        qb1, qb2 = st.columns([1,1])
        with qb1:
            if st.button("Mark Absent"):
                try:
                    save_attendance(teacher, date_key, None, "Absent")
                    add_msg("success", f"Marked {teacher} Absent")
                except Exception as e:
                    add_msg("error", f"Absent failed: {e}")
        with qb2:
            if st.button("Mark Excused"):
                try:
                    save_attendance(teacher, date_key, None, "Excused")
                    add_msg("success", f"Marked {teacher} Excused")
                except Exception as e:
                    add_msg("error", f"Excused failed: {e}")

    ca, cr = st.columns([1,1])
    with ca:
        # Disable Add/Update if blank time or invalid
        add_disabled = time_blank or (not time_blank and not _valid_time(hhmm))
        if st.button("Add / Update", disabled=add_disabled):
            candidate = {"teacher": teacher, "date": date_key, "time": hhmm, "status": auto_status}
            if already:
                st.session_state.attendance_pending = candidate
                add_msg("warning", f"Pending overwrite for {teacher}. Confirm below.")
            else:
                try:
                    save_attendance(teacher, date_key, hhmm, auto_status)
                    add_msg("success", f"Saved {teacher} {auto_status} @ {hhmm}")
                except Exception as e:
                    add_msg("error", f"Save failed for {teacher}: {e}")
    with cr:
        if st.button("Reset Time"):
            st.session_state.attendance_time_str = START_TIME
            st.session_state.attendance_pending = None
            add_msg("info", "Time reset to 08:00")

    pending = st.session_state.attendance_pending
    if pending:
        st.markdown(
            f"**Confirm overwrite:** {pending['teacher']} "
            f"(Old: {existing_map[pending['teacher']]['status']} @ {existing_map[pending['teacher']]['time']} "
            f"→ New: {pending['status']} @ {pending['time']})"
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm Update"):
                try:
                    save_attendance(pending["teacher"], pending["date"], pending["time"], pending["status"])
                    add_msg("success", f"Updated {pending['teacher']} to {pending['status']} @ {pending['time']}")
                except Exception as e:
                    add_msg("error", f"Update failed: {e}")
                finally:
                    st.session_state.attendance_pending = None
                    (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())
        with c2:
            if st.button("Cancel"):
                st.session_state.attendance_pending = None
                add_msg("info", "Update canceled")
                (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())

    st.subheader(f"Records for {date_key}")

    df = pd.DataFrame(
        [
            {"Teacher": r["name"], "Time": r.get("time") or "", "Status": r.get("status") or ""}
            for r in raw_rows if r.get("name")
        ]
    )

    if df.empty:
        add_msg("info", "No attendance records yet.")
    else:
        original_map = {row.Teacher: (row.Time, row.Status) for row in df.itertuples()}

        auto_reclass = st.checkbox(
            "Auto reclassify Present/Late/VeryLate from Time on save",
            value=True,
            help="Recalculate status from Time for those rows."
        )

        edited_df = st.data_editor(
            df,
            key=f"att_editor_{date_key}",
            num_rows="dynamic",
            column_config={
                "Teacher": st.column_config.TextColumn("Teacher", help="Must match existing teacher."),
                "Time": st.column_config.TextColumn(
                    "Time (HH:MM)",
                    help="Blank for Absent/Excused.",
                    validate="^$|^([0-1][0-9]|2[0-3]):[0-5][0-9]$"  # allow blank
                ),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Present","Late","VeryLate","Absent","Excused"],
                    required=True
                ),
            },
            hide_index=True,
        )

        def _auto_status_from_time(tstr: str) -> str:
            return _classify(tstr) if tstr else "Absent"

        valid_teacher_set = set(teachers)
        invalid_teachers = []
        invalid_times = []
        to_upsert = []

        for row in edited_df.itertuples():
            teacher_name = (row.Teacher or "").strip()
            time_val = (row.Time or "").strip()
            status_val = (row.Status or "").strip()
            if not teacher_name:
                continue
            if teacher_name not in valid_teacher_set:
                invalid_teachers.append(teacher_name)
                continue
            if status_val in ("Present","Late","VeryLate"):
                if not _valid_time(time_val):
                    invalid_times.append(f"{teacher_name} ({time_val or 'blank'})")
                    continue
                if auto_reclass:
                    status_val = _auto_status_from_time(time_val)
            else:
                time_val = ""
            orig = original_map.get(teacher_name)
            if not orig:
                to_upsert.append((teacher_name, time_val or None, status_val))
            else:
                o_time, o_status = orig
                if (o_time or "") != (time_val or "") or o_status != status_val:
                    to_upsert.append((teacher_name, time_val or None, status_val))

        if invalid_teachers:
            add_msg("warning", f"Unknown teacher names ignored: {', '.join(sorted(set(invalid_teachers)))}")
        if invalid_times:
            add_msg("warning", f"Invalid time values ignored: {', '.join(invalid_times)}")

        col_save, col_refresh = st.columns([1,1])
        with col_save:
            if st.button("Save Table Changes", disabled=not to_upsert):
                if to_upsert:
                    saved = 0
                    for teacher_name, time_val, status_val in to_upsert:
                        try:
                            save_attendance(teacher_name, date_key, time_val, status_val)
                            saved += 1
                        except Exception as e:
                            add_msg("error", f"Failed {teacher_name}: {e}")
                    if saved:
                        add_msg("success", f"Applied {saved} change(s).")
                else:
                    add_msg("info", "No changes detected.")
        with col_refresh:
            if st.button("Discard Changes / Refresh"):
                add_msg("info", "Refresh requested.")

    # --- NEW: Full teacher list table (includes unsigned) ---
    st.markdown("---")
    show_full = st.checkbox("Show full teacher list (including not signed)", value=False)
    if show_full:
        # Build map from existing rows
        rec_map = {r["name"]: r for r in raw_rows if r.get("name")}
        full_rows = []
        for t in teachers:
            rec = rec_map.get(t)
            if rec:
                full_rows.append({
                    "Teacher": t,
                    "Time": rec.get("time") or "",
                    "Status": rec.get("status") or ""
                })
            else:
                full_rows.append({
                    "Teacher": t,
                    "Time": "",
                    "Status": "Not Signed"
                })
        full_df = pd.DataFrame(full_rows)

        # Sorting: signed first (Present/Late/VeryLate/Absent/Excused), then by time, then name.
        def _norm_time(t: str) -> str:
            return t if t else "99:99"

        full_df["__signed_order"] = full_df["Status"].apply(lambda s: 0 if s != "Not Signed" else 1)
        full_df["__time_order"] = full_df["Time"].apply(_norm_time)

        full_df = full_df.sort_values(by=["__signed_order", "__time_order", "Teacher"])
        full_df = full_df.drop(columns=["__signed_order", "__time_order"])

        st.dataframe(full_df, use_container_width=True)

    return messages