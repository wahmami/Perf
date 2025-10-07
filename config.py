subjects = ["Arabic", "French", "English", "EPS", "SVT", "Maths", "Quran"]
classes = ["PS", "MS", "GS", "CP", "CE1", "CE2", "CM1", "CM2", "CE6"]
level_options = [f"{i}{s}" for s in "ABCDE" for i in range(1, 7)]  # ['1A', ..., '6E']

modules = ["Français", "Arabic", "Math", "English"]

submodules = {
    "Français": [
        "Production écrite", "Lexique", "Grammaire", "Conjugaison", "Orthographe",
        "Dictée", "Poésie", "Écriture", "Copie", "Projet de classe", "Graphisme"
    ],
    "Arabic": [
        "التعبير الكتابي", "الإملاء", "الخط", "مشروع الوحدة", "التطبيقات الكتابية",
        "التراكيب", "الصرف والتحويل", "التواصل الشفوي", "الشكل", "فهم المقروء", "إنشاء"
    ],
    "Math": [],
    "English": []
}

materials = ["Feutre bleu", "Feutre  vert", "Feutre noir", "Feutre rouge", "Brosse"]