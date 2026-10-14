"""Fontes de vagas — todas usam APIs públicas ou pesquisa sem login."""

from .remoteok import buscar_remoteok
from .greenhouse import buscar_greenhouse
from .lever import buscar_lever

FONTE_LINKEDIN = "LinkedIn"
FONTE_REMOTEOK = "Remote OK"
FONTE_GREENHOUSE = "Greenhouse"
FONTE_LEVER = "Lever"

__all__ = [
    "buscar_remoteok",
    "buscar_greenhouse",
    "buscar_lever",
    "FONTE_LINKEDIN",
    "FONTE_REMOTEOK",
    "FONTE_GREENHOUSE",
    "FONTE_LEVER",
]
