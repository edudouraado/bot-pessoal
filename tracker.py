"""
Tracker de candidaturas — SQLite local.

Estados possíveis:
  descoberta  → vaga encontrada pelo bot
  preparada   → carta gerada, pronta para enviar
  enviada     → candidatura enviada
  entrevista  → convocado para entrevista
  teste       → teste técnico
  proposta    → proposta recebida
  rejeitada   → não avançou
  desistiu    → cancelada pelo candidato
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "candidaturas.db"

ESTADOS = [
    "descoberta", "preparada", "enviada",
    "entrevista", "teste", "proposta", "rejeitada", "desistiu",
]


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar() -> None:
    with _conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidaturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                titulo TEXT,
                empresa TEXT,
                fonte TEXT,
                localizacao TEXT,
                score INTEGER,
                salario_min REAL,
                salario_max REAL,
                estado TEXT DEFAULT 'descoberta',
                carta TEXT,
                observacoes TEXT,
                criado_em TEXT,
                atualizado_em TEXT
            )
        """)


def registrar(vaga: dict) -> bool:
    """Registra vaga se ainda não existir. Devolve True se foi nova."""
    inicializar()
    with _conectar() as conn:
        try:
            conn.execute(
                """INSERT INTO candidaturas
                   (url, titulo, empresa, fonte, localizacao, score,
                    salario_min, salario_max, estado, criado_em, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'descobreta', ?, ?)""",
                (
                    vaga["url"], vaga["titulo"], vaga["empresa"],
                    vaga.get("fonte", ""), vaga.get("localizacao", ""),
                    vaga.get("score", 0), vaga.get("salario_min"),
                    vaga.get("salario_max"),
                    datetime.now().isoformat(timespec="seconds"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def guardar_carta(url: str, carta: str, estado: str = "preparada") -> None:
    inicializar()
    with _conectar() as conn:
        conn.execute(
            "UPDATE candidaturas SET carta = ?, estado = ?, atualizado_em = ? WHERE url = ?",
            (carta, estado, datetime.now().isoformat(timespec="seconds"), url),
        )


def mudar_estado(url: str, novo_estado: str) -> None:
    if novo_estado not in ESTADOS:
        raise ValueError(f"Estado inválido: {novo_estado}. Use: {ESTADOS}")
    inicializar()
    with _conectar() as conn:
        conn.execute(
            "UPDATE candidaturas SET estado = ?, atualizado_em = ? WHERE url = ?",
            (novo_estado, datetime.now().isoformat(timespec="seconds"), url),
        )


def listar(estado: str | None = None) -> list[dict]:
    inicializar()
    with _conectar() as conn:
        if estado:
            rows = conn.execute(
                "SELECT * FROM candidaturas WHERE estado = ? ORDER BY score DESC",
                (estado,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM candidaturas ORDER BY atualizado_em DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def resumo() -> dict:
    inicializar()
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT estado, COUNT(*) as n FROM candidaturas GROUP BY estado"
        ).fetchall()
    return {r["estado"]: r["n"] for r in rows}
