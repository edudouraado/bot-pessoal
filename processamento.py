"""
Módulo de Processamento e Score (Pandas)
========================================
Recebe a lista de dicionários do módulo de extração, converte-a num DataFrame
e aplica a lógica de Match Score:

* **+3 pontos** por cada termo encontrado: SQL, PostgreSQL, Python, FastAPI, React
* **+2 pontos** por cada termo encontrado: Dados, Automação, APIs
* **-10 pontos** por cada termo de exclusão: Sénior, Senior, Pleno,
  Especialista, Lead, Tech Lead

A comparação ignora maiúsculas/minúsculas e acentos (ex.: "Automação" ==
"automacao"). O DataFrame devolvido está limpo, sem duplicados, sem
pontuações negativas e ordenado decrescentemente por `score`.

Uso básico:
    from processamento import processar_vagas
    df = processar_vagas(lista_de_dict)
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

# --------------------------------------------------------------------------- #
# Definição das regras de scoring
# --------------------------------------------------------------------------- #

# (ponto por ocorrência, termo)
TERMOS_SCORE: list[tuple[int, str]] = [
    (+3, "SQL"),
    (+3, "PostgreSQL"),
    (+3, "Python"),
    (+3, "FastAPI"),
    (+3, "React"),
    (+2, "Dados"),
    (+2, "Automação"),
    (+2, "APIs"),
]

# Fator de exclusão: vagas séniores/plenas não devem aparecer.
TERMOS_EXCLUSAO: list[str] = [
    "Sénior",
    "Senior",
    "Pleno",
    "Especialista",
    "Lead",
    "Tech Lead",
]

PONTOS_EXCLUSAO = -10

COLUNAS_OBRIGATORIAS = ["titulo", "empresa", "url", "resumo"]

# Ordem de saída no DataFrame final (`data_publicacao` é preenchida pela
# extração; em dados externos pode ficar vazia).
COLUNAS_SAIDA = [
    "score",
    "termos",
    "titulo",
    "empresa",
    "localizacao",
    "data_publicacao",
    "url",
    "resumo",
]


# --------------------------------------------------------------------------- #
# Utilitários de texto
# --------------------------------------------------------------------------- #


def _normalizar(texto: str) -> str:
    """
    Minúsculas + remoção de acentos, para comparações robustas:
    "Automação" -> "automacao", "Sénior" -> "senior".
    """
    if not isinstance(texto, str):
        return ""
    sem_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem_acentos if unicodedata.category(c) != "Mn")


def _termo_encontrado(texto_normalizado: str, termo: str) -> bool:
    """
    Procura `termo` como palavra inteira no texto já normalizado.

    Usa limites de palavra (`\\b`) para evitar falsos positivos, EXCETO em
    termos que contêm não-alfanuméricos (ex.: "APIs" -> também casa "apis").
    """
    padrao = re.escape(_normalizar(termo))
    return re.search(rf"(?<!\w){padrao}(?!\w)", texto_normalizado) is not None


def calcular_score(resumo: str, titulo: str = "") -> tuple[int, list[str]]:
    """
    Calcula o Match Score de uma vaga somando os pontos de cada termo
    encontrado no título + resumo. Devolve `(score, termos_encontrados)`.

    Termos que normalizam para a mesma forma (ex.: "Sénior" == "Senior")
    são contados uma única vez; "Tech Lead" subsume "Lead".
    """
    texto = _normalizar(f"{titulo} {resumo}")
    score = 0
    encontrados: list[str] = []
    vistos: set[str] = set()  # termos normalizados já contabilizados

    for pontos, termo in TERMOS_SCORE:
        chave = _normalizar(termo)
        if chave in vistos:
            continue
        if _termo_encontrado(texto, termo):
            score += pontos
            encontrados.append(termo)
            vistos.add(chave)

    for termo in sorted(TERMOS_EXCLUSAO, key=len, reverse=True):
        chave = _normalizar(termo)
        if chave in vistos:
            continue
        if _termo_encontrado(texto, termo):
            score += PONTOS_EXCLUSAO
            encontrados.append(termo)
            vistos.add(chave)
            # "Tech Lead" subsume "Lead": evita dupla punição da mesma menção.
            if chave == "tech lead":
                vistos.add("lead")

    return score, encontrados



# --------------------------------------------------------------------------- #
# Pipeline principal
# --------------------------------------------------------------------------- #


def processar_vagas(
    lista_vagas: list[dict],
    incluir_negativos: bool = False,
) -> pd.DataFrame:
    """
    Converte a lista de dicionários da extração num DataFrame limpo e
    ordenado por `score` decrescente.

    Parâmetros
    ----------
    lista_vagas       : lista devolvida por `extracao.extrair_vagas()`.
    incluir_negativos : se True, mantém também as vagas com score < 0
                        (por omissão são omitidas, conforme especificação).

    Devolve
    -------
    pd.DataFrame com colunas: score, termos, titulo, empresa,
    data_publicacao, url, resumo.
    """
    if not lista_vagas:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df = pd.DataFrame(lista_vagas)

    # Garante a existência das colunas esperadas (DOM pode ter mudado).
    for coluna in COLUNAS_OBRIGATORIAS:
        if coluna not in df.columns:
            df[coluna] = ""
        df[coluna] = df[coluna].fillna("").astype(str).str.strip()

    # Colunas opcionais vindas da extração (local e data de publicação).
    for coluna_opcional in ("localizacao", "data_publicacao"):
        if coluna_opcional not in df.columns:
            df[coluna_opcional] = ""
        else:
            df[coluna_opcional] = df[coluna_opcional].fillna("").astype(str)

    # Remove linhas sem título nem URL e duplicados pela URL normalizada.
    df = df[(df["titulo"] != "") | (df["url"] != "")]
    df["_chave"] = (
        df["url"].str.split("?").str[0].str.rstrip("/").str.lower()
    )
    df = df[df["_chave"] != ""]
    df = df.drop_duplicates(subset="_chave", keep="first")

    # Score por linha (com guard contra falhas inesperadas).
    scores: list[int] = []
    termos: list[str] = []
    for _, linha in df.iterrows():
        try:
            pontos, encontrados = calcular_score(
                resumo=linha["resumo"], titulo=linha["titulo"]
            )
        except Exception:  # noqa: BLE001 - nunca quebrar o pipeline
            pontos, encontrados = 0, []
        scores.append(pontos)
        termos.append(", ".join(encontrados))

    df["score"] = scores
    df["termos"] = termos

    # Omissão de pontuações negativas (fator de exclusão).
    if not incluir_negativos:
        df = df[df["score"] >= 0]

    df = df.sort_values(by="score", ascending=False, kind="stable")
    df = df.drop(columns="_chave").reset_index(drop=True)

    return df[COLUNAS_SAIDA]
