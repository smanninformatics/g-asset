# i18n.py
"""Lightweight language detection and UI string translations (en/es/fr/pt)."""

_MARKERS = {
    "es": ["parcialmente", "sí", "herramienta", "evaluación", "seleccione",
           "administración de antibióticos", "no aplica"],
    "fr": ["partiellement", "oui", "évaluation", "sélectionnez",
           "gestion des antibiotiques", "établissement"],
    "pt": ["parcialmente implementado", "não", "avaliação", "selecione",
           "gestão de antibióticos", "instalação"],
}

def detect_language(text: str) -> str:
    t = (text or "").lower()
    scores = {lg: sum(t.count(m) for m in ms) for lg, ms in _MARKERS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else "en"


STRINGS = {
    "en": {
        "app_title": "G-ASET Scoring & Improvement Planner",
        "upload": "Upload completed G-ASET file(s) (PDF or CSV)",
        "tab_scores": "Scores", "tab_trends": "Trends", "tab_plan": "Action Plan",
        "overall": "Overall Score", "domain": "Domain", "earned": "Earned Points",
        "max": "Max Points", "pct": "Percent", "item": "Item", "question": "Question",
        "points": "Points", "select_assessment": "Select assessment",
        "facility": "Facility", "date": "Completion date",
        "no_files": "Upload one or more completed G-ASET assessments to begin.",
        "trend_hint": "Upload two or more assessments for the same facility to view trends over time.",
        "gap": "Not implemented — priority action", "partial_gap": "Partially implemented — strengthen",
        "recommendation": "Recommended action", "priority": "Priority",
        "plan_intro": "Actions below are generated from items scoring below full points, ordered by configurable priority.",
        "internal_use": "Scores are for internal use only and are not intended for comparison between facilities.",
        "download_plan": "Download action plan (CSV)",
        "field_inspector": "PDF field inspector (for SME field-map configuration)",
    },
    "es": {
        "app_title": "G-ASET: Puntuación y Plan de Mejora",
        "upload": "Cargue archivo(s) G-ASET completado(s) (PDF o CSV)",
        "tab_scores": "Puntuaciones", "tab_trends": "Tendencias", "tab_plan": "Plan de Acción",
        "overall": "Puntuación Global", "domain": "Dominio", "earned": "Puntos Obtenidos",
        "max": "Puntos Máximos", "pct": "Porcentaje", "item": "Ítem", "question": "Pregunta",
        "points": "Puntos", "select_assessment": "Seleccione la evaluación",
        "facility": "Establecimiento", "date": "Fecha de finalización",
        "no_files": "Cargue una o más evaluaciones G-ASET completadas para comenzar.",
        "trend_hint": "Cargue dos o más evaluaciones del mismo establecimiento para ver tendencias.",
        "gap": "No implementado — acción prioritaria", "partial_gap": "Parcialmente implementado — fortalecer",
        "recommendation": "Acción recomendada", "priority": "Prioridad",
        "plan_intro": "Las acciones se generan a partir de ítems con puntuación incompleta, ordenadas por prioridad configurable.",
        "internal_use": "Las puntuaciones son solo para uso interno; no deben usarse para comparar establecimientos.",
        "download_plan": "Descargar plan de acción (CSV)",
        "field_inspector": "Inspector de campos del PDF (configuración del mapa de campos)",
    },
    "fr": {
        "app_title": "G-ASET : Notation et Plan d'Amélioration",
        "upload": "Téléversez le(s) fichier(s) G-ASET complété(s) (PDF ou CSV)",
        "tab_scores": "Scores", "tab_trends": "Tendances", "tab_plan": "Plan d'Action",
        "overall": "Score Global", "domain": "Domaine", "earned": "Points Obtenus",
        "max": "Points Max", "pct": "Pourcentage", "item": "Item", "question": "Question",
        "points": "Points", "select_assessment": "Sélectionnez l'évaluation",
        "facility": "Établissement", "date": "Date d'achèvement",
        "no_files": "Téléversez une ou plusieurs évaluations G-ASET complétées pour commencer.",
        "trend_hint": "Téléversez au moins deux évaluations du même établissement pour voir les tendances.",
        "gap": "Non mis en œuvre — action prioritaire", "partial_gap": "Partiellement mis en œuvre — renforcer",
        "recommendation": "Action recommandée", "priority": "Priorité",
        "plan_intro": "Les actions sont générées à partir des items sous le score maximal, classées par priorité configurable.",
        "internal_use": "Les scores sont à usage interne uniquement.",
        "download_plan": "Télécharger le plan d'action (CSV)",
        "field_inspector": "Inspecteur des champs PDF (configuration du mappage)",
    },
    "pt": {
        "app_title": "G-ASET: Pontuação e Plano de Melhoria",
        "upload": "Carregue arquivo(s) G-ASET preenchido(s) (PDF ou CSV)",
        "tab_scores": "Pontuações", "tab_trends": "Tendências", "tab_plan": "Plano de Ação",
        "overall": "Pontuação Geral", "domain": "Domínio", "earned": "Pontos Obtidos",
        "max": "Pontos Máximos", "pct": "Percentual", "item": "Item", "question": "Pergunta",
        "points": "Pontos", "select_assessment": "Selecione a avaliação",
        "facility": "Estabelecimento", "date": "Data de conclusão",
        "no_files": "Carregue uma ou mais avaliações G-ASET preenchidas para começar.",
        "trend_hint": "Carregue duas ou mais avaliações do mesmo estabelecimento para ver tendências.",
        "gap": "Não implementado — ação prioritária", "partial_gap": "Parcialmente implementado — fortalecer",
        "recommendation": "Ação recomendada", "priority": "Prioridade",
        "plan_intro": "As ações são geradas a partir de itens com pontuação abaixo do máximo, ordenadas por prioridade configurável.",
        "internal_use": "As pontuações são apenas para uso interno.",
        "download_plan": "Baixar plano de ação (CSV)",
        "field_inspector": "Inspetor de campos do PDF (configuração do mapa de campos)",
    },
}

def t(lang: str, key: str) -> str:
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))