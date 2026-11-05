# -*- coding: utf-8 -*-
"""
Pacote de manipulação e extração de editais de concurso.
"""
from .pdf_parser import inspect_pdf, extract_full_text_by_pages
from .extractor_local import (
    extract_cronograma_local,
    extract_verticalizado_local,
    discover_cargos_in_pdf
)
from .extractor_ai import (
    is_gemini_available,
    extract_cronograma_with_ai,
    extract_verticalizado_with_ai
)
from .notifications import check_and_notify_cronograma_deadlines

__all__ = [
    "inspect_pdf",
    "extract_full_text_by_pages",
    "extract_cronograma_local",
    "extract_verticalizado_local",
    "discover_cargos_in_pdf",
    "is_gemini_available",
    "extract_cronograma_with_ai",
    "extract_verticalizado_with_ai",
    "check_and_notify_cronograma_deadlines"
]
