# 💼 Bot Pessoal — Caça a Vagas

Pipeline multi-fonte de busca de vagas **júnior** (dev fullstack + dados), com
filtros duros, scoring, geração de carta por IA local (Ollama) e tracker de
candidaturas em SQLite.

## Fontes (todas APIs públicas, sem login, sem risco de ban)

| Fonte | API | Legalidade |
|-------|-----|------------|
| **LinkedIn** | Pesquisa pública sem login (Playwright) | Uso pessoal, pausas aleatórias |
| **Remote OK** | `remoteok.com/api` | API pública oficial |
| **Greenhouse** | `boards-api.greenhouse.io` | API oficial de ATS (Nubank, Stone, etc) |
| **Lever** | `api.lever.co/v0/postings` | API oficial de ATS (startups) |

**Zero automação de candidatura** — a ferramenta encontra, filtra, gera a carta
e abre a vaga; o envio é feito por você (1 clique). Isso elimina risco de ban.

## Filtros duros (antes do score)

1. **Nível júnior obrigatório** — Junior, Trainee, Estágio, Entry, Graduate
2. **Tech/dev/dados obrigatório** — Python, SQL, React, Desenvolvedor, Analista de Dados, etc
3. **Exclusão por título** — se o título contiver Sênior, Pleno, Sales, Crypto, etc, a vaga é descartada na hora

Depois aplica score com bônus por stack e penalidade por termos indesejados.

## Match Score

| Regra | Pontos |
|-------|--------|
| Python, FastAPI, Node.js, React, SQL, PostgreSQL, JavaScript, TypeScript | **+4** |
| Desenvolvedor, Analista de Dados, Fullstack, Backend, Frontend, Software Engineer | **+3** |
| Dados, Automação, APIs, Pandas, Express, Tailwind | **+2** |
| Remoto, Híbrido | **+2** |
| Fortaleza, Ceará | **+3** |
| Sênior, Pleno, Sales, Vendas, Customer Success, Crypto… | **−20** |

## Instalação

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Ollama (opcional, para cartas com IA):
```bash
ollama pull qwen3.5:0.8b
```

## Execução

```bash
python -m streamlit run app.py
```

## Estrutura

| Ficheiro | Responsabilidade |
|----------|-----------------|
| `config.py` | Perfil do candidato (edite para calibrar) |
| `fontes/remoteok.py` | API Remote OK |
| `fontes/greenhouse.py` | API Greenhouse (boards brasileiros) |
| `fontes/lever.py` | API Lever |
| `extracao.py` | LinkedIn (Playwright, sem login) |
| `processamento.py` | Filtros duros + score + dedup + ordenação |
| `cartas.py` | Carta personalizada via Ollama (fallback: template) |
| `tracker.py` | Pipeline SQLite (descoberta → preparada → enviada → …) |
| `app.py` | Dashboard Streamlit |

## Tracker

Estados possíveis: `descoberta`, `preparada`, `enviada`, `entrevista`,
`teste`, `proposta`, `rejeitada`, `desistiu`.

A base de dados fica em `candidaturas.db` (local, não versionada).

## Nota sobre LinkedIn

O scraper usa pesquisa **pública sem login**, com User-Agent realista e
pausas aleatórias. Use com moderação e conforme os ToS do LinkedIn. As
fontes Greenhouse/Lever/Remote OK são APIs oficiais — sem risco de bloqueio.
