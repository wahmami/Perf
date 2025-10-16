import streamlit as st
from supabase import create_client
import logging
from datetime import date as _date

# Remove (or leave) sqlite bits if no longer needed for attendance
# import sqlite3
# from pathlib import Path
# DB_PATH = Path("perfman.db")

_cfg = st.secrets.get("supabase", {}) or {}
if not _cfg.get("url") or not _cfg.get("key"):
    raise RuntimeError("Missing [supabase] section in Streamlit secrets (url/key).")

supabase = create_client(_cfg["url"], _cfg["key"])

def _table(name: str):
    return supabase.table(name)

# ---------- Teachers (Supabase) ----------
def load_teachers():
    try:
        res = _table("teachers").select("name").order("name").execute()
        return [r["name"] for r in (res.data or []) if r.get("name")]
    except Exception as e:
        logging.error(f"load_teachers error: {e}")
        return []

def get_all_teachers():
    """
    Wrapper so cahiers.py can import this.
    Reuse existing load_teachers() if present.
    """
    try:
        return load_teachers()
    except NameError:
        # Fallback direct select if load_teachers not defined.
        res = _table("teachers").select("*").order("name").execute()
        return res.data or []

def add_teacher(name, first_day=None, subject=None, assigned_classes=None):
    try:
        _table("teachers").insert({
            "name": name,
            "first_day": first_day,
            "subject": subject,
            "assigned_classes": assigned_classes
        }).execute()
    except Exception as e:
        logging.error(f"add_teacher error: {e}")

def update_teacher(teacher_id, **fields):
    fields.pop("level", None)
    try:
        _table("teachers").update(fields).eq("id", teacher_id).execute()
    except Exception as e:
        logging.error(f"update_teacher error: {e}")

def delete_teacher(teacher_id):
    try:
        _table("teachers").delete().eq("id", teacher_id).execute()
    except Exception as e:
        logging.error(f"delete_teacher error: {e}")

def get_assigned_classes_for_teacher(teacher_name: str) -> list[str]:
    """
    Return assigned_classes for a teacher by name.
    Supports text CSV or JSON array in the teachers table.
    """
    try:
        res = _table("teachers").select("assigned_classes").eq("name", teacher_name).single().execute()
        raw = (res.data or {}).get("assigned_classes")
        return _split_classes(raw)
    except Exception as e:
        logging.error(f"get_assigned_classes_for_teacher error: {e}")
        return []

# ---------- Attendance (Supabase unified) ----------
def save_attendance(teacher_name: str, date_str: str, time_str: str | None, status: str):
    """
    Upsert attendance row in Supabase (unique teacher_name+date)
    """
    try:
        # Check existing
        existing = _table("attendance").select("id").eq("teacher_name", teacher_name).eq("date", date_str).limit(1).execute()
        rows = existing.data or []
        if rows:
            aid = rows[0]["id"]
            _table("attendance").update({
                "time": time_str,
                "status": status
            }).eq("id", aid).execute()
        else:
            _table("attendance").insert({
                "teacher_name": teacher_name,
                "date": date_str,
                "time": time_str,
                "status": status
            }).execute()
    except Exception as e:
        logging.error(f"save_attendance error: {e}")
        raise

def load_today_attendance(date_str: str):
    try:
        # FIX: remove invalid dict argument
        res = _table("attendance")\
            .select("teacher_name,time,status")\
            .eq("date", date_str)\
            .order("time", desc=False)\
            .execute()
        return [
            {
                "name": r.get("teacher_name"),
                "date": date_str,
                "time": r.get("time"),
                "status": r.get("status")
            } for r in (res.data or [])
        ]
    except Exception as e:
        logging.error(f"load_today_attendance error: {e}")
        return []

def get_attendance_for_teacher(teacher_name: str):
    try:
        res = _table("attendance").select("date,status").eq("teacher_name", teacher_name).order("date", {"ascending": True}).execute()
        return res.data or []
    except Exception as e:
        logging.error(f"get_attendance_for_teacher error: {e}")
        return []

# ---------- Journal (Supabase) ----------
def add_journal_entry(teacher_name, date, status, observation, outdated_days):
    try:
        _table("journal").insert({
            "teacher_name": teacher_name, "date": date, "status": status,
            "observation": observation, "outdated_days": outdated_days
        }).execute()
    except Exception as e:
        logging.error(f"add_journal_entry error: {e}")

def get_journal_entries(date=None):
    try:
        q = _table("journal").select("teacher_name,date,status,observation,outdated_days")
        if date:
            q = q.eq("date", date)
        res = q.execute()
        return res.data or []
    except Exception as e:
        logging.error(f"get_journal_entries error: {e}")
        return []

JOURNAL_TABLE = "journal_inspections"

def upsert_journal_record(inspection_date: str, teacher_name: str, last_entry_date: str, observations: str | None):
    """
    Auto-derive status / days_late:
      UPDATED if last_entry_date == inspection_date
      OUTDATED otherwise (days_late = inspection_date - last_entry_date)
    """
    from datetime import date
    d_ins = date.fromisoformat(inspection_date)
    d_last = date.fromisoformat(last_entry_date)
    if d_last >= d_ins:
        status = "UPDATED"
        days_late = 0
    else:
        days_late = (d_ins - d_last).days
        status = "OUTDATED"
    payload = {
        "inspection_date": inspection_date,
        "teacher_name": teacher_name,
        "last_entry_date": last_entry_date,
        "status": status,
        "days_late": days_late,
        "observations": observations
    }
    _table(JOURNAL_TABLE).upsert(payload, on_conflict="inspection_date,teacher_name").execute()

def list_journal_range(start_date: str, end_date: str):
    res = _table(JOURNAL_TABLE)\
        .select("id,inspection_date,teacher_name,last_entry_date,status,days_late,observations")\
        .gte("inspection_date", start_date)\
        .lte("inspection_date", end_date)\
        .order("inspection_date")\
        .order("teacher_name")\
        .execute()
    return res.data or []

def delete_journal_record(rec_id: int):
    _table(JOURNAL_TABLE).delete().eq("id", rec_id).execute()

# ---------- Cahier (Supabase) ----------
def add_cahier_entry(teacher_name, inspection_date, last_corrected_date, last_corrected_module, last_corrected_title, observation, uncorrected_lessons):
    try:
        payload = {
            "teacher_name": teacher_name,
            "inspection_date": str(inspection_date),
            "last_corrected_date": str(last_corrected_date) if last_corrected_date else None,
            "last_corrected_module": last_corrected_module,
            "last_corrected_title": last_corrected_title,
            "observation": observation
        }
        res = _table("cahiers").insert(payload).execute()
        cahier = (res.data or [None])[0]
        cahier_id = cahier.get("id") if cahier else None
        if cahier_id and uncorrected_lessons:
            for lesson in uncorrected_lessons:
                lesson_payload = {
                    "cahier_id": cahier_id,
                    "lesson_date": str(lesson.get("date")) if lesson.get("date") else None,
                    "module": lesson.get("module"),
                    "title": lesson.get("title")
                }
                _table("cahiers_uncorrected").insert(lesson_payload).execute()
    except Exception as e:
        logging.error(f"add_cahier_entry error: {e}")

def get_cahier_entries():
    try:
        res = _table("cahiers").select("*").order("inspection_date", {"ascending": False}).execute()
        cahiers = res.data or []
        results = []
        for c in cahiers:
            unc_res = _table("cahiers_uncorrected").select("*").eq("cahier_id", c.get("id")).execute()
            uncorrected = unc_res.data or []
            results.append({
                "id": c.get("id"),
                "teacher_name": c.get("teacher_name"),
                "inspection_date": c.get("inspection_date"),
                "last_corrected_date": c.get("last_corrected_date"),
                "last_corrected_module": c.get("last_corrected_module"),
                "last_corrected_title": c.get("last_corrected_title"),
                "observation": c.get("observation"),
                "uncorrected": uncorrected
            })
        return results
    except Exception as e:
        logging.error(f"get_cahier_entries error: {e}")
        return []

# ---------- Cahier (lesson book) checks ----------
CAHIER_TABLE = "cahier_checks"

def get_all_teachers():
    """
    Wrapper so cahiers.py can import this.
    Reuse existing load_teachers() if present.
    """
    try:
        return load_teachers()
    except NameError:
        # Fallback direct select if load_teachers not defined.
        res = _table("teachers").select("*").order("name").execute()
        return res.data or []

def upsert_cahier_entry(
    inspection_date: str,
    teacher_name: str,
    class_name: str,
    last_uncorrected_date: str,
    lesson_title: str,
    module: str | None,
    submodule: str | None,
    observations: str | None
):
    from datetime import date
    d_ins = date.fromisoformat(inspection_date)
    d_last = date.fromisoformat(last_uncorrected_date)
    days_gap = max(0, (d_ins - d_last).days)
    if days_gap <= 7:
        status = "GOOD"
    elif days_gap <= 14:
        status = "NOT_GOOD"
    else:
        status = "BAD"
    payload = {
        "inspection_date": inspection_date,
        "teacher_name": teacher_name,
        "class_name": class_name,
        "last_uncorrected_date": last_uncorrected_date,
        "lesson_title": lesson_title,
        "module": module,
        "submodule": submodule,
        "days_gap": days_gap,
        "status": status,
        "observations": observations
    }
    _table(CAHIER_TABLE).upsert(payload, on_conflict="inspection_date,teacher_name,class_name").execute()

# Optional simple add alias (kept for imports)
def add_cahier_entry(*args, **kwargs):
    return upsert_cahier_entry(*args, **kwargs)

def list_cahier_range(start_date: str, end_date: str):
    res = _table(CAHIER_TABLE)\
        .select("id,inspection_date,teacher_name,class_name,last_uncorrected_date,lesson_title,module,submodule,days_gap,status,observations")\
        .gte("inspection_date", start_date)\
        .lte("inspection_date", end_date)\
        .order("inspection_date")\
        .order("teacher_name")\
        .execute()
    return res.data or []

def delete_cahier_entry(entry_id: int):
    _table(CAHIER_TABLE).delete().eq("id", entry_id).execute()
# ---------- end cahier ----------

# ---------- Materials (Supabase) ----------
def add_material_entry(teacher_name, material, quantity, date):
    try:
        payload = {
            "teacher_name": teacher_name,
            "material": material,
            "quantity": int(quantity) if quantity is not None else None,
            "date": str(date)
        }
        _table("materials").insert(payload).execute()
    except Exception as e:
        logging.error(f"add_material_entry error: {e}")

def get_material_entries():
    try:
        res = _table("materials").select("*").order("date", {"ascending": False}).execute()
        return res.data or []
    except Exception as e:
        logging.error(f"get_material_entries error: {e}")
        return []

# ---------- Rapport Deliveries (Supabase) ----------
def add_rapport_delivery(rapport_id, teacher_name, delivered_day, delivered_classes, days_late):
    try:
        payload = {
            "rapport_id": rapport_id,
            "teacher_name": teacher_name,
            "delivered_day": str(delivered_day) if delivered_day is not None else None,
            "delivered_classes": delivered_classes,
            "days_late": int(days_late) if days_late is not None else None
        }
        _table("rapport_deliveries").insert(payload).execute()
    except Exception as e:
        logging.error(f"add_rapport_delivery error: {e}")

def get_rapport_deliveries():
    try:
        del_res = _table("rapport_deliveries").select("*").order("delivered_day", desc=True).execute()
        deliveries = del_res.data or []

        # fetch rapports to enrich deliveries with title/due_date
        rap_res = _table("rapports").select("id,title,due_date").execute()
        rapports = {r["id"]: r for r in (rap_res.data or [])}

        results = []
        for d in deliveries:
            rapport = rapports.get(d.get("rapport_id"))
            results.append({
                "title": rapport.get("title") if rapport else None,
                "due_date": rapport.get("due_date") if rapport else None,
                "teacher_name": d.get("teacher_name"),
                "delivered_day": d.get("delivered_day"),
                "delivered_classes": d.get("delivered_classes"),
                "days_late": d.get("days_late")
            })
        return results
    except Exception as e:
        logging.error(f"get_rapport_deliveries error: {e}")
        return []

# ---------- Rapports (Supabase) ----------
def add_rapport(title, due_date, classes):
    try:
        payload = {"title": title, "due_date": str(due_date), "classes": classes}
        _table("rapports").insert(payload).execute()
    except Exception as e:
        logging.error(f"add_rapport error: {e}")

def update_rapport(rapport_id, title, due_date, classes):
    try:
        _table("rapports").update({
            "title": title,
            "due_date": str(due_date),
            "classes": classes
        }).eq("id", rapport_id).execute()
    except Exception as e:
        logging.error(f"update_rapport error: {e}")

def delete_rapport(rapport_id):
    try:
        # remove related deliveries first, then the rapport
        _table("rapport_deliveries").delete().eq("rapport_id", rapport_id).execute()
        _table("rapports").delete().eq("id", rapport_id).execute()
    except Exception as e:
        logging.error(f"delete_rapport error: {e}")

def _split_classes(val):
    if not val:
        return []
    if isinstance(val, (list, tuple)):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        return [p.strip() for p in val.replace(";", ",").split(",") if p.strip()]
    return []

def get_teachers_light():
    """
    Minimal teacher rows for UI: id, name, classes (CSV or array).
    """
    res = _table("teachers").select("id,name,classes").order("name").execute()
    return res.data or []

def get_teacher_classes(teacher_id: int):
    """
    Normalize teachers.classes to a list[str].
    """
    res = _table("teachers").select("classes").eq("id", teacher_id).single().execute()
    raw = (res.data or {}).get("classes")
    return _split_classes(raw)

# ---------- Devoir (Supabase) ----------
def add_devoir_entry(teacher_name, class_name, thursday_date, status, sent_date, days_late):
    try:
        payload = {
            "teacher_name": teacher_name,
            "class_name": class_name,
            "thursday_date": str(thursday_date) if thursday_date is not None else None,
            "status": status,
            "sent_date": str(sent_date) if sent_date is not None else None,
            "days_late": int(days_late) if days_late is not None else None
        }
        _table("devoir").insert(payload).execute()
    except Exception as e:
        logging.error(f"add_devoir_entry error: {e}")

def get_devoir_entries():
    try:
        res = _table("devoir").select("*").order("thursday_date", {"ascending": False}).execute()
        return res.data or []
    except Exception as e:
        logging.error(f"get_devoir_entries error: {e}")
        return []

def is_level_unique(level, exclude_teacher_id=None):
    try:
        q = _table("teachers").select("id").eq("level", level)
        if exclude_teacher_id is not None:
            q = q.neq("id", exclude_teacher_id)
        res = q.limit(1).execute()
        rows = res.data or []
        return len(rows) == 0
    except Exception as e:
        logging.error(f"is_level_unique error: {e}")
        return False

def get_rapports():
    try:
        # latest due_date first; set desc=True if you want newest first
        res = _table("rapports").select("id,title,due_date,classes").order("due_date", desc=True).execute()
        return res.data or []
    except Exception as e:
        logging.error(f"get_rapports error: {e}")
        return []

# Calendar overrides (vacations / weekend working) ---------------------------
CALENDAR_TABLE = "calendar_overrides"

def add_calendar_override(kind: str, start_date: str, end_date: str, label: str | None):
    """
    kind: 'VACATION' or 'WORKING'
    dates: 'YYYY-MM-DD'
    """
    _table(CALENDAR_TABLE).insert({
        "kind": kind,
        "start_date": start_date,
        "end_date": end_date,
        "label": label
    }).execute()

def delete_calendar_override(override_id: int):
    _table(CALENDAR_TABLE).delete().eq("id", override_id).execute()

def load_overrides_range(start_date: str, end_date: str):
    """
    Return overrides whose ranges INTERSECT the window [start_date, end_date].
    Overlap condition: row.start_date <= end_date AND row.end_date >= start_date
    """
    try:
        res = _table(CALENDAR_TABLE)\
            .select("id,kind,start_date,end_date,label")\
            .lte("start_date", end_date)\
            .gte("end_date", start_date)\
            .order("start_date")\
            .execute()
        rows = res.data or []
        # Defensive filter (in case of unexpected rows)
        return [
            r for r in rows
            if r["start_date"] <= end_date and r["end_date"] >= start_date
        ]
    except Exception as e:
        logging.error(f"load_overrides_range error: {e}")
        return []

# Optional: add a raw fetch for debugging
def debug_all_overrides():
    try:
        res = _table(CALENDAR_TABLE).select("*").order("start_date").execute()
        return res.data or []
    except Exception as e:
        logging.error(f"debug_all_overrides error: {e}")
        return []

# --- Rapports (templates, assignments, deliveries) ---

def create_rapport(title: str, announce_date: str, due_date: str) -> int:
    res = _table("rapports").insert({
        "title": title,
        "announce_date": announce_date,
        "due_date": due_date,
    }).execute()
    return (res.data or [{}])[0].get("id")

def list_rapports():
    res = _table("rapports")\
        .select("id,title,announce_date,due_date")\
        .order("announce_date", desc=True).execute()
    return res.data or []

def delete_rapport(rapport_id: int):
    # cascade cleanup
    _table("rapport_deliveries").delete().eq("rapport_id", rapport_id).execute()
    _table("rapport_assignments").delete().eq("rapport_id", rapport_id).execute()
    _table("rapports").delete().eq("id", rapport_id).execute()

def set_rapport_assignments(rapport_id: int, teacher_names: list[str]):
    # replace all assignments atomically
    _table("rapport_assignments").delete().eq("rapport_id", rapport_id).execute()
    if teacher_names:
        rows = [{"rapport_id": rapport_id, "teacher_name": t} for t in teacher_names if t]
        _table("rapport_assignments").insert(rows).execute()

def list_rapport_assignments(rapport_id: int):
    res = _table("rapport_assignments")\
        .select("teacher_name").eq("rapport_id", rapport_id)\
        .order("teacher_name").execute()
    return [r["teacher_name"] for r in (res.data or []) if r.get("teacher_name")]

def list_rapports_for_teacher(teacher_name: str):
    try:
        asg = _table("rapport_assignments").select("rapport_id")\
            .eq("teacher_name", teacher_name).execute()
        ids = [r["rapport_id"] for r in (asg.data or [])]
        if not ids:
            return []
        res = _table("rapports")\
            .select("id,title,announce_date,due_date")\
            .in_("id", ids).order("announce_date", desc=True).execute()
        return res.data or []
    except Exception:
        return []

def _status_from_delivery(_due: str, _delivered: str):
    d_due = _date.fromisoformat(_due)
    d_del = _date.fromisoformat(_delivered)
    diff = (d_del - d_due).days  # negative=EARLY, 0=ON_TIME, positive=LATE
    if diff < 0:
        return "EARLY", diff
    if diff == 0:
        return "ON_TIME", 0
    return "LATE", diff

def upsert_rapport_delivery(rapport_id: int, teacher_name: str, delivered_at: str, observations: str | None):
    # fetch due_date
    res = _table("rapports").select("due_date").eq("id", rapport_id).single().execute()
    if not res.data or "due_date" not in res.data:
        raise ValueError(f"Rapport {rapport_id} not found")
    due_date = res.data["due_date"]
    status, days_diff = _status_from_delivery(due_date, delivered_at)
    payload = {
        "rapport_id": rapport_id,
        "teacher_name": teacher_name,
        "delivered_at": delivered_at,
        "status": status,
        "days_diff": days_diff,
        "observations": observations,
    }
    _table("rapport_deliveries").upsert(payload, on_conflict="rapport_id,teacher_name").execute()

# Backward-compat alias if needed
def add_rapport_delivery(*args, **kwargs):
    return upsert_rapport_delivery(*args, **kwargs)

def list_deliveries_for_rapport(rapport_id: int):
    res = _table("rapport_deliveries")\
        .select("id,rapport_id,teacher_name,delivered_at,status,days_diff,observations")\
        .eq("rapport_id", rapport_id).order("teacher_name").execute()
    return res.data or []

# ---------- Devoirs (scope + weekly tracking) ----------

def list_devoirs_scope():
    res = _table("devoirs_scope")\
        .select("id,teacher_name,class_name")\
        .order("teacher_name").order("class_name").execute()
    return res.data or []

def list_devoirs_teachers():
    res = _table("devoirs_scope").select("teacher_name").execute()
    names = sorted({r["teacher_name"] for r in (res.data or []) if r.get("teacher_name")})
    return names

def get_devoirs_classes_for_teacher(teacher_name: str):
    res = _table("devoirs_scope").select("class_name").eq("teacher_name", teacher_name)\
        .order("class_name").execute()
    return [r["class_name"] for r in (res.data or []) if r.get("class_name")]

def set_devoirs_classes_for_teacher(teacher_name: str, classes: list[str]):
    _table("devoirs_scope").delete().eq("teacher_name", teacher_name).execute()
    rows = [{"teacher_name": teacher_name, "class_name": c} for c in (classes or []) if c]
    if rows:
        _table("devoirs_scope").insert(rows).execute()

def clear_devoirs_for_teacher(teacher_name: str):
    _table("devoirs_scope").delete().eq("teacher_name", teacher_name).execute()

def list_devoirs_for_week(week_thursday: str):
    res = _table("devoirs_weekly")\
        .select("id,teacher_name,class_name,week_thursday,posted_at,status,days_late,observations")\
        .eq("week_thursday", week_thursday)\
        .order("teacher_name").order("class_name").execute()
    return res.data or []

def upsert_devoir_week(teacher_name: str, class_name: str, week_thursday: str,
                       posted_at: str | None, observations: str | None):
    d_thu = _date.fromisoformat(week_thursday)
    if posted_at:
        d_post = _date.fromisoformat(posted_at)
        diff = (d_post - d_thu).days
        if diff <= 0:
            status, days_late = "ON_TIME", 0
        else:
            status, days_late = "LATE", diff
    else:
        status, days_late = "NOT_POSTED", None
    payload = {
        "teacher_name": teacher_name,
        "class_name": class_name,
        "week_thursday": week_thursday,
        "posted_at": posted_at,
        "status": status,
        "days_late": days_late,
        "observations": observations,
    }
    _table("devoirs_weekly").upsert(
        payload, on_conflict="teacher_name,class_name,week_thursday"
    ).execute()
# ---------- end Devoirs ----------

def add_material_entry(the_date: str, teacher_name: str, material: str):
    _table("materials_log").insert({
        "day": the_date,
        "teacher_name": teacher_name,
        "material": material
    }).execute()

def list_material_entries_for_teacher(teacher_name: str):
    res = _table("materials_log")\
        .select("id,day,teacher_name,material")\
        .eq("teacher_name", teacher_name)\
        .order("day", desc=True).execute()
    return res.data or []

def list_material_group_for_teacher(teacher_name: str):
    """
    Returns list of {material, count} grouped.
    """
    rows = list_material_entries_for_teacher(teacher_name)
    counts = {}
    for r in rows:
        m = r.get("material")
        if not m:
            continue
        counts[m] = counts.get(m, 0) + 1
    return [{"material": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
