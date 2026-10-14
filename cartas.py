"""
Cartas de apresentação — usa Ollama local para gerar texto personalizado.

Modelos disponíveis no teu PC:
  qwen3.5:0.8b      (texto geral)
  qwen2.5-coder:1.5b (código — não usado aqui)

Se o Ollama não estiver a correr, gera uma carta-base template.
"""

from __future__ import annotations

import json
import logging

import requests

import config

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "qwen3.5:0.8b"
TIMEOUT = 60


def _verificar_ollama() -> bool:
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _prompt_sistema() -> str:
    projetos = "\n".join(
        f"- {p['titulo']} ({p['stack']}): {p['descricao']}" for p in config.PROJETOS
    )
    experiencia = "\n".join(
        f"- {e['cargo']} na {e['empresa']} ({e['periodo']})" for e in config.EXPERIENCIA
    )
    habilidades = ", ".join(config.HABILIDADES)

    return f"""Você é um assistente que escreve cartas de apresentação curtas e profissionais para vagas de emprego no Brasil.

Candidato: {config.NOME}
Local: {config.LOCALIZACAO}
Email: {config.EMAIL}
LinkedIn: {config.LINKEDIN}
GitHub: {config.GITHUB}
Objetivo: {config.CARGO_DESEJADO}

Resumo: {config.RESUMO}

Habilidades: {habilidades}

Experiência:
{experiencia}

Projetos:
{projetos}

Escreva UMA carta de apresentação em português do Brasil, no máximo 150 palavras, em 2-3 parágrafos curtos.
Tom: profissional mas humano, direto, sem exagero.
Foque nas habilidades e projetos que combinam com a vaga descrita.
Termine com uma frase de chamada para entrevista.
NÃO invente experiências que não estejam no perfil acima."""


def gerar_carta(titulo_vaga: str, empresa: str, resumo_vaga: str) -> str:
    """
    Gera carta personalizada para a vaga. Usa Ollama se disponível,
    senão devolve carta template.
    """
    if not _verificar_ollama():
        logger.info("Ollama indisponível — a usar carta template.")
        return _carta_template(titulo_vaga, empresa)

    prompt = (
        f"{_prompt_sistema()}\n\n"
        f"Vaga: {titulo_vaga} na empresa {empresa}\n"
        f"Descrição da vaga (resumo): {resumo_vaga[:800]}\n\n"
        "Escreva agora a carta de apresentação:"
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 400},
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        texto = resp.json().get("response", "").strip()
        if texto:
            return texto
        logger.warning("Ollama devolveu texto vazio — a usar template.")
        return _carta_template(titulo_vaga, empresa)
    except requests.RequestException as exc:
        logger.warning("Erro Ollama (%s) — a usar template.", exc)
        return _carta_template(titulo_vaga, empresa)


def _carta_template(titulo: str, empresa: str) -> str:
    return (
        f"Prezados da {empresa},\n\n"
        f"Meu nome é {config.NOME} e escrevo para manifestar interesse na vaga "
        f"de {titulo}. Sou graduado em Direito, cursando Análise e Desenvolvimento "
        f"de Sistemas (Unifor, 2026), e atuo como Analista Júnior de Gestão de "
        f"Estoque na SB Farma, onde desenvolvo automações em Python e consultas "
        f"SQL avançadas (CTEs, subconsultas, joins relacionais).\n\n"
        f"Meu portfólio inclui uma API REST serverless com FastAPI e PostgreSQL, "
        f"uma aplicação full stack em React + Node.js com JWT, e ferramentas de "
        f"parsing de XML com Pandas. Busco aplicar essa combinação de visão de "
        f"negócios e técnica em uma oportunidade júnior, de preferência remota "
        f"ou híbrida em Fortaleza.\n\n"
        f"Disponível para conversar. Obrigado pela atenção.\n"
        f"{config.NOME} — {config.LINKEDIN} — {config.GITHUB}"
    )


def gerar_email_assunto(titulo: str, empresa: str) -> str:
    return f"Candidatura — {titulo} — {config.NOME}"
