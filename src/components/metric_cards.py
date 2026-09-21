"""
Componente reutilizável para exibição de Cards KPI / Métricas no Streamlit.
Padroniza visualmente as métricas do sistema com suporte total a tema claro e escuro.
"""

from typing import Any, Dict, List, Optional, Union
import html
import textwrap
import streamlit as st


def render_metric_card(
    title: str,
    value: Any,
    border_color: str = "#3b82f6",
    value_color: Optional[str] = None,
    title_color: Optional[str] = None,
    subtitle: Optional[str] = None,
    extra_html: Optional[str] = None,
    text_align: str = "left",
) -> None:
    """
    Renderiza um card individual de métrica/KPI com visual padronizado.
    """
    style_align = f"text-align: {text_align};" if text_align != "left" else ""
    card_style = f'style="border-left-color: {border_color}; {style_align}"'.strip()

    val_style = f'style="color: {value_color};"' if value_color else ""
    tit_style = f'style="color: {title_color};"' if title_color else ""

    subtitle_html = (
        f' <span style="font-size: 0.9rem; opacity: 0.75; font-weight: normal;">{html.escape(str(subtitle))}</span>'
        if subtitle
        else ""
    )

    extra_content = extra_html.strip() if extra_html else ""

    html_content = textwrap.dedent(f"""<div class="metric-card" {card_style}>
<div class="metric-title" {tit_style}>{title}</div>
<div class="metric-value" {val_style}>{value}{subtitle_html}</div>
{extra_content}
</div>""").strip()
    st.markdown(html_content, unsafe_allow_html=True)


def render_metric_cards(
    cards: List[Dict[str, Any]],
    cols: Optional[Union[int, List[int], List[float]]] = None,
) -> None:
    """
    Renderiza múltiplos cards de métrica distribuídos em colunas st.columns.
    """
    if not cards:
        return

    num_cards = len(cards)
    col_layout = cols if cols is not None else num_cards

    columns = st.columns(col_layout)

    for idx, card in enumerate(cards):
        col_target = columns[idx % len(columns)]
        with col_target:
            render_metric_card(
                title=card.get("title", ""),
                value=card.get("value", ""),
                border_color=card.get("border_color", "#3b82f6"),
                value_color=card.get("value_color"),
                title_color=card.get("title_color"),
                subtitle=card.get("subtitle"),
                extra_html=card.get("extra_html"),
                text_align=card.get("text_align", "left"),
            )
