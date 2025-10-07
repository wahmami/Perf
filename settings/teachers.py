import streamlit as st
from datetime import date
import importlib.util
from pathlib import Path
from database import get_all_teachers, add_teacher, update_teacher, delete_teacher

CONFIG_PATH = Path("config.py")

def _load_config_lists():
    if not CONFIG_PATH.exists():
        return [], []
    spec = importlib.util.spec_from_file_location("cfgmod", CONFIG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    subjects = list(getattr(mod, "subjects", []))
    classes = list(getattr(mod, "classes", []))
    return subjects, classes

def _parse_csv(value):
    if not value:
        return []
    return [s.strip() for s in value.split(",") if s.strip()]

def render():
    messages = []
    st.subheader("Teachers")

    subject_options, class_options = _load_config_lists()
    if not subject_options:
        st.warning("No subjects found in config.py (subjects = [...]).")
    if not class_options:
        st.warning("No classes found in config.py (classes = [...]).")

    # Add Teacher Form
    with st.form("add_teacher_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2,1,2])
        with c1:
            name = st.text_input("Name*", "")
            first_day = st.date_input("First Day", value=date.today())
        with c2:
            subjects_selected = st.multiselect(
                "Subjects",
                options=subject_options,
                default=subject_options[:1] if subject_options else []
            )
        with c3:
            assigned_selected = st.multiselect(
                "Assigned Classes",
                options=class_options,
                default=[]
            )
        if st.form_submit_button("Add"):
            if not name.strip():
                st.warning("Name required.")
            else:
                add_teacher(
                    name.strip(),
                    str(first_day),
                    ", ".join(subjects_selected) if subjects_selected else None,
                    ", ".join(assigned_selected) if assigned_selected else None
                )
                messages.append(("success", f"Added {name.strip()}"))

    st.divider()
    st.subheader("Existing Teachers")

    rows = get_all_teachers()
    if not rows:
        st.info("No teachers yet.")
        return messages

    # Simple (non-live) filter: updates on Enter / focus change
    filter_text = st.text_input("Filter by name", placeholder="Type part of a name to filter...")
    if filter_text:
        f_lower = filter_text.lower()
        rows = [r for r in rows if (r[1] or "").lower().find(f_lower) != -1]
        if not rows:
            st.warning("No teachers match the filter.")
            return messages

    # Render list
    for r in rows:
        # tuple: (id,name,first_day,subject,assigned_classes)
        tid, tname, first_day, subj_csv, assigned_csv = r
        subj_list = _parse_csv(subj_csv)
        assigned_list = _parse_csv(assigned_csv)

        with st.expander(tname or f"Teacher {tid}", expanded=False):
            ec1, ec2, ec3 = st.columns([2,2,1])
            with ec1:
                new_name = st.text_input("Name", value=tname or "", key=f"name_{tid}")
                new_fd = st.text_input("First Day (YYYY-MM-DD)", value=first_day or "", key=f"fd_{tid}")
            with ec2:
                new_subjects = st.multiselect(
                    "Subjects",
                    options=subject_options,
                    default=[s for s in subj_list if s in subject_options],
                    key=f"subj_{tid}"
                )
                new_assigned = st.multiselect(
                    "Assigned Classes",
                    options=class_options,
                    default=[c for c in assigned_list if c in class_options],
                    key=f"cls_{tid}"
                )
            with ec3:
                col_upd, col_del = st.columns(2)
                if col_upd.button("Update", key=f"upd_{tid}"):
                    update_teacher(
                        tid,
                        name=new_name.strip(),
                        first_day=new_fd.strip() or None,
                        subject=", ".join(new_subjects) if new_subjects else None,
                        assigned_classes=", ".join(new_assigned) if new_assigned else None
                    )
                    messages.append(("success", f"Updated {new_name.strip()}"))
                if col_del.button("Delete", key=f"del_{tid}"):
                    delete_teacher(tid)
                    messages.append(("warning", f"Deleted {tname}"))

    return messages