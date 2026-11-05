# -*- coding: utf-8 -*-
"""
Módulo de parsing e manipulação de arquivos PDF para editais.
Extrai texto por página, tabelas e metadados usando pdfplumber.
"""
from pathlib import Path
from typing import Dict, List, Any, Optional
import pdfplumber
from src.logger import logger
from src.config import ROOT_DIR, EDITAIS_DIR

def resolve_pdf_path(path_str: str) -> Optional[Path]:
    """Resolve o arquivo PDF lidando com caminhos relativos e absolutos de containers ou host, inclusive em subpastas."""
    if not path_str:
        return None
    p = Path(path_str)
    if p.exists():
        return p
    # Tenta resolver relativo à raiz do projeto
    rel_p = ROOT_DIR / path_str
    if rel_p.exists():
        return rel_p
    # Tenta encontrar na pasta raiz de editais
    edital_p = EDITAIS_DIR / p.name
    if edital_p.exists():
        return edital_p
    # Busca recursiva em subpastas de uploads/editais/
    try:
        matches = list(EDITAIS_DIR.glob(f"**/{p.name}"))
        if matches:
            return matches[0]
    except Exception:
        pass
    return None

def inspect_pdf(pdf_path: str) -> Dict[str, Any]:
    """Retorna metadados básicos de um PDF (total de páginas, tamanho, se é legível)."""
    p = resolve_pdf_path(pdf_path)
    if not p or not p.exists():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")
    
    file_size_mb = p.stat().st_size / (1024 * 1024)
    with pdfplumber.open(str(p)) as pdf:
        total_pages = len(pdf.pages)
        first_page_text = pdf.pages[0].extract_text() or "" if total_pages > 0 else ""
        
    return {
        "file_name": p.name,
        "file_path": str(p),
        "file_size_mb": round(file_size_mb, 2),
        "total_pages": total_pages,
        "has_text": len(first_page_text.strip()) > 50,
        "preview": first_page_text[:400]
    }

def extract_full_text_by_pages(pdf_path: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Extrai texto e tabelas página a página do PDF resolvendo caminhos Docker/Host."""
    results = []
    p = resolve_pdf_path(pdf_path)
    if not p or not p.exists():
        logger.error(f"Arquivo PDF não encontrado após resolução: {pdf_path}")
        return results

    try:
        with pdfplumber.open(str(p)) as pdf:
            pages_to_process = pdf.pages[:max_pages] if max_pages else pdf.pages
            for i, page in enumerate(pages_to_process):
                page_text = page.extract_text() or ""
                tables = page.extract_tables() or []
                results.append({
                    "page_number": i + 1,
                    "text": page_text,
                    "tables": tables
                })
    except Exception as e:
        logger.error(f"Erro ao extrair páginas do PDF {pdf_path}: {e}")
        
    return results

