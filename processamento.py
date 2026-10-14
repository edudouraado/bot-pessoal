"""
Processamento e Score — perfil Eduardo (fullstack + dados, júnior).

Filtros OBRIGATÓRIOS (antes do score):
  1. Pelo menos 1 termo de nível júnior (Junior, Trainee, Entry, Estágio…)
  2. Pelo menos 1 termo de tech/dev/dados (Python, SQL, React, Desenvolvedor…)

Depois aplica score e penaliza sênior/pleno/não-tech.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

import config

TERMOS_SCORE: list[tuple[int, str]] = [
    (+4, "Python"), (+4, "FastAPI"), (+4, "Node.js"), (+4, "React"),
    (+4, "SQL"), (+4, "PostgreSQL"), (+4, "JavaScript"), (+4, "TypeScript"),
    (+3, "Desenvolvedor"), (+3, "Analista de Dados"), (+3, "Fullstack"),
    (+3, "Backend"), (+3, "Frontend"), (+3, "Software Engineer"),
    (+2, "Dados"), (+2, "Automação"), (+2, "APIs"), (+2, "Pandas"),
    (+2, "Express"), (+2, "Tailwind"),
    (+2, "Remoto"), (+2, "Híbrido"), (+3, "Fortaleza"), (+3, "Ceará"),
]

# Filtro duro 1: a vaga precisa ter PELO MENOS UM destes (senão, descarta)
TERMOS_NIVEL_JUNIOR: list[str] = [
    "Junior", "Júnior", "Entry level", "Entry", "Trainee",
    "Estágio", "Estagio", "Intern", "Graduate", "Assistente",
]

# Filtro duro 2: a vaga precisa ter PELO MENOS UM destes (senão, descarta)
TERMOS_CORE_DEV: list[str] = [
    "Python", "FastAPI", "Node.js", "React", "SQL", "PostgreSQL",
    "JavaScript", "TypeScript", "Desenvolvedor", "Desenvolvedora",
    "Programador", "Programadora", "Backend", "Frontend", "Fullstack",
    "Full Stack", "Software Engineer", "Analista de Dados", "Data Analyst",
    "Engenheiro de Dados", "Django", "Flask", "Java", "Kotlin", "C#",
    "Vue", "Angular", "Docker", "API", "Automação", "Pandas",
]

# Filtro duro 3: se aparecer no TÍTULO, descarta a vaga inteira
EXCLUSAO_TITULO: list[str] = [
    "Senior", "Sénior", "Sênior", "Staff", "Principal", "Lead",
    "Tech Lead", "Manager", "Director", "Especialista", "Pleno", "Plena",
    "III", "IV", "Sales", "Vendas", "Comercial", "Customer Success",
    "Crypto", "Trading", "Recrutamento", "Consultant", "Representative",
    "Riscos", "Liquidez", "Crédito", "Credito", "Data Annotation",
    "Annotator", "Digital Assets", "Danish", "Speaking", "Localization",
    "Translator", "DevOps", "SRE", "Architect", "Architect",
]

# Pontuação de exclusão no resumo (não descarta, mas zera o score)
TERMOS_EXCLUSAO_RESUMO: list[str] = [
    "Senior", "Sénior", "Sênior", "Staff", "Principal",
    "Lead", "Tech Lead", "Manager", "Director", "Especialista",
    "Pleno", "Plena", "Sales", "Vendas", "Comercial",
    "Customer Success", "Suporte", "Crypto", "Trading",
]

PONTOS_EXCLUSAO = -20

COLUNAS_OBRIGATORIAS = ["titulo", "empresa", "url", "resumo"]

COLUNAS_SAIDA = [
    "score", "termos", "titulo", "empresa", "localizacao",
    "fonte", "salario_min", "salario_max", "data_publicacao", "url", "resumo",
]


def _normalizar(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    sem_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem_acentos if unicodedata.category(c) != "Mn")


def _termo_encontrado(texto_normalizado: str, termo: str) -> bool:
    padrao = re.escape(_normalizar(termo))
    return re.search(rf"(?<!\w){padrao}(?!\w)", texto_normalizado) is not None


def _tem_termo(texto_norm: str, termos: list[str]) -> bool:
    return any(_termo_encontrado(texto_norm, t) for t in termos)


def _excluido_por_titulo(titulo: str) -> bool:
    t = _normalizar(titulo)
    return any(_termo_encontrado(t, e) for e in EXCLUSAO_TITULO)


def vaga_elegivel(titulo: str, resumo: str) -> tuple[bool, str]:
    """
    Verifica filtros duros. Devolve (elegivel, motivo).
    """
    texto = _normalizar(f"{titulo} {resumo}")
    titulo_norm = _normalizar(titulo)

    if _excluido_por_titulo(titulo):
        return False, "titulo_excluido"

    if not _tem_termo(titulo_norm, TERMOS_NIVEL_JUNIOR):
        if not _tem_termo(texto, TERMOS_NIVEL_JUNIOR):
            return False, "sem_nivel_junior"

    if not _tem_termo(texto, TERMOS_CORE_DEV):
        return False, "sem_tech_core"

    return True, ""


def calcular_score(resumo: str, titulo: str = "") -> tuple[int, list[str]]:
    texto = _normalizar(f"{titulo} {resumo}")
    score = 0
    encontrados: list[str] = []
    vistos: set[str] = set()

    for pontos, termo in TERMOS_SCORE:
        chave = _normalizar(termo)
        if chave in vistos:
            continue
        if _termo_encontrado(texto, termo):
            score += pontos
            encontrados.append(termo)
            vistos.add(chave)

    for termo in sorted(TERMOS_EXCLUSAO_RESUMO, key=len, reverse=True):
        chave = _normalizar(termo)
        if chave in vistos:
            continue
        if _termo_encontrado(texto, termo):
            score += PONTOS_EXCLUSAO
            encontrados.append(termo)
            vistos.add(chave)
            if chave in ("tech lead", "senior", "sênior", "sénior"):
                vistos.add("lead")

    return score, encontrados


def _passa_filtro_localizacao(localizacao: str, modalidades: list[str]) -> bool:
    loc = _normalizar(localizacao)
    mods = [_normalizar(m) for m in modalidades]
    if not mods:
        return True
    if "remoto" in mods and any(t in loc for t in ("remoto", "remote", "brasil", "anywhere", "home office", "homeoffice")):
        return True
    if "hibrido" in mods and any(t in loc for t in ("hibrido", "hybrid")):
        return True
    if "fortaleza" in mods and any(t in loc for t in ("fortaleza", "ceara", "ce ")):
        return True
    return False


def _passa_filtro_salario(salario_min: float | None, salario_minimo: float | None) -> bool:
    if not salario_minimo:
        return True
    if salario_min is None:
        return True
    return salario_min >= salario_minimo


def processar_vagas(
    lista_vagas: list[dict],
    incluir_negativos: bool = False,
    modalidades: list[str] | None = None,
    salario_minimo: float | None = None,
) -> pd.DataFrame:
    if not lista_vagas:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df = pd.DataFrame(lista_vagas)

    for coluna in COLUNAS_OBRIGATORIAS:
        if coluna not in df.columns:
            df[coluna] = ""
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()

    for coluna_opcional in ("localizacao", "data_publicacao", "fonte", "tags"):
        if coluna_opcional not in df.columns:
            df[coluna_opcional] = ""
        else:
            df[coluna_opcional] = df[coluna_opcional].fillna("").astype(str)

    for coluna_salario in ("salario_min", "salario_max"):
        if coluna_salario not in df.columns:
            df[coluna_salario] = None
        else:
            df[coluna_salario] = pd.to_numeric(df[coluna_salario], errors="coerce")

    df = df[(df["titulo"] != "") | (df["url"] != "")]
    df["_chave"] = (
        df["url"].str.split("?").str[0].str.rstrip("/").str.lower()
    )
    df = df[df["_chave"] != ""]
    df = df.drop_duplicates(subset="_chave", keep="first")

    elegiveis = []
    motivos = []
    for _, linha in df.iterrows():
        ok, motivo = vaga_elegivel(linha["titulo"], linha["resumo"])
        elegiveis.append(ok)
        motivos.append(motivo)
    df["_elegivel"] = elegiveis
    df["_motivo"] = motivos

    total_brutas = len(df)
    df = df[df["_elegivel"]].copy()

    if df.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    scores: list[int] = []
    termos: list[str] = []
    for _, linha in df.iterrows():
        try:
            pontos, encontrados = calcular_score(
                resumo=linha["resumo"], titulo=linha["titulo"]
            )
        except Exception:
            pontos, encontrados = 0, []
        scores.append(pontos)
        termos.append(", ".join(encontrados))

    df["score"] = scores
    df["termos"] = termos

    if modalidades:
        df = df[df["localizacao"].apply(lambda x: _passa_filtro_localizacao(x, modalidades))]
    if salario_minimo:
        df = df[df["salario_min"].apply(lambda x: _passa_filtro_salario(x, salario_minimo))]

    if not incluir_negativos:
        df = df[df["score"] >= 0]

    df = df.sort_values(by="score", ascending=False, kind="stable")
    df = df.drop(columns=["_chave", "_elegivel", "_motivo"]).reset_index(drop=True)

    return df[COLUNAS_SAIDA]
