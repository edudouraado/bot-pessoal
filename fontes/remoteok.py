"""
Remote OK — API pública e gratuita.
Documentação: https://remoteok.com/api
Termos: uso livre com User-Agent identificado. Não é scraping.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"
USER_AGENT = "bot-pessoal-jobsearch/1.0 (pessoal; contato: edusalesoliveira@hotmail.com)"
TIMEOUT = 15

TERMS_EN = [
    "junior", "entry", "graduate", "trainee", "intern",
    "python", "node", "react", "javascript", "typescript",
    "sql", "postgres", "fullstack", "full stack", "backend", "frontend",
    "data", "analyst",
]

TERMS_EXCLUSAO = ["senior", "sênior", "staff", "lead", "principal", "manager", "director"]


def _extrair_salario(item: dict) -> tuple[Optional[float], Optional[float]]:
    salary_min = item.get("salary_min")
    salary_max = item.get("salary_max")
    try:
        smin = float(salary_min) if salary_min else None
        smax = float(salary_max) if salary_max else None
    except (TypeError, ValueError):
        smin, smax = None, None
    return smin, smax


def _texto_match(texto: str, termos: list[str]) -> bool:
    baixo = texto.lower()
    return any(t in baixo for t in termos)


def buscar_remoteok(
    keywords: Optional[list[str]] = None,
    limite: int = 30,
) -> list[dict]:
    """
    Busca vagas remotas na API do Remote OK.
    Retorna lista de dicts no padrão do projeto:
    titulo, empresa, localizacao, url, resumo, fonte, data_publicacao, salario_min, salario_max
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        resp = requests.get(API_URL, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Remote OK falhou: %s", exc)
        return []

    data = resp.json()
    if not isinstance(data, list):
        logger.warning("Remote OK retornou formato inesperado.")
        return []

    resultados = []
    for item in data:
        if not isinstance(item, dict) or item.get("legal"):
            continue

        position = item.get("position", "") or ""
        company = item.get("company", "") or ""
        description = (item.get("description", "") or "")[:600]
        tags = item.get("tags") or []
        url_raw = item.get("url") or ""
        date = item.get("date", "") or ""
        smin, smax = _extrair_salario(item)
        location = item.get("location") or "Remote"

        texto_completo = f"{position} {company} {description} {' '.join(tags)}".lower()

        if terms := keywords or TERMS_EN:
            if not _texto_match(texto_completo, terms):
                continue

        if _texto_match(position, TERMS_EXCLUSAO):
            continue

        url = url_raw if url_raw.startswith("http") else f"https://remoteok.com/l/{item.get('id', '')}"

        resultados.append({
            "titulo": position or "(sem título)",
            "empresa": company or "(sem empresa)",
            "localizacao": location,
            "url": url,
            "resumo": " ".join(description.split())[:600],
            "fonte": "Remote OK",
            "data_publicacao": date[:10] if date else "",
            "salario_min": smin,
            "salario_max": smax,
            "tags": ", ".join(tags),
        })

        if len(resultados) >= limite:
            break

    logger.info("Remote OK: %s vagas.", len(resultados))
    return resultados
