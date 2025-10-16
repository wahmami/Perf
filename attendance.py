import streamlit as st
from datetime import date as _date
import pandas as pd
from database import load_teachers, load_today_attendance, save_attendance
import unicodedata

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

def _grid_height(n_rows: int, row_h: int = 35, header_h: int = 38, pad: int = 16, max_h: int = 1200) -> int:
    """
    Compute a height so the table shows all rows without inner scrolling.
    Cap at max_h to avoid overly tall pages.
    """
    return min(max_h, header_h + max(1, n_rows) * row_h + pad)

def _ascii_alias(s: str) -> str:
    if s is None:
        return ""
    # remove accents; keep spaces/hyphens
    base = "".join(ch for ch in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(ch))
    return base.upper()

def _augmented_label(name: str) -> str:
    alias = _ascii_alias(name).strip()
    # show alias only if it adds value
    if alias and alias != name.upper() and alias not in name.upper():
        return f"{name} · {alias}"
    return name

def _names_only(items):
    if not items:
        return []
    x = items[0]
    if isinstance(x, dict):
        names = [str(i.get("name", "")).strip() for i in items]
    elif isinstance(x, (list, tuple)):
        names = [str(i[1]).strip() for i in items if len(i) > 1]
    else:
        names = [str(i).strip() for i in items]
    return sorted({n for n in names if n})

def attendance():
    messages = []
    def add_msg(level, text): messages.append((level, text))

    st.header("📅 Attendance")
    selected_date = st.date_input("Date", _date.today())
    date_key = str(selected_date)

    # Init session state for current date
    if "attendance_time_date" not in st.session_state or st.session_state.attendance_time_date != date_key:
        st.session_state.attendance_time_date = date_key
        st.session_state.attendance_time_str = START_TIME
        st.session_state.attendance_pending = None  # clear stale pending when date changes
    if "attendance_pending" not in st.session_state:
        st.session_state.attendance_pending = None
    if "attendance_time_str" not in st.session_state:
        st.session_state.attendance_time_str = START_TIME

    def _inc_time(delta: int):
        cur = st.session_state.get("attendance_time_str", START_TIME)
        st.session_state.attendance_time_str = _adjust_time_str(cur, delta)

    # Load teachers (type-to-filter directly in the selectbox)
    teachers_all = _names_only(load_teachers() or [])
    if not teachers_all:
        add_msg("info", "No teachers found (Supabase 'teachers').")
        return messages
    teacher = st.selectbox(
        "Teacher",
        teachers_all,
        key="att_teacher",
        index=(0 if teachers_all else None),
        placeholder="Select a teacher",
        format_func=_augmented_label
    )
    if not teacher:
        st.info("Type to filter and select a teacher.")
        return messages

    raw_rows = load_today_attendance(date_key) or []
    existing_map = {r["name"]: {"time": r["time"], "status": r["status"]} for r in raw_rows if r.get("name")}

    st.subheader("Add / Update Sign-in")

    # Time controls
    c_minus, c_time, c_plus = st.columns([1,4,1])
    with c_minus:
        st.button("-1 minute", on_click=_inc_time, args=(-1,), key=f"att_time_minus_{date_key}")
    with c_plus:
        st.button("+1 minute", on_click=_inc_time, args=(+1,), key=f"att_time_plus_{date_key}")
    with c_time:
        typed = st.text_input("Timestamp (HH:MM) (leave blank for Absent / Excused quick buttons)", value=st.session_state.attendance_time_str)
        st.session_state.attendance_time_str = (typed or "").strip()

    hhmm = st.session_state.attendance_time_str
    time_blank = (hhmm == "")

    if not time_blank and not _valid_time(hhmm):
        add_msg("error", "Invalid time format (use HH:MM).")
        auto_status = "—"
    elif time_blank:
        auto_status = "—"
        st.caption("No time entered: use quick Absent / Excused buttons below.")
    else:
        auto_status = _classify(hhmm)

    already = teacher in existing_map

    # One row of actions
    add_disabled = time_blank or (not time_blank and not _valid_time(hhmm))
    b1, b2, b3, b4 = st.columns([2, 2, 2, 2])

    with b1:
        if st.button("Add/Update", disabled=add_disabled):
            candidate = {"teacher": teacher, "date": date_key, "time": hhmm, "status": auto_status}
            if already:
                st.session_state.attendance_pending = candidate
            else:
                try:
                    save_attendance(teacher, date_key, hhmm, auto_status)
                    (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())
                except Exception as e:
                    add_msg("error", f"Save failed for {teacher}: {e}")

    with b2:
        if st.button("mark absent", disabled=already):
            try:
                save_attendance(teacher, date_key, None, "Absent")
                (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())
            except Exception as e:
                add_msg("error", f"Absent failed: {e}")

    with b3:
        if st.button("mark excused", disabled=already):
            try:
                save_attendance(teacher, date_key, None, "Excused")
                (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())
            except Exception as e:
                add_msg("error", f"Excused failed: {e}")

    with b4:
        if st.button("reset time"):
            st.session_state.attendance_time_str = START_TIME
            st.session_state.attendance_pending = None

    pending = st.session_state.attendance_pending
    if pending and pending.get("date") != date_key:
        st.session_state.attendance_pending = None
        pending = None

    if pending:
        old = existing_map.get(pending["teacher"])
        old_status = (old.get("status") if old else "—")
        old_time = (old.get("time") if old else "—")
        st.markdown(f"**Confirm overwrite:** {pending['teacher']} (Old: {old_status} @ {old_time} → New: {pending['status']} @ {pending['time']})")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm Update"):
                try:
                    save_attendance(pending["teacher"], pending["date"], pending["time"], pending["status"])
                except Exception as e:
                    add_msg("error", f"Update failed: {e}")
                finally:
                    st.session_state.attendance_pending = None
                    (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())
        with c2:
            if st.button("Cancel"):
                st.session_state.attendance_pending = None

    st.subheader(f"Records for {date_key}")

    df = pd.DataFrame(
        [
            {"Teacher": r["name"], "Time": r.get("time") or "", "Status": r.get("status") or ""}
            for r in raw_rows if r.get("name")
        ]
    )
    # Sort by time descending (valid HH:MM first, blanks last), then Teacher asc for stability
    if not df.empty:
        def _to_min_or_neg1(s: str) -> int:
            try:
                if isinstance(s, str) and len(s) == 5 and s[2] == ":":
                    hh, mm = s.split(":")
                    if hh.isdigit() and mm.isdigit():
                        return int(hh) * 60 + int(mm)
            except Exception:
                pass
            return -1  # blanks/invalid at bottom when sorting desc
        df["__sort_time"] = df["Time"].apply(_to_min_or_neg1)
        df = df.sort_values(["__sort_time", "Teacher"], ascending=[False, True]).drop(columns="__sort_time")

    if df.empty:
        add_msg("info", "No attendance records yet.")
    else:
        def _row_bg_color(row):
            t = (row.get("Time") or "").strip()
            try:
                hh, mm = t.split(":")
                mins = int(hh) * 60 + int(mm)
            except Exception:
                return [""] * len(row)
            if mins >= 8 * 60 + 46:
                color = "background-color: #ffd6d6"  # light red
            elif 8 * 60 + 31 <= mins <= 8 * 60 + 45:
                color = "background-color: #ffe5b4"  # light orange
            else:
                return [""] * len(row)
            return [color] * len(row)

        st.markdown("---")
        c_left, c_right = st.columns([3, 2])

        with c_left:
            st.subheader("Attendance (highlighted)")
            st.dataframe(
                df.style.apply(_row_bg_color, axis=1),
                width="stretch",
                height=_grid_height(len(df))
            )

        with c_right:
            st.subheader("Absent / Not Signed teachers")
            rec_map = {r["name"]: r for r in raw_rows if r.get("name")}
            rows_missing = []
            for t in teachers_all:
                 rec = rec_map.get(t)
                 if rec is None:
                     rows_missing.append({"Teacher": t, "Status": "Not Signed", "Time": ""})
                 else:
                     if rec.get("status") == "Absent":
                         rows_missing.append({"Teacher": t, "Status": "Absent", "Time": rec.get("time") or ""})
            if rows_missing:
                df_missing = pd.DataFrame(rows_missing)
                df_missing["__order"] = df_missing["Status"].apply(lambda s: 0 if s == "Not Signed" else 1)
                df_missing = df_missing.sort_values(by=["__order", "Teacher"]).drop(columns="__order")
                st.dataframe(df_missing, width="stretch", height=_grid_height(len(df_missing)))
            else:
                st.info("No Absent or Not Signed teachers.")

    return messages

def attendance_menu():
    return attendance()