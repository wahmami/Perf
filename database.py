import streamlit as st
from supabase import create_client
import logging

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
    try:
        res = _table("teachers").select("id,name,first_day,subject,assigned_classes").order("name").execute()
        rows = res.data or []
        return [
            (r.get("id"), r.get("name"), r.get("first_day"), r.get("subject"), r.get("assigned_classes"))
            for r in rows
        ]
    except Exception as e:
        logging.error(f"get_all_teachers error: {e}")
        return []

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

def get_teacher_classes(teacher_name):
    try:
        res = _table("teachers").select("assigned_classes").eq("name", teacher_name).limit(1).execute()
        rows = res.data or []
        if not rows:
            return []
        assigned = rows[0].get("assigned_classes") or ""
        return [c.strip() for c in assigned.split(",") if c.strip()]
    except Exception as e:
        logging.error(f"get_teacher_classes error: {e}")
        return []

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
