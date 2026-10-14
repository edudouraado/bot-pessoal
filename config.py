"""
Perfil do candidato — usado pelo scoring, filtros e geração de cartas.

Edite este ficheiro para calibrar a ferramenta ao seu perfil real.
"""

NOME = "Eduardo Dourado"
EMAIL = "edusalesoliveira@hotmail.com"
TELEFONE = "(61) 98343-9617"
LINKEDIN = "linkedin.com/in/eduardodouradosdo"
GITHUB = "github.com/edudouraado"
PORTFOLIO = "eduardo-portfolio-alpha.vercel.app"
LOCALIZACAO = "Fortaleza, CE"

CARGO_DESEJADO = "Desenvolvedor Júnior / Analista de Dados Júnior"

SALARIO_ATUAL = 3600
SALARIO_MINIMO = 5000

MODALIDADES = ["Remoto", "Híbrido"]

HABILIDADES = [
    "Python", "FastAPI", "Node.js", "JavaScript", "React",
    "PostgreSQL", "SQL", "Pandas", "Express",
    "HTML", "CSS", "Tailwind", "Git", "Power BI",
]

RESUMO = (
    "Profissional em transição para Tecnologia, combinando base analítica do Direito "
    "com experiência prática em operações, auditoria e gestão de estoque no varejo "
    "farmacêutico. Estudante de Análise e Desenvolvimento de Sistemas com domínio em "
    "SQL Avançado (CTEs, subconsultas, joins relacionais), Python, FastAPI, Node.js "
    "e React. Busco primeira oportunidade como Desenvolvedor Júnior para aplicar "
    "visão estratégica de negócios e habilidades técnicas na criação de soluções "
    "eficientes e automação de processos."
)

PROJETOS = [
    {
        "titulo": "Dashboard Analítico de Auditoria de Estoque",
        "stack": "Python, FastAPI, PostgreSQL, SQL Avançado",
        "descricao": (
            "API REST serverless com cache TTL para cruzamento automatizado de notas "
            "fiscais com conferências físicas, identificando divergências operacionais."
        ),
    },
    {
        "titulo": "Módulo Analítico de Conversão e Giro",
        "stack": "PostgreSQL, SQL Avançado",
        "descricao": (
            "Consultas analíticas complexas (CTEs, subconsultas otimizadas) cruzando "
            "transferências de estoque com vendas reais do PDV."
        ),
    },
    {
        "titulo": "Automação para Auditoria Fiscal",
        "stack": "Python, Pandas, XML",
        "descricao": (
            "Parsing massivo de XML de Notas Fiscais (NF-e 4.00) com namespaces para "
            "rastreabilidade de lotes e mitigação de perdas por validade."
        ),
    },
    {
        "titulo": "Openest — Plataforma de Conexões Sociais",
        "stack": "React, Node.js, PostgreSQL, JWT",
        "descricao": (
            "Aplicação web com feed dinâmico, chat em tempo real, autenticação JWT "
            "e moderação via React Portals."
        ),
    },
]

EXPERIENCIA = [
    {
        "empresa": "SB Farma",
        "cargo": "Analista Júnior de Gestão de Estoque e Mix Ideal",
        "periodo": "Fev/2026 – Presente",
        "destaques": [
            "Remanejamento de estoque com visão orientada a dados, otimizando distribuição",
            "Consultas SQL avançadas (CTEs, otimização de queries, relatórios relacionais)",
            "Automações em Python para leitura massiva de notas fiscais",
        ],
    },
    {
        "empresa": "SB Farma",
        "cargo": "Assistente de Prevenção de Perdas",
        "periodo": "Jun/2025 – Fev/2026",
        "destaques": [
            "Auditorias físicas sistêmicas e identificação de gargalos",
            "Controle de validades e rastreabilidade de lotes",
        ],
    },
]

FORMACAO = [
    "Análise e Desenvolvimento de Sistemas — Unifor (previsão 2026)",
    "Bacharelado em Direito — UniCEUB (concluído 2024)",
]
