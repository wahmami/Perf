import streamlit as st
import pandas as pd
from datetime import date
from database import (
    load_teachers,
    list_rapports_for_teacher,
    upsert_rapport_delivery,
    list_rapports,
    list_rapport_assignments,
    list_deliveries_for_rapport,
)

def _teacher_names_only(items):
    if not items: return []
    x = items[0]
    if isinstance(x, dict): return [i.get("name","") for i in items]
    if isinstance(x, (list, tuple)): return [i[1] for i in items]
    return [str(i) for i in items]

def rapports():
    st.header("📄 Rapports")

    # Record delivery
    st.subheader("Record delivery")
    teachers = _teacher_names_only(load_teachers() or [])
    teacher = st.selectbox("Teacher", teachers, key="rp_teacher")

    rapts = list_rapports_for_teacher(teacher) if teacher else []
    r_labels = [f"{r['id']} — {r['title']} (due {r['due_date']})" for r in rapts]
    sel = st.selectbox("Rapport", r_labels, index=(0 if r_labels else None), key="rp_sel_rapport")
    sel_r = rapts[r_labels.index(sel)] if sel else None

    delivered_at = st.date_input("Delivery day", value=date.today(), key="rp_delivered_at")
    observations = st.text_area("Observations (optional)", key="rp_obs")

    can_save = bool(teacher and sel_r)
    if st.button("Save delivery", key="rp_save_delivery", disabled=not can_save):
        upsert_rapport_delivery(sel_r["id"], teacher, delivered_at.isoformat(), observations.strip() or None)
        st.success("Saved.")

    st.markdown("---")

    # Status by rapport
    st.subheader("Status by rapport")
    rap_all = list_rapports()
    labels = [f"{r['id']} — {r['title']} (due {r['due_date']})" for r in rap_all]
    sel2 = st.selectbox("Rapport to review", labels, index=(0 if labels else None), key="rp_review_rapport")
    r2 = rap_all[labels.index(sel2)] if sel2 else None

    if r2:
        assigned = list_rapport_assignments(r2["id"]) or []
        deliveries = {d["teacher_name"]: d for d in (list_deliveries_for_rapport(r2["id"]) or [])}
        rows = []
        for t in assigned:
            d = deliveries.get(t)
            rows.append({
                "Teacher": t,
                "Delivered": (d.get("delivered_at") if d else ""),
                "Status": (d.get("status") if d else "NOT_DELIVERED"),
                "Days Diff": (d.get("days_diff") if d else ""),
                "Observations": (d.get("observations") if d else ""),
            })
        df = pd.DataFrame(rows).sort_values("Teacher")
        st.dataframe(df, width='stretch')
    return []