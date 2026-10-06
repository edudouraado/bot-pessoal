"""
Módulo de Visualização (Streamlit)
==================================
Interface do pipeline de procura de emprego remoto. Importa os módulos
anteriores (`extracao` e `processamento`), expõe um botão de execução e
renderiza o DataFrame processado de forma interativa, com URLs clicáveis.

Execução:
    streamlit run app.py
"""

from __future__ import annotations

import logging

import streamlit as st

from extracao import CONSULTAS, ErroExtracao, extrair_vagas
from processamento import processar_vagas

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Procura de Emprego Remoto",
    page_icon="💼",
    layout="wide",
)

# --------------------------------------------------------------------------- #
# Estado da sessão (evita repetir a extração a cada interação)
# --------------------------------------------------------------------------- #


def _obter_estado() -> dict:
    """Garante a existência das chaves de estado na sessão."""
    if "df" not in st.session_state:
        st.session_state.df = None
    if "extraidas" not in st.session_state:
        st.session_state.extraidas = 0
    return st.session_state


def _executar_pesquisa(max_vagas: int, detalhar: bool, dias: int) -> None:
    """Chama o módulo de extração e depois o de processamento."""
    estado = _obter_estado()
    with st.spinner("A pesquisar vagas no LinkedIn (pode demorar 1-2 min)…"):
        try:
            lista = extrair_vagas(
                max_vagas=max_vagas,
                dias_publicacao=dias,
                detalhar_descricao=detalhar,
            )
        except ErroExtracao as exc:
            st.error(f"Falha na extração: {exc}")
            logger.error("Erro de extração: %s", exc)
            return
        except Exception as exc:  # noqa: BLE001 - salvaguarda geral da UI
            st.error(f"Erro inesperado na extração: {exc}")
            logger.exception("Erro inesperado na extração")
            return

    estado.extraidas = len(lista)
    estado.df = processar_vagas(lista)

    if estado.df.empty:
        st.warning(
            "A extração terminou sem vagas elegíveis. "
            "Verifique a ligação ou tente novamente mais tarde."
        )


def main() -> None:
    estado = _obter_estado()

    st.title("💼 Procura de Emprego Remoto")

    with st.sidebar:
        st.header("⚙️ Parâmetros")
        max_vagas = st.slider("Máximo de vagas", 5, 100, 25, step=5)
        dias = st.selectbox(
            "Publicadas nos últimos (dias)",
            options=[1, 3, 7, 14, 30],
            index=2,  # 7 dias = última semana
            help=(
                "Filtra vagas antigas: filtro oficial do LinkedIn (f_TPR) "
                "mais validação da data no cartão."
            ),
        )
        detalhar = st.checkbox(
            "Ler descrição completa (mais lento)", value=True
        )
        st.divider()
        executar = st.button(
            "🚀 Executar pesquisa", type="primary", use_container_width=True
        )
        st.caption(
            "A extração usa pausas aleatórias para mitigar bloqueios anti-bot; "
            "evite executar repetidamente em curtos intervalos."
        )
        st.caption(
            "ℹ️ Sem filtro de candidatura simplificada: são incluídas vagas "
            "com candidatura externa (site da empresa) e com candidatura "
            "simplificada."
        )

    st.caption(
        f"**{len(CONSULTAS)} consultas** • Remoto • Brasil • Publicadas nos "
        f"últimos **{dias} dias** • Nível: júnior/entry"
    )
    with st.expander("🔎 Consultas booleanas aplicadas"):
        for consulta in CONSULTAS:
            st.code(consulta, language=None)

    if executar:
        _executar_pesquisa(max_vagas, detalhar, dias)

    df = estado.df

    if df is None:
        st.info(
            "Configure os parâmetros no menu lateral e clique em "
            "**Executar pesquisa** para começar."
        )
        return

    # ------------------------------------------------------------------ #
    # Métricas resumo
    # ------------------------------------------------------------------ #
    col1, col2, col3 = st.columns(3)
    col1.metric("Vagas extraídas", estado.extraidas)
    col2.metric("Vagas elegíveis", len(df))
    col3.metric(
        "Score máximo",
        int(df["score"].max()) if not df.empty else 0,
    )

    if df.empty:
        st.warning("Nenhuma vaga com score >= 0 foi encontrada.")
        return

    # ------------------------------------------------------------------ #
    # Tabela interativa — URL como hiperligação clicável
    # ------------------------------------------------------------------ #
    st.subheader("🎯 Vagas ordenadas por Match Score")

    # Cópia de apresentação: limita o resumo para a tabela não ficar ilegível.
    # A coluna `url` mantém o URL puro e é configurada como LinkColumn,
    # garantindo hiperligações clicáveis dentro da tabela interativa.
    df_apresentacao = df.copy()
    truncado = df_apresentacao["resumo"].str.len() > 220
    df_apresentacao["resumo"] = df_apresentacao["resumo"].str.slice(0, 220) + (
        truncado.map({True: "…", False: ""})
    )

    st.dataframe(
        df_apresentacao,
        width="stretch",
        height=450,
        hide_index=True,
        column_config={
            "score": st.column_config.NumberColumn(
                "Score", help="Pontuação de aderência à sua stack", width="small"
            ),
            "termos": st.column_config.TextColumn(
                "Termos", help="Termos que geraram o score", width="medium"
            ),
            "titulo": st.column_config.TextColumn("Título", width="large"),
            "empresa": st.column_config.TextColumn("Empresa", width="medium"),
            "localizacao": st.column_config.TextColumn(
                "Local",
                help="Localização indicada na vaga (cidade/país ou Remoto)",
                width="medium",
            ),
            "data_publicacao": st.column_config.TextColumn(
                "Publicada",
                help="Data de publicação da vaga (AAAAMMDD)",
                width="small",
            ),
            "url": st.column_config.LinkColumn(
                "Vaga",
                display_text="Abrir vaga",
                help="Clique para abrir a vaga no LinkedIn",
                width="small",
            ),
            "resumo": st.column_config.TextColumn("Resumo", width="large"),
        },
    )

    # ------------------------------------------------------------------ #
    # Cartões com links garantidamente clicáveis (complemento da tabela)
    # ------------------------------------------------------------------ #
    with st.expander("🔗 Abrir vagas em lista de links"):
        for _, linha in df.iterrows():
            st.markdown(
                f"- **[{linha['titulo']}]({linha['url']})** — "
                f"{linha['empresa']} · score **{linha['score']}**"
            )

    # ------------------------------------------------------------------ #
    # Download do resultado
    # ------------------------------------------------------------------ #
    st.download_button(
        "⬇️ Descarregar CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="vagas_remote.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
