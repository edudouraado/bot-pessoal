"""
Módulo de Extração
==================
Extrai vagas de emprego da pesquisa **pública** do LinkedIn (sem login) usando
Playwright. Executa várias consultas booleanas (cargos em português, stack
técnica e cargos em inglês), filtra vagas **remotas no Brasil** e devolve uma
lista de dicionários:

    [{"titulo": str, "empresa": str, "url": str, "resumo": str}, ...]

Uso básico:
    from extracao import extrair_vagas
    vagas = extrair_vagas(max_vagas=25)

Notas de robustez (anti-bloqueio e mudanças de DOM):
* Todos os seletores CSS têm fallbacks (o DOM do LinkedIn muda com frequência).
* Esperas explícitas + `time.sleep` com pausas aleatórias entre ações.
* Bloco try/except por cartão: uma vaga problemática não aborta a execução.
* Se o LinkedIn devolver 403/429/999 é levantada `ErroExtracao` com mensagem
  clara (provável bloqueio anti-bot).

Execução standalone:  python extracao.py 10
"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
import urllib.parse
from datetime import date, datetime
from typing import Optional, Sequence

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Configuração da pesquisa
# --------------------------------------------------------------------------- #

URL_PESQUISA_BASE = "https://www.linkedin.com/jobs/search"

# geoId oficial, obtido pelo typeahead do próprio LinkedIn (sugestão "Brasil").
# IMPORTANTE: só o texto em `location` é IGNORADO pelo LinkedIn (ele cai na
# localização por defeito do IP) — o geoId é obrigatório para filtrar país.
GEOS: dict[str, str] = {"Brasil": "106057199"}

def montar_query(*grupos: Sequence[str]) -> str:
    """
    Combina grupos de termos numa query booleana do LinkedIn:
    cada grupo vira `("termo A" OR "termo B")` e os grupos são unidos por AND.
    Grupos vazios são ignorados.

    Ex.: montar_query(["Python", "React"], ["Júnior"]) ->
         `("Python" OR "React") AND ("Júnior")`
    """
    partes = [
        "(" + " OR ".join(f'"{termo}"' for termo in grupo) + ")"
        for grupo in grupos
        if grupo
    ]
    return " AND ".join(partes)


# --- Termos da pesquisa -----------------------------------------------------
# Edite estas listas para alargar ou restringir a procura.
TERMOS_STACK = [
    "Python",
    "SQL",
    "PostgreSQL",
    "React",
    "JavaScript",
    "TypeScript",
    "FastAPI",
]

# Cargos em português (PRIORIDADE — mercado brasileiro).
TERMOS_CARGOS_PT = [
    "Desenvolvedor",
    "Desenvolvedora",
    "Programador",
    "Programadora",
    "Dev",
]

# Cargos em inglês (empresas brasileiras que publicam títulos em inglês).
TERMOS_CARGOS_EN = [
    "Developer",
    "Software Engineer",
    "Fullstack",
    "Full Stack",
    "Frontend",
    "Backend",
]

TERMOS_NIVEL = ["Júnior", "Junior", "Entry level", "Graduate", "Trainee"]

# --- Consultas executadas (por ordem de prioridade) -------------------------
# 1. Cargos em português AND nível júnior.
# 2. Stack técnica AND nível júnior.
# 3. Cargos em inglês AND nível júnior.
# Os resultados são unidos e deduplicados por URL. A cota de `max_vagas`
# divide-se igualmente por consulta, por isso a ORDEM importa: a consulta
# em português tem prioridade e preenche a cota primeiro.
QUERY_CARGOS_PT = montar_query(TERMOS_CARGOS_PT, TERMOS_NIVEL)
QUERY_BOOLEANA = montar_query(TERMOS_STACK, TERMOS_NIVEL)
QUERY_CARGOS_EN = montar_query(TERMOS_CARGOS_EN, TERMOS_NIVEL)
CONSULTAS: list[str] = [QUERY_CARGOS_PT, QUERY_BOOLEANA, QUERY_CARGOS_EN]

# User-Agent realista (o Playwright por omissão expõe "HeadlessChrome").
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# --------------------------------------------------------------------------- #
# Seletores CSS (ordenados do mais específico para o mais genérico)
# --------------------------------------------------------------------------- #

SELETORES_CARTAO = [
    "li.jobs-search-results__list-item",
    "ul.jobs-search__results-list > li",
    "li.jobs-search__organic-job",
    "div.jobs-search-results-list li[data-occludable-job-id]",
    "div.job-card-container",
    "div.jobs-search-results-list li",
]

SELETORES_TITULO = [
    "a.job-card-container__link",
    ".job-card-list__title",
    "h3.base-search-card__title",
    ".job-search-card__title",
    "h3",
]

SELETORES_EMPRESA = [
    ".job-card-container__company-name",
    ".hidden-nested-link",
    "h4.base-search-card__subtitle",
    ".job-search-card__subtitle",
    "h4",
]

SELETORES_LINK = [
    "a.job-card-container__link",
    "a.base-card__full-link",
    "a[href*='/jobs/view/']",
]

# Resumo curto que o próprio cartão pode expor (quando existe, evita cliques).
SELETORES_RESUMO = [
    ".job-card-container__description",
    ".job-card-list__description",
    ".artdeco-entity-snippet__description",
    ".job-search-card__snippet",
    "[data-test-job-card-description]",
]

# Descrição completa no painel de detalhe (após clicar no cartão).
SELETORES_DESCRICAO = [
    ".show-more-less-html__markup",
    ".description__text--rich",
    "#job-details",
    ".jobs-description__text",
    ".jobs-unified-top-card__job-description",
    ".jobs-description__content",
    "[data-testid='job-details']",
]

# Botões "mostrar mais" dentro do painel de detalhe.
SELETORES_MOSTRAR_MAIS = [
    "button.show-more-less__button",
    "button[aria-label='Show more']",
    "button[aria-label='Ver mais']",
    "button[data-test-description-show-more]",
]

# Modais de login/consentimento que bloqueiam a vista.
SELETORES_OVERLAY = [
    "button.modal__dismiss",
    "button[data-test-modal-close-btn]",
    "button[aria-label='Dismiss']",
    "button[aria-label='Fechar']",
    "button.artdeco-modal__dismiss",
]

SELETORES_BANNER_COOKIES = [
    "#artdeco-global-eu-cookie-announcement button",
    "button[data-control-name='artdeco_cookie_footer_call_to_action']",
]

# Data de publicação no cartão (valida a recência da vaga no cliente).
SELETORES_DATA = [
    "time.job-search-card__listdate",
    "time[datetime]",
]

# Localização indicada no cartão (cidade/país ou "Remoto").
SELETORES_LOCAL = [
    "span.job-search-card__location",
    ".job-search-card__location",
    ".job-card-container__location",
    "[data-test-job-card-location]",
]


class ErroExtracao(RuntimeError):
    """Erro fatal de extração (bloqueio, rede ou DOM inesperado)."""


# --------------------------------------------------------------------------- #
# Utilitários
# --------------------------------------------------------------------------- #


def _pausa(min_s: float = 0.8, max_s: float = 2.2) -> None:
    """Pausa aleatória para mitigar deteção de bots (time.sleep)."""
    time.sleep(random.uniform(min_s, max_s))


def _limpar(texto: str) -> str:
    """Colapsa espaços/quebras de linha e remove zero-width spaces."""
    return " ".join(texto.replace("\u200b", " ").split())


def _cortar(texto: str, max_chars: int = 600) -> str:
    """Trunca o resumo numa fronteira de palavra, acrescentando reticências."""
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars].rsplit(" ", 1)[0] + "…"


# --------------------------------------------------------------------------- #
# Navegação e interação com a página
# --------------------------------------------------------------------------- #


# Códigos oficiais do LinkedIn para o filtro "Data de publicação" (f_TPR):
# valor em segundos ("r" + segundos). 1 dia = 86400, semana = 604800, mês = 2592000.
_TPR_OFICIAL = {1: "r86400", 7: "r604800", 30: "r2592000"}


def _codigo_tpr(dias: int) -> str:
    """Converte um número de dias no código `f_TPR` do LinkedIn."""
    return _TPR_OFICIAL.get(dias, f"r{dias * 86400}")


def construir_url_pesquisa(
    keywords: str = QUERY_BOOLEANA,
    localizacao: Optional[str] = "Brasil",
    remoto: bool = True,
    dias_publicacao: int = 7,
) -> str:
    """
    Monta a URL da pesquisa pública do LinkedIn.

    * `keywords`        -> query booleana (cargos/stack AND nível júnior).
    * `localizacao`     -> país/cidade, padrão "Brasil" (com `geoId` oficial
                           vindo de `GEOS`). IMPORTANTE: o LinkedIn IGNORA o
                           mero texto em `location` (usa o defeito do IP),
                           por isso o geoId é obrigatório. `None` = sem
                           restrição geográfica (vagas de todo o mundo).
    * `remoto`          -> ativa o filtro oficial `f_WT=2` (Trabalho: Remoto).
    * `dias_publicacao` -> filtro oficial `f_TPR` "Data de publicação"
                           (ex.: 7 = última semana). 0 = sem limite de data.

    Nota: NÃO se aplica `f_AL` (Candidatura Simplificada) — a pesquisa inclui
    tanto candidaturas externas como candidatura simplificada.
    """
    parametros: dict[str, str] = {
        "keywords": keywords,
        "position": "1",
        "pageNum": "0",
    }
    if localizacao:
        parametros["location"] = localizacao
        geo_id = GEOS.get(localizacao)
        if geo_id:
            parametros["geoId"] = geo_id
    if remoto:
        # f_WT: 1 = No escritório, 2 = Remoto, 3 = Híbrido
        parametros["f_WT"] = "2"
    if dias_publicacao > 0:
        parametros["f_TPR"] = _codigo_tpr(dias_publicacao)
    return f"{URL_PESQUISA_BASE}?{urllib.parse.urlencode(parametros)}"


def _normalizar_url(href: str) -> str:
    """Converte URLs relativas em absolutas e remove parâmetros de tracking."""
    absoluto = urllib.parse.urljoin(URL_PESQUISA_BASE, href)
    partes = urllib.parse.urlsplit(absoluto)
    return urllib.parse.urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))


def _texto(container, seletores: list[str]) -> str:
    """Devolve o texto do primeiro seletor que responder dentro do container."""
    for seletor in seletores:
        try:
            elemento = container.query_selector(seletor)
            if elemento is None:
                continue
            bruto = elemento.inner_text() or ""
        except Exception:  # noqa: BLE001 - DOM volátil do LinkedIn
            continue
        limpo = _limpar(bruto)
        if limpo:
            return limpo
    return ""


def _atributo(container, seletores: list[str], atributo: str) -> str:
    """Devolve o valor de um atributo (ex.: href) do primeiro seletor válido."""
    for seletor in seletores:
        try:
            elemento = container.query_selector(seletor)
            if elemento is None:
                continue
            valor = elemento.get_attribute(atributo)
        except Exception:  # noqa: BLE001 - DOM volátil do LinkedIn
            continue
        if valor:
            return valor
    return ""


def _data_publicacao(container) -> Optional[date]:
    """
    Devolve a data de publicação de um cartão (atributo `datetime` de <time>,
    ex.: "2026-10-01") ou None quando o elemento não existe/é inválido.
    """
    for seletor in SELETORES_DATA:
        try:
            elemento = container.query_selector(seletor)
            if elemento is None:
                continue
            bruto = elemento.get_attribute("datetime") or ""
        except Exception:  # noqa: BLE001 - DOM volátil do LinkedIn
            continue
        if not bruto:
            continue
        try:
            return datetime.fromisoformat(bruto).date()
        except ValueError:
            continue
    return None


def _fechar_overlays(pagina) -> None:
    """Remove modais de login/banner de cookies (JS) e fecha botões conhecidos."""
    # O modal do LinkedIn pode ficar "invisible" mas ainda interceptar cliques;
    # removê-lo diretamente do DOM é o fallback mais robusto.
    try:
        pagina.evaluate(
            """() => document.querySelectorAll(
                 '.top-level-modal-container, .modal__overlay, '
                 + '#artdeco-global-eu-cookie-announcement'
               ).forEach(e => e.remove())"""
        )
    except PlaywrightError:
        pass
    for seletor in SELETORES_BANNER_COOKIES + SELETORES_OVERLAY:
        try:
            botao = pagina.query_selector(seletor)
            if botao is not None and botao.is_visible():
                botao.click(timeout=2000)
                _pausa(0.4, 0.9)
                return
        except Exception:  # noqa: BLE001
            continue


def _localizar_cartoes(pagina) -> list:
    """Lista os cartões de vaga usando o primeiro seletor que devolver items."""
    for seletor in SELETORES_CARTAO:
        try:
            cartoes = pagina.query_selector_all(seletor)
        except PlaywrightError:
            continue
        if cartoes:
            return cartoes
    return []


def _rolar_lista(pagina) -> None:
    """Rola a coluna de resultados (container interno ou página inteira)."""
    for alvo in (
        "div.jobs-search-results-list",
        "div.scaffold-layout__list",
        "ul.jobs-search__results-list",
    ):
        try:
            if pagina.query_selector(alvo):
                pagina.eval_on_selector(alvo, "el => el.scrollTop += 700")
                return
        except PlaywrightError:
            continue
    try:
        pagina.mouse.wheel(0, 700)
    except PlaywrightError:
        pass


def _restaurar_lista(pagina, url_pesquisa: str, timeout_ms: int) -> bool:
    """Garante que a lista de vagas está visível (volta atrás ou recarrega)."""
    if _localizar_cartoes(pagina):
        return True
    try:
        pagina.go_back(wait_until="domcontentloaded", timeout=timeout_ms)
        _pausa(0.8, 1.6)
        _fechar_overlays(pagina)
        if _localizar_cartoes(pagina):
            return True
    except PlaywrightError:
        pass
    try:
        pagina.goto(url_pesquisa, wait_until="domcontentloaded", timeout=timeout_ms)
        _fechar_overlays(pagina)
        pagina.wait_for_selector(", ".join(SELETORES_CARTAO), timeout=timeout_ms)
        return True
    except PlaywrightError:
        return False


# --------------------------------------------------------------------------- #
# Extração
# --------------------------------------------------------------------------- #


def _limpar_abas_extras(pagina) -> None:
    """Fecha abas abertas além da principal (modo visitante pode abrir nova)."""
    try:
        for aba in list(pagina.context.pages[1:]):
            aba.close()
    except PlaywrightError:
        pass


def _descrever_por_clique(pagina, cartao, url_pesquisa: str, timeout_ms: int) -> str:
    """
    Lê a descrição completa no painel de detalhe. Clicar pode navegar na mesma
    aba ou abrir nova aba (modo visitante) — ambos os casos são tratados e a
    lista de resultados é restaurada no final.
    """
    resumo = ""
    _fechar_overlays(pagina)  # garante que nada intercepta o clique

    # ID da vaga permite esperar que o painel SPA realmente atualize
    # (sem isto, poderíamos ler a descrição da vaga anterior).
    job_id = None
    try:
        job_id = cartao.evaluate(
            "el => { const c = el.querySelector('[data-entity-urn]') || el;"
            " const m = ((c.getAttribute('data-entity-urn') || '').match"
            "(/jobPosting:(\\d+)/)); return m ? m[1] : null; }"
        )
    except PlaywrightError:
        pass

    try:
        # Clique via JS: imune a overlays residuais que interceptam pointer
        # events e não impedem a navegação SPA (currentJobId na URL).
        cartao.evaluate(
            "el => (el.tagName === 'A' ? el : el.querySelector('a') || el).click()"
        )
    except PlaywrightError:
        return ""
    _pausa(0.8, 1.6)

    paginas = pagina.context.pages
    alvo = paginas[-1]  # última aba aberta (ou a própria página)
    try:
        if job_id:
            # Espera o painel apontar para ESTA vaga antes de ler a descrição.
            alvo.wait_for_url(
                lambda u: f"currentJobId={job_id}" in u, timeout=6000
            )
            _pausa(0.6, 1.2)  # dá tempo ao DOM para renderizar a nova descrição
        alvo.wait_for_selector(", ".join(SELETORES_DESCRICAO), timeout=8000)
        # Tenta expandir a descrição completa ("mostrar mais").
        for seletor in SELETORES_MOSTRAR_MAIS:
            botao = alvo.query_selector(seletor)
            if botao is not None:
                try:
                    botao.click(timeout=2000)
                    _pausa(0.5, 1.0)
                except PlaywrightError:
                    pass
                break
        resumo = _texto(alvo, SELETORES_DESCRICAO)
    except PlaywrightTimeoutError:
        logger.warning("Painel de detalhe não carregou a tempo; sem resumo.")
    except PlaywrightError as exc:
        logger.warning("Falha ao ler descrição detalhada: %s", exc)
    finally:
        _limpar_abas_extras(pagina)
        _restaurar_lista(pagina, url_pesquisa, timeout_ms)

    return _cortar(resumo)


def _extrair_cartao(
    pagina,
    cartao,
    detalhar_descricao: bool,
    url_pesquisa: str,
    timeout_ms: int,
) -> Optional[dict[str, str]]:
    """Extrai título, empresa, URL e resumo de um único cartão de vaga."""
    titulo = _texto(cartao, SELETORES_TITULO)
    empresa = _texto(cartao, SELETORES_EMPRESA)
    local = _texto(cartao, SELETORES_LOCAL)
    href = _atributo(cartao, SELETORES_LINK, "href")
    resumo = _texto(cartao, SELETORES_RESUMO)

    if not titulo and not href:
        return None
    if not href:
        href = _atributo(cartao, ["a"], "href")
    if not href:
        return None

    if not resumo and detalhar_descricao:
        resumo = _descrever_por_clique(pagina, cartao, url_pesquisa, timeout_ms)

    data = _data_publicacao(cartao)
    return {
        "titulo": titulo or "(sem título)",
        "empresa": empresa or "(empresa não identificada)",
        "localizacao": local,
        "url": _normalizar_url(href),
        "resumo": resumo,
        "data_publicacao": data.isoformat() if data else "",
    }


def _carregar_pesquisa(pagina, url: str, timeout_ms: int) -> None:
    """Navega até à pesquisa tratando bloqueios, lentidão e overlays."""
    try:
        resposta = pagina.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise ErroExtracao(
            "Tempo esgotado ao carregar a pesquisa do LinkedIn (rede lenta?)."
        ) from exc
    except PlaywrightError as exc:
        raise ErroExtracao(f"Falha de navegação até ao LinkedIn: {exc}") from exc

    if resposta is not None and resposta.status in (403, 429, 999):
        raise ErroExtracao(
            f"LinkedIn respondeu HTTP {resposta.status} — provável bloqueio "
            "anti-bot. Aguarde alguns minutos, use headless=False ou aumente "
            "as pausas aleatórias."
        )

    _pausa(1.0, 2.0)
    _fechar_overlays(pagina)

    seletor_cartoes = ", ".join(SELETORES_CARTAO)
    try:
        pagina.wait_for_selector(seletor_cartoes, timeout=timeout_ms)
    except PlaywrightTimeoutError:
        # Última tentativa: espera a rede ficar ociosa e fecha overlays outra vez.
        try:
            pagina.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightError:
            pass
        _fechar_overlays(pagina)
        try:
            pagina.wait_for_selector(seletor_cartoes, timeout=10_000)
        except PlaywrightTimeoutError as exc:
            raise ErroExtracao(
                "Nenhum cartão de vaga encontrado. A pesquisa pode estar "
                "bloqueada para visitas sem login ou o DOM do LinkedIn mudou "
                "(atualize os seletores em extracao.py)."
            ) from exc


def _coletar_pagina(
    pagina,
    url_pesquisa: str,
    limite_total: int,
    limite_consulta: int,
    detalhar_descricao: bool,
    dias_publicacao: int,
    timeout_ms: int,
    resultados: list[dict[str, str]],
    vistos: set[str],
) -> None:
    """
    Percorre a lista de resultados de UMA consulta e acrescenta vagas novas a
    `resultados` (deduplicadas pelo conjunto `vistos`).

    * `limite_total`    — teto global de vagas já acumuladas;
    * `limite_consulta` — cota de vagas novas atribuída a ESTA consulta;
    * `max_sem_novos`   — corta o loop se a lista deixar de crescer.
    """
    indice = 0
    sem_novos = 0
    novos = 0
    max_sem_novos = 8

    while (
        len(resultados) < limite_total
        and novos < limite_consulta
        and sem_novos < max_sem_novos
    ):
        cartoes = _localizar_cartoes(pagina)

        if not cartoes:
            if not _restaurar_lista(pagina, url_pesquisa, timeout_ms):
                logger.error("Lista de vagas indisponível; a terminar.")
                break
            sem_novos += 1
            continue

        if indice >= len(cartoes):
            _rolar_lista(pagina)
            sem_novos += 1
            _pausa(1.0, 2.0)
            continue

        cartao = cartoes[indice]
        indice += 1

        # Filtro de recência no cliente (complementa o f_TPR da URL):
        # ignora vagas publicadas há mais de `dias_publicacao` dias.
        # Não conta como falha (sem_novos): é progresso legítimo do índice.
        if dias_publicacao > 0:
            data_cartao = _data_publicacao(cartao)
            if data_cartao is not None:
                idade = (date.today() - data_cartao).days
                if idade > dias_publicacao:
                    logger.debug(
                        "Cartão #%s ignorado: publicado há %s dias.",
                        indice,
                        idade,
                    )
                    continue

        # try/except vital: mudança de DOM num cartão não aborta o lote.
        try:
            item = _extrair_cartao(
                pagina, cartao, detalhar_descricao, url_pesquisa, timeout_ms
            )
        except Exception as exc:  # noqa: BLE001 - proteção total por item
            logger.warning("Falha ao ler o cartão #%s: %s", indice, exc)
            sem_novos += 1
            continue

        if item is None:
            sem_novos += 1
            continue

        chave = item["url"].split("?")[0]
        if chave in vistos:
            continue

        vistos.add(chave)
        resultados.append(item)
        novos += 1
        sem_novos = 0
        _pausa(0.6, 1.4)

    logger.info(
        "Consulta devolveu %s vagas novas (total acumulado: %s).",
        novos,
        len(resultados),
    )


def extrair_vagas(
    keywords: str | Sequence[str] | None = None,
    localizacao: Optional[str] = "Brasil",
    max_vagas: int = 25,
    dias_publicacao: int = 7,
    detalhar_descricao: bool = True,
    headless: bool = True,
    timeout_ms: int = 25_000,
) -> list[dict[str, str]]:
    """
    Executa a(s) pesquisa(s) pública(s) no LinkedIn e devolve uma lista de
    dicionários com as chaves: `titulo`, `empresa`, `localizacao`, `url`,
    `resumo` e `data_publicacao`.

    Parâmetros
    ----------
    keywords           : consulta booleana (str) OU sequência de consultas.
                         Cada consulta executa-se por sua vez e os resultados
                         são unidos e deduplicados por URL. Por omissão usa
                         `CONSULTAS` (cargos PT, stack e cargos EN — por ordem
                         de prioridade).
    localizacao        : país/cidade com geoId oficial (padrão "Brasil");
                         None = vagas de todo o mundo.
    max_vagas          : total de vagas a extrair, repartido equitativamente
                         pelas consultas (cota arredondada para cima).
    dias_publicacao    : janela de recência em dias — filtro `f_TPR` na URL +
                         validação da data no cartão (0 = sem limite).
    detalhar_descricao : se True, clica no cartão para obter a descrição
                         completa quando o resumo curto não existe.
    headless           : corre o Chromium sem interface (mais discreto).
    timeout_ms         : timeout base das esperas do Playwright.

    Se TODAS as consultas falharem é levantada `ErroExtracao`; se apenas
    algumas falharem, o erro é registado no log e as restantes executam-se.
    """
    if keywords is None:
        consultas = list(CONSULTAS)
    elif isinstance(keywords, str):
        consultas = [keywords]
    else:
        consultas = [consulta for consulta in keywords if consulta]

    if not consultas:
        raise ErroExtracao("Nenhuma consulta de pesquisa fornecida.")

    # Cota justa por consulta (arredondada para cima): garante que TODAS as
    # consultas contribuem mesmo quando max_vagas é pequeno.
    cota = -(-max_vagas // len(consultas))

    resultados: list[dict[str, str]] = []
    vistos: set[str] = set()
    erros: list[str] = []

    with sync_playwright() as p:
        try:
            navegador = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except PlaywrightError as exc:
            raise ErroExtracao(
                "Chromium do Playwright não está instalado. Execute: "
                "`python -m playwright install chromium`"
            ) from exc

        contexto = navegador.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="pt-BR",
        )
        pagina = contexto.new_page()
        pagina.set_default_timeout(timeout_ms)

        try:
            for consulta in consultas:
                if len(resultados) >= max_vagas:
                    break

                url_pesquisa = construir_url_pesquisa(
                    consulta, localizacao, dias_publicacao=dias_publicacao
                )
                logger.info("Consulta: %s", consulta)

                try:
                    _carregar_pesquisa(pagina, url_pesquisa, timeout_ms)
                except ErroExtracao as exc:
                    # Uma consulta a falhar não invalida as restantes
                    # (ex.: limite de carregamento ou overlays numa delas).
                    logger.warning("Consulta falhou (%s): %s", consulta, exc)
                    erros.append(str(exc))
                    _pausa(1.5, 3.0)
                    continue

                _coletar_pagina(
                    pagina,
                    url_pesquisa,
                    limite_total=max_vagas,
                    limite_consulta=cota,
                    detalhar_descricao=detalhar_descricao,
                    dias_publicacao=dias_publicacao,
                    timeout_ms=timeout_ms,
                    resultados=resultados,
                    vistos=vistos,
                )

            if not resultados and erros:
                # Todas as consultas falharam: propaga o primeiro erro.
                raise ErroExtracao(erros[0])

            logger.info(
                "Total: %s vagas de %s consulta(s).",
                len(resultados),
                len(consultas),
            )
        except ErroExtracao:
            raise
        except PlaywrightError as exc:
            raise ErroExtracao(f"Erro inesperado do Playwright: {exc}") from exc
        finally:
            contexto.close()
            navegador.close()

    return resultados[:max_vagas]


# --------------------------------------------------------------------------- #
# CLI de demonstração
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    quantidade = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    try:
        vagas = extrair_vagas(max_vagas=quantidade)
    except ErroExtracao as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        raise SystemExit(1) from erro
    print(json.dumps(vagas, ensure_ascii=False, indent=2))



