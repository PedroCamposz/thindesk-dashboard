"""Regras de negócio do Thindesk (enums, SLA, transições de status)."""
from datetime import datetime, timedelta

STATUS = ("aberto", "em_andamento", "aguardando", "resolvido", "cancelado")
STATUS_ATIVOS = ("aberto", "em_andamento", "aguardando")  # ainda na fila (backlog)
PRIORIDADES = ("baixa", "media", "alta", "critica")

# Multiplicador aplicado ao SLA base do tipo conforme a prioridade
FATOR_SLA = {"critica": 0.25, "alta": 0.5, "media": 1.0, "baixa": 1.5}

# Máquina de estados: de -> para (transições permitidas)
TRANSICOES = {
    "aberto": {"em_andamento", "cancelado"},
    "em_andamento": {"aguardando", "resolvido", "cancelado"},
    "aguardando": {"em_andamento", "cancelado"},
    "resolvido": {"em_andamento"},  # reabertura
    "cancelado": set(),
}


def calcular_prazo_sla(aberto_em: datetime, sla_horas: int, prioridade: str) -> datetime:
    return aberto_em + timedelta(hours=sla_horas * FATOR_SLA[prioridade])


def transicao_valida(atual: str, novo: str) -> bool:
    return novo in TRANSICOES.get(atual, set())


def classificar_saude(score: float) -> str:
    if score >= 85:
        return "Excelente"
    if score >= 70:
        return "Boa"
    if score >= 50:
        return "Atenção"
    return "Crítica"
