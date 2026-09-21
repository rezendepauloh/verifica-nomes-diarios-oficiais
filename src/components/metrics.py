# -*- coding: utf-8 -*-
"""
Componente de Cards Métricos (Indicadores).
Utiliza a biblioteca reutilizável metric_cards para compatibilidade total com temas.
"""
from src.components.metric_cards import render_metric_cards

def render_metrics(occurrences):
    """Renderiza os cards métricos de Total, Pendentes e Lidos."""
    total_found = len(occurrences)
    pendentes = sum(1 for row in occurrences if row[6] == "Pendente")
    resolvidos = total_found - pendentes

    cards = [
        {
            "title": "Total Detectado",
            "value": total_found,
            "border_color": "#3b82f6"
        },
        {
            "title": "Alertas Pendentes",
            "value": pendentes,
            "border_color": "#f59e0b"
        },
        {
            "title": "Acompanhados / Lidos",
            "value": resolvidos,
            "border_color": "#10b981"
        }
    ]

    render_metric_cards(cards, cols=3)
