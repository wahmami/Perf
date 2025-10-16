# PerfMan

Application Streamlit pour le suivi de performance pédagogique (présences, cahiers, devoirs, rapports, matériaux, configuration).

## Sommaire
1. Attendance (Présence enseignants)
2. Journal (Inspection cahiers / livres)
3. Cahiers (Suivi des cahiers par enseignant / classe)
4. Devoirs (Devoirs hebdomadaires en ligne – jeudi)
5. Rapports (Création, affectations, livraisons)
6. Materials (Usage des matériaux pédagogiques)
7. Settings (Configuration centrale)
8. Base de Données (Tables Supabase)
9. Variables & Secrets
10. Lancement & Déploiement
11. Roadmap
12. Licence / Avertissements
13. Cheat Sheet

---

## 1. Attendance
Objectif: enregistrer l’heure d’arrivée + statut par date.

Fonctionnalités principales:
- Saisie avec ajustement ±1 minute
- Classification automatique (Present / Late / VeryLate)
- Marquage rapide Absent / Excused (heure NULL)
- Confirmation avant écrasement
- Table éditable sans scroll interne
- Vue des enseignants Not Signed / Absent

Règles:
- Statuts temporels exigent HH:MM valide
- Absent / Excused: time = NULL
- Reclassification automatique optionnelle lors des sauvegardes groupées

---

## 2. Journal
Contrôle de mise à jour des cahiers enseignants.

Champs:
- inspection_date
- teacher_name
- last_entry_date
- status (UPDATED / OUTDATED)
- days_late (si OUTDATED)
- observations

Unicité: (inspection_date, teacher_name)

Vue semaine dynamique (navigation + table éditable + indicateurs).

---

## 3. Cahiers
Suivi par enseignant + classes réellement assignées (assigned_classes).
- Sélection enseignant → classe issue de assigned_classes
- Saisie / consultation selon la logique interne (non détaillée ici si module déjà existant)
- Harmonisé avec la logique Devoirs (pas de scope manuel séparé)

---

## 4. Devoirs
Chaque enseignant doit publier un devoir en ligne chaque jeudi.
Stockage par trio (teacher_name, class_name, week_thursday).

Champs:
- teacher_name
- class_name
- week_thursday (date du jeudi de la semaine)
- posted_at (date, nullable)
- status (ON_TIME / LATE / NOT_POSTED)
- days_late (int, NULL si NOT_POSTED)
- observations (texte)

Logique:
- posted_at ≤ jeudi → ON_TIME (days_late=0)
- posted_at > jeudi → LATE (days_late = diff jours)
- posted_at NULL → NOT_POSTED

Classes listées = assigned_classes de l’enseignant (pas de scope manuel supplémentaire).

---

## 5. Rapports
Gestion des rapports internes.

Tables:
- rapports: id, title, announce_date, due_date, inserted_at
- rapport_assignments: rapport_id, teacher_name (unique pair)
- rapport_deliveries: rapport_id, teacher_name, delivered_at, status (EARLY / ON_TIME / LATE), days_diff, observations

Logique status (livraison vs due_date):
- livré < due_date → EARLY
- livré = due_date → ON_TIME
- livré > due_date → LATE
Absence de livraison dans la vue récap → NOT_DELIVERED.

Actions:
- Création rapport + affectations initiales
- Édition des affectations (add/remove)
- Suppression (cascade assignments + deliveries)
- Page Rapports: saisie livraison + revue par rapport (table des enseignants, statut).

---

## 6. Materials
Enregistrement de l’usage des matériaux pédagogiques.

Champs (materials_log):
- day
- teacher_name
- material (issu de config.py)
- inserted_at

Vue:
- Formulaire: date / enseignant / matériel / sauvegarde
- Historique des entrées (table)
- Regroupement (count par matériel)

---

## 7. Settings
Onglets:
- Teachers (table Supabase)
- Subjects
- Classes
- Materials
- Modules
- Submodules
- Vacations (overrides calendrier)
- Rapports

Édition des listes CSV → génération / réécriture de config.py.

Vacations:
- VACATION (jour/plage)
- WORKING (activation week-end)
- Filtre intervalle (par défaut mois courant)

---

## 8. Base de Données (Supabase)
Tables principales (résumé):

```
teachers
attendance
journal_inspections
calendar_overrides
rapports
rapport_assignments
rapport_deliveries
devoirs_weekly
materials_log
```

Exemple rapports:
```
rapports(
  id bigserial PK,
  title text,
  announce_date date,
  due_date date,
  inserted_at timestamptz
)
rapport_assignments(
  id bigserial PK,
  rapport_id bigint FK -> rapports(id) cascade,
  teacher_name text,
  unique(rapport_id, teacher_name)
)
rapport_deliveries(
  id bigserial PK,
  rapport_id bigint FK -> rapports(id) cascade,
  teacher_name text,
  delivered_at date,
  status text check in (EARLY,ON_TIME,LATE),
  days_diff int,
  observations text,
  unique(rapport_id, teacher_name)
)
```

Exemple devoirs:
```
devoirs_weekly(
  id bigserial PK,
  teacher_name text,
  class_name text,
  week_thursday date,
  posted_at date null,
  status text check in (ON_TIME,LATE,NOT_POSTED),
  days_late int null,
  observations text,
  unique(teacher_name, class_name, week_thursday)
)
```

Exemple materials:
```
materials_log(
  id bigserial PK,
  day date,
  teacher_name text,
  material text,
  inserted_at timestamptz
)
```

---

## 9. Variables & Secrets
Ne pas versionner:
- .streamlit/secrets.toml
- .env*

Variables:
- SUPABASE_URL
- SUPABASE_KEY

Chargement:
```
import os
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
```

---

## 10. Lancement & Déploiement
Installation:
```
pip install -r requirements.txt
```
Exécution locale:
```
streamlit run app.py
```
Mise à jour dépendances:
```
pip freeze > requirements.txt
```

---

## 11. Roadmap (exemples)
- Export CSV (Attendance / Journal / Rapports / Devoirs)
- Stats agrégées (retards, taux ON_TIME)
- Rôles / permissions
- Visualisation calendrier (Vacations)
- Filtres avancés Journal / Rapports
- Notifications (rapports en retard)
- Recalcul auto si due_date modifiée (rapports)

---

## 12. Licence / Avertissements
Usage interne. Rotation immédiate des clés en cas d’exposition. Adapter RLS (Row Level Security) si besoin.

---

## 13. Cheat Sheet

Attendance:
- Present/Late/VeryLate auto selon HH:MM
- Absent/Excused: time NULL
- Overwrite nécessite confirmation

Journal:
- status = UPDATED si last_entry_date ≥ inspection_date
- Sinon OUTDATED + days_late

Rapports:
- EARLY / ON_TIME / LATE depuis due_date
- NOT_DELIVERED si aucune entrée delivery

Devoirs:
- week_thursday = jeudi calculé
- ON_TIME si posted_at ≤ jeudi
- LATE sinon
- NOT_POSTED si aucune date

Materials:
- Log simple (day, teacher, material)
- Group by counts

Settings:
- Édition listes (CSV) → config.py
- Vacations overrides
- Rapports tab (création + affectations)

Contributions: créer branche feature/* puis PR.
