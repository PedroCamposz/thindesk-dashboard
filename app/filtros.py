"""Leitura e validação dos filtros de consulta (RF05), comuns a vários endpoints.

Filtros aceitos na query string:
  data_inicio, data_fim   -> AAAA-MM-DD (aplicados sobre a data de abertura)
  status                  -> um ou mais, separados por vírgula
  prioridade              -> uma ou mais, separadas por vírgula
  tipo_id, tecnico_id, setor_id -> inteiros (devem existir)
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .db import get_db
from .erros import ParametroInvalido
from .regras import PRIORIDADES, STATUS


@dataclass
class Filtro:
    data_inicio: date | None = None
    data_fim: date | None = None
    status: list = field(default_factory=list)
    prioridade: list = field(default_factory=list)
    tipo_id: int | None = None
    tecnico_id: int | None = None
    setor_id: int | None = None

    def where(self, alias="c", usar_datas=True):
        """Monta cláusula WHERE parametrizada (sem concatenar valores -> sem SQL injection)."""
        cond, params = [], []
        if usar_datas and self.data_inicio:
            cond.append(f"{alias}.aberto_em >= ?")
            params.append(f"{self.data_inicio} 00:00:00")
        if usar_datas and self.data_fim:
            cond.append(f"{alias}.aberto_em <= ?")
            params.append(f"{self.data_fim} 23:59:59")
        if self.status:
            cond.append(f"{alias}.status IN ({','.join('?' * len(self.status))})")
            params += self.status
        if self.prioridade:
            cond.append(f"{alias}.prioridade IN ({','.join('?' * len(self.prioridade))})")
            params += self.prioridade
        for campo in ("tipo_id", "tecnico_id", "setor_id"):
            valor = getattr(self, campo)
            if valor is not None:
                cond.append(f"{alias}.{campo} = ?")
                params.append(valor)
        return (" WHERE " + " AND ".join(cond)) if cond else "", params

    def como_dict(self):
        return {k: (str(v) if isinstance(v, date) else v) for k, v in self.__dict__.items() if v not in (None, [])}


def ler_data(valor, nome):
    if valor in (None, ""):
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        raise ParametroInvalido(f"'{nome}' deve estar no formato AAAA-MM-DD.", {"parametro": nome, "valor": valor})


def ler_inteiro(valor, nome, minimo=None, maximo=None, padrao=None):
    if valor in (None, ""):
        return padrao
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ParametroInvalido(f"'{nome}' deve ser um número inteiro.", {"parametro": nome, "valor": valor})
    if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
        raise ParametroInvalido(f"'{nome}' deve estar entre {minimo} e {maximo}.", {"parametro": nome, "valor": n})
    return n


def ler_lista(valor, nome, permitidos):
    if not valor:
        return []
    itens = [v.strip().lower() for v in valor.split(",") if v.strip()]
    invalidos = [v for v in itens if v not in permitidos]
    if invalidos:
        raise ParametroInvalido(f"Valor inválido para '{nome}': {', '.join(invalidos)}.",
                                {"parametro": nome, "permitidos": list(permitidos)})
    return list(dict.fromkeys(itens))


def _existe(tabela, id_):
    return get_db().execute(f"SELECT 1 FROM {tabela} WHERE id = ?", (id_,)).fetchone() is not None


def ler_filtro(args) -> Filtro:
    f = Filtro(
        data_inicio=ler_data(args.get("data_inicio"), "data_inicio"),
        data_fim=ler_data(args.get("data_fim"), "data_fim"),
        status=ler_lista(args.get("status"), "status", STATUS),
        prioridade=ler_lista(args.get("prioridade"), "prioridade", PRIORIDADES),
        tipo_id=ler_inteiro(args.get("tipo_id"), "tipo_id", 1),
        tecnico_id=ler_inteiro(args.get("tecnico_id"), "tecnico_id", 1),
        setor_id=ler_inteiro(args.get("setor_id"), "setor_id", 1),
    )
    if f.data_inicio and f.data_fim and f.data_inicio > f.data_fim:
        raise ParametroInvalido("'data_inicio' não pode ser maior que 'data_fim'.",
                                {"data_inicio": str(f.data_inicio), "data_fim": str(f.data_fim)})
    for campo, tabela in (("tipo_id", "tipos_chamado"), ("tecnico_id", "tecnicos"), ("setor_id", "setores")):
        valor = getattr(f, campo)
        if valor is not None and not _existe(tabela, valor):
            raise ParametroInvalido(f"'{campo}' = {valor} não existe.", {"parametro": campo, "valor": valor})
    return f


def periodo_padrao(f: Filtro, hoje: date, dias=30):
    """Garante um intervalo de datas (padrão: últimos 30 dias) para séries temporais."""
    fim = f.data_fim or hoje
    inicio = f.data_inicio or (fim - timedelta(days=dias - 1))
    return inicio, fim
