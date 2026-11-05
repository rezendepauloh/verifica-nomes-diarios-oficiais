# -*- coding: utf-8 -*-
"""
Extrator complementar e inteligente via Gemini API.
Utilizado para refinar ou complementar cronogramas e tópicos complexos de editais.
Usa chamadas HTTP diretas com a chave GEMINI_API_KEY do .env.
"""
import json
import requests
from typing import List, Dict, Any
from src.config import GEMINI_API_KEY
from src.logger import logger

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

def is_gemini_available() -> bool:
    """Verifica se a chave da API do Gemini está configurada."""
    return bool(GEMINI_API_KEY and len(GEMINI_API_KEY.strip()) > 10)

def call_gemini_json(prompt: str) -> Dict[str, Any]:
    """Executa uma chamada ao Gemini solicitando retorno estrito em formato JSON."""
    if not is_gemini_available():
        raise ValueError("Chave GEMINI_API_KEY não configurada no arquivo .env.")

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Nenhuma resposta retornada pela API do Gemini.")

    text_resp = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
    return json.loads(text_resp)

def extract_cronograma_with_ai(sample_text: str) -> List[Dict[str, Any]]:
    """Extrai ou refina datas do cronograma a partir de um trecho de texto do edital."""
    prompt = f"""
Você é um especialista em editais de concursos públicos brasileiros.
Analise o texto a seguir extraído de um edital e extraia as principais datas e eventos do cronograma.
Retorne um JSON no seguinte formato:
{{
  "cronograma": [
    {{
      "evento": "Nome da Atividade/Evento",
      "data_inicio": "DD/MM/AAAA",
      "data_fim": "DD/MM/AAAA (ou vazio se for data única)",
      "data_limite": "DD/MM/AAAA (data final relevante)",
      "status": "Previsto",
      "observacao": "Detalhe adicional relevante"
    }}
  ]
}}

Texto do edital:
\"\"\"
{sample_text[:12000]}
\"\"\"
"""
    try:
        res = call_gemini_json(prompt)
        items = res.get("cronograma", [])
        return items
    except Exception as e:
        logger.error(f"Erro na extração de cronograma via Gemini: {e}")
        return []

def extract_verticalizado_with_ai(sample_text: str, cargo: str = "") -> List[Dict[str, Any]]:
    """Estrutura o conteúdo programático do edital em disciplinas e tópicos claros."""
    prompt = f"""
Você é um especialista em preparação para concursos públicos.
Analise o conteúdo programático extraído do edital a seguir (foco no cargo: '{cargo or 'Geral'}')
e estruture um Edital Verticalizado detalhado.
Separe cada assunto em tópicos individuais de estudo (ex: Crase, Concordância Verbal, Regência Nominal, etc).

Retorne um JSON no seguinte formato:
{{
  "verticalizado": [
    {{
      "disciplina": "Nome da Disciplina (Ex: Língua Portuguesa)",
      "topico": "Assunto ou tópico específico a ser estudado",
      "subtopico": "Subtópico se houver",
      "peso": 1.0,
      "questoes_previstas": 0
    }}
  ]
}}

Texto do conteúdo programático:
\"\"\"
{sample_text[:15000]}
\"\"\"
"""
    try:
        res = call_gemini_json(prompt)
        items = res.get("verticalizado", [])
        return items
    except Exception as e:
        logger.error(f"Erro na extração de edital verticalizado via Gemini: {e}")
        return []

