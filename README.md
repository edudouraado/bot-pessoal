# 💼 Pipeline Local de Procura de Emprego Remoto

Pipeline local em Python com três módulos independentes que extraem, processam
e apresentam vagas de emprego remotas do LinkedIn (pesquisa pública, sem login).

## Estrutura

| Ficheiro          | Módulo              | Tecnologia  | Responsabilidade |
|-------------------|---------------------|-------------|------------------|
| `extracao.py`     | 1. Extração         | Playwright  | Navegar na pesquisa do LinkedIn e extrair título, empresa, URL e resumo. |
| `processamento.py`| 2. Processamento    | Pandas      | Calcular o Match Score, limpar, deduplicar e ordenar. |
| `app.py`          | 3. Visualização     | Streamlit   | Interface com botão de execução e tabela interativa com links clicáveis. |

## Instalação

```bash
pip install -r requirements.txt
python -m playwright install chromium   # uma única vez (descarrega o browser)
```

## Execução

```bash
# Interface web (recomendado)
python -m streamlit run app.py

# Extração standalone (devolve JSON)
python extracao.py 10
```

## Consultas aplicadas

A pesquisa executa **três consultas booleanas** em sequência (resultados
unidos e deduplicados por URL). A cota de `max_vagas` divide-se por consulta,
por isso **a ordem é a prioridade**:

1. **Cargos em português (prioridade):**
   ```
   ("Desenvolvedor" OR "Desenvolvedora" OR "Programador" OR "Programadora" OR "Dev") AND ("Júnior" OR "Junior" OR "Entry level" OR "Graduate" OR "Trainee")
   ```
2. **Stack técnica:**
   ```
   ("Python" OR "SQL" OR "PostgreSQL" OR "React" OR "JavaScript" OR "TypeScript" OR "FastAPI") AND ("Júnior" OR "Junior" OR "Entry level" OR "Graduate" OR "Trainee")
   ```
3. **Cargos em inglês (empresas BR com títulos em inglês):**
   ```
   ("Developer" OR "Software Engineer" OR "Fullstack" OR "Full Stack" OR "Frontend" OR "Backend") AND ("Júnior" OR "Junior" OR "Entry level" OR "Graduate" OR "Trainee")
   ```

Para personalizar, edite as listas `TERMOS_CARGOS_PT`, `TERMOS_STACK`,
`TERMOS_CARGOS_EN` e `TERMOS_NIVEL` no topo de `extracao.py` — as consultas
são geradas automaticamente a partir delas.

- **Geografia:** **Brasil** (`location=Brasil` + `geoId=106057199`). O
  `geoId` é obrigatório — sem ele o LinkedIn ignora o texto e usa a
  localização por defeito do IP. Para mudar o país: pesquise a localização
  na barra do LinkedIn, copie o `geoId` da URL final e acrescente a entrada
  em `GEOS` (em `extracao.py`). `localizacao=None` = sem restrição.
- **Modalidade:** `Remoto` (filtro oficial `f_WT=2`).
- **Recência:** por omissão, apenas vagas publicadas **na última semana**
  (`f_TPR=r604800` na URL + validação da data no cartão). Configurável no
  menu lateral (1/3/7/14/30 dias) ou com `dias_publicacao=0` para desativar.
- **Candidaturas:** **não** existe filtro `f_AL` (Candidatura Simplificada) —
  são incluídas tanto vagas com candidatura externa (site da empresa) como
  com candidatura simplificada.
- Sem autenticação, para evitar bloqueios.

## Match Score

| Regra | Pontos |
|-------|--------|
| `SQL`, `PostgreSQL`, `Python`, `FastAPI`, `React` | **+3** cada |
| `Dados`, `Automação`, `APIs` | **+2** cada |
| `Sénior`, `Senior`, `Pleno`, `Especialista`, `Lead`, `Tech Lead` | **−10** cada (exclusão) |

- Comparação sem distinção de maiúsculas/acentos (`Automação` == `automacao`).
- Termos equivalentes contam uma única vez (`Sénior`/`Senior`); `Tech Lead`
  subsume `Lead`.
- Pontuações negativas são omitidas; ordenação decrescente por `score`.

## Robustez anti-bloqueio

- User-Agent realista, viewport e locale consistentes.
- Pausas aleatórias (`time.sleep`) entre navegações e cliques.
- Seletores CSS com múltiplos fallbacks (DOM do LinkedIn muda frequentemente).
- try/except por cartão: uma vaga com DOM inesperado não aborta o lote.
- Deteção de HTTP 403/429/999 com mensagem clara (`ErroExtracao`).
- Remoção de modais de login/cookies via JS (interceptavam os cliques).
- Sincronização por `currentJobId` antes de ler a descrição (evita resumos
  da vaga anterior).

## Nota

Use com moderação e conforme os Termos de Serviço do LinkedIn. As pausas
aleatórias e a pesquisa sem login mitigam, mas não eliminam, o risco de
bloqueio. Vagas sem login estão limitadas à primeira página de resultados.
