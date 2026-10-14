"""
Greenhouse — API pública de boards (usada por Nubank, iFood, Creditas, etc).
Documentação: https://developers.greenhouse.io/job-board.html
Uso livre para leitura de vagas publicadas.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://boards-api.greenhouse.io/v1/boards"
USER_AGENT = "bot-pessoal-jobsearch/1.0 (pessoal; contato: edusalesoliveira@hotmail.com)"
TIMEOUT = 15

EMPRESAS = [
    "quintoandar", "stone", "nubank", "wolf", "movile", "arco",
    "gympass", "loggi", "rappi", "hotmart", "sympla",
    "ebanx", "neon", "unico", "cloudwalk", "cielo", "pagseguro",
    "symphony", "containerteam", "serasaexperian",
]

TERMS_NIVEL = [
    "junior", "júnior", "entry", "graduate", "trainee", "estágio", "estagio", "intern",
]

TERMS_TECH = [
    "desenvolvedor", "desenvolvedora", "programador", "analista de dados",
    "python", "node", "react", "javascript", "typescript",
    "sql", "postgres", "fullstack", "full stack", "backend", "frontend",
    "engenheiro de software", "software engineer",
]

TERMS_EN = TERMS_NIVEL + TERMS_TECH

TERMS_EXCLUSAO = ["senior", "sênior", "staff", "lead", "principal", "manager", "director"]


def _limpar_html(texto: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", texto or "")
    return " ".join(html.unescape(sem_tags).split())


def _match(texto: str, termos: list[str]) -> bool:
    baixo = texto.lower()
    return any(t in baixo for t in termos)


def _match_vaga(texto: str) -> bool:
    baixo = texto.lower()
    tem_nivel = any(t in baixo for t in TERMS_NIVEL)
    tem_tech = any(t in baixo for t in TERMS_TECH)
    return tem_nivel and tem_tech


def _extrair_salario(texto: str) -> tuple[Optional[float], Optional[float]]:
    padrao = re.search(
        r"(?:R\$|BRL)\s*([\d.,]+)\s*(?:-|a|até)\s*(?:R\$|BRL)?\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    if not padrao:
        return None, None
    try:
        smin = float(padrao.group(1).replace(".", "").replace(",", "."))
        smax = float(padrao.group(2).replace(".", "").replace(",", "."))
        return smin, smax
    except ValueError:
        return None, None


def buscar_greenhouse(
    empresas: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    limite: int = 50,
) -> list[dict]:
    """
    Busca vagas em boards Greenhouse de empresas brasileiras.
    """
    empresas = empresas or EMPRESAS
    terms = keywords or TERMS_EN
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    resultados = []
    for empresa in empresas:
        if len(resultados) >= limite:
            break
        url = f"{API_BASE}/{empresa}/jobs?content=true"
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.debug("Greenhouse %s falhou: %s", empresa, exc)
            continue

        jobs = data.get("jobs", [])
        for job in jobs:
            titulo = job.get("title", "") or ""
            location = (job.get("location") or {}).get("name", "") or ""
            content = _limpar_html(job.get("content", ""))
            absolute_url = job.get("absolute_url", "")
            updated = job.get("updated_at", "") or ""

            texto = f"{titulo} {location} {content}".lower()

            if not _match_vaga(texto):
                continue
            if _match(titulo, TERMS_EXCLUSAO):
                continue

            smin, smax = _extrair_salario(content)

            resultados.append({
                "titulo": titulo or "(sem título)",
                "empresa": empresa.replace("-", " ").title(),
                "localizacao": location or "Não informado",
                "url": absolute_url,
                "resumo": content[:600],
                "fonte": "Greenhouse",
                "data_publicacao": updated[:10] if updated else "",
                "salario_min": smin,
                "salario_max": smax,
                "tags": "",
            })

            if len(resultados) >= limite:
                break

    logger.info("Greenhouse: %s vagas.", len(resultados))
    return resultados
