"""
Dashboard multi-fonte — Streamlit.

Combina: LinkedIn (Playwright) + Remote OK + Greenhouse + Lever.
Gera carta com Ollama, rastreia candidaturas em SQLite.
"""

from __future__ import annotations

import logging

import streamlit as st

import config
import tracker
from cartas import gerar_carta, gerar_email_assunto
from extracao import CONSULTAS, ErroExtracao, extrair_vagas
from fontes import buscar_greenhouse, buscar_lever, buscar_remoteok
from processamento import processar_vagas

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Bot Pessoal — Vagas",
    page_icon="💼",
    layout="wide",
)


def _obter_estado() -> dict:
    for chave, valor in [("df", None), ("extraidas", 0), ("carta", None)]:
        if chave not in st.session_state:
            st.session_state[chave] = valor
    return st.session_state


def _executar_pesquisa(
    usar_linkedin: bool,
    usar_remoteok: bool,
    usar_greenhouse: bool,
    usar_lever: bool,
    max_vagas: int,
    dias: int,
    detalhar: bool,
    modalidades: list[str],
    salario_minimo: float | None,
) -> None:
    estado = _obter_estado()
    todas: list[dict] = []

    with st.status("A pesquisar vagas…", expanded=True) as status:
        if usar_linkedin:
            st.write("LinkedIn…")
            try:
                lista = extrair_vagas(
                    max_vagas=max_vagas // 2,
                    dias_publicacao=dias,
                    detalhar_descricao=detalhar,
                )
                for item in lista:
                    item["fonte"] = "LinkedIn"
                    item.setdefault("salario_min", None)
                    item.setdefault("salario_max", None)
                todas.extend(lista)
                st.write(f"  ✓ LinkedIn: {len(lista)}")
            except ErroExtracao as exc:
                st.warning(f"LinkedIn falhou: {exc}")
            except Exception as exc:
                st.warning(f"LinkedIn erro inesperado: {exc}")

        if usar_remoteok:
            st.write("Remote OK…")
            try:
                lista = buscar_remoteok(limite=max_vagas // 2)
                todas.extend(lista)
                st.write(f"  ✓ Remote OK: {len(lista)}")
            except Exception as exc:
                st.warning(f"Remote OK falhou: {exc}")

        if usar_greenhouse:
            st.write("Greenhouse (Nubank, iFood, Creditas…)…")
            try:
                lista = buscar_greenhouse(limite=max_vagas // 2)
                todas.extend(lista)
                st.write(f"  ✓ Greenhouse: {len(lista)}")
            except Exception as exc:
                st.warning(f"Greenhouse falhou: {exc}")

        if usar_lever:
            st.write("Lever (startups)…")
            try:
                lista = buscar_lever(limite=max_vagas // 2)
                todas.extend(lista)
                st.write(f"  ✓ Lever: {len(lista)}")
            except Exception as exc:
                st.warning(f"Lever falhou: {exc}")

        status.update(label=f"Concluído — {len(todas)} vagas brutas", state="complete")

    estado.extraidas = len(todas)
    estado.df = processar_vagas(
        todas,
        modalidades=modalidades or None,
        salario_minimo=salario_minimo or None,
    )

    if estado.df.empty:
        st.warning("Nenhuma vaga elegível com os filtros atuais.")
    else:
        for _, linha in estado.df.iterrows():
            tracker.registrar(linha.to_dict())


def _painel_tracker() -> None:
    st.subheader("📋 Pipeline de candidaturas")
    resumo = tracker.resumo()
    if not resumo:
        st.info("Nenhuma candidatura registada ainda.")
        return

    cols = st.columns(len(resumo))
    for col, (estado, n) in zip(cols, resumo.items()):
        col.metric(estado.title(), n)

    todas = tracker.listar()
    if todas:
        import pandas as pd
        df_t = pd.DataFrame(todas)
        mostrar = df_t[["estado", "titulo", "empresa", "score", "url"]].copy()
        st.dataframe(mostrar, width="stretch", hide_index=True)


def main() -> None:
    estado = _obter_estado()

    st.title("💼 Bot Pessoal — Caça a Vagas")
    st.caption(
        f"**{config.NOME}** · {config.LOCALIZACAO} · "
        f"alvo: {config.CARGO_DESEJADO} · salário mín: R$ {config.SALARIO_MINIMO}"
    )

    with st.sidebar:
        st.header("⚙️ Fontes")
        usar_linkedin = st.checkbox("LinkedIn", value=True, help="Playwright, sem login, pesquisa pública")
        usar_remoteok = st.checkbox("Remote OK", value=True, help="API pública, 100% legal")
        usar_greenhouse = st.checkbox("Greenhouse", value=True, help="ATS oficial — Nubank, iFood, etc")
        usar_lever = st.checkbox("Lever", value=True, help="API oficial de startups")

        st.divider()
        st.header("🎯 Filtros")
        max_vagas = st.slider("Máx. por fonte", 5, 100, 25, step=5)
        dias = st.selectbox("LinkedIn — publicadas nos últimos (dias)", [1, 3, 7, 14, 30], index=2)
        detalhar = st.checkbox("LinkedIn — ler descrição completa", value=True)
        modalidades = st.multiselect(
            "Modalidade", ["Remoto", "Híbrido", "Fortaleza"], default=["Remoto", "Híbrido"]
        )
        salario_minimo = st.number_input(
            "Salário mínimo (R$)", 0, 50000, config.SALARIO_MINIMO, step=500
        )

        st.divider()
        executar = st.button("🚀 Executar pesquisa", type="primary", use_container_width=True)

    with st.expander("🔎 Consultas booleanas do LinkedIn"):
        for consulta in CONSULTAS:
            st.code(consulta, language=None)

    if executar:
        _executar_pesquisa(
            usar_linkedin, usar_remoteok, usar_greenhouse, usar_lever,
            max_vagas, dias, detalhar, modalidades, salario_minimo or None,
        )

    df = estado.df

    if df is None:
        st.info("Configure as fontes no menu lateral e clique em **Executar pesquisa**.")
        _painel_tracker()
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vagas brutas", estado.extraidas)
    col2.metric("Elegíveis", len(df))
    col3.metric("Score máximo", int(df["score"].max()) if not df.empty else 0)
    col4.metric("Fontes ativas", sum([usar_linkedin, usar_remoteok, usar_greenhouse, usar_lever]))

    if df.empty:
        return

    st.subheader("🎯 Vagas ordenadas por Match Score")

    df_apresentacao = df.copy()
    truncado = df_apresentacao["resumo"].str.len() > 200
    df_apresentacao["resumo"] = df_apresentacao["resumo"].str.slice(0, 200) + (
        truncado.map({True: "…", False: ""})
    )

    st.dataframe(
        df_apresentacao,
        width="stretch",
        height=420,
        hide_index=True,
        column_config={
            "score": st.column_config.NumberColumn("Score", width="small"),
            "termos": st.column_config.TextColumn("Termos", width="medium"),
            "titulo": st.column_config.TextColumn("Título", width="large"),
            "empresa": st.column_config.TextColumn("Empresa", width="medium"),
            "localizacao": st.column_config.TextColumn("Local", width="medium"),
            "fonte": st.column_config.TextColumn("Fonte", width="small"),
            "salario_min": st.column_config.NumberColumn("Sal. mín", format="R$ %.0f", width="small"),
            "salario_max": st.column_config.NumberColumn("Sal. máx", format="R$ %.0f", width="small"),
            "url": st.column_config.LinkColumn("Vaga", display_text="Abrir", width="small"),
            "resumo": st.column_config.TextColumn("Resumo", width="large"),
        },
    )

    st.divider()
    st.subheader("✍️ Carta de apresentação")

    opcoes = [f"{r['score']} · {r['empresa']} — {r['titulo']}" for _, r in df.head(15).iterrows()]
    idx = st.selectbox("Escolher vaga", range(len(opcoes)), format_func=lambda i: opcoes[i])

    if idx is not None:
        linha = df.iloc[idx]
        if st.button("Gerar carta com IA", type="secondary"):
            with st.spinner("A gerar carta…"):
                carta = gerar_carta(linha["titulo"], linha["empresa"], linha["resumo"])
                st.session_state.carta = carta
                tracker.guardar_carta(linha["url"], carta)

        if st.session_state.carta:
            st.text_area("Carta (copiar e colar na candidatura)", st.session_state.carta, height=260)
            st.code(gerar_email_assunto(linha["titulo"], linha["empresa"]), language=None)
            col_a, col_b = st.columns(2)
            col_a.link_button("🔗 Abrir vaga no browser", linha["url"])
            col_b.button("✅ Marcar como 'preparada'", on_click=tracker.mudar_estado, args=(linha["url"], "preparada"))

    _painel_tracker()


if __name__ == "__main__":
    main()
