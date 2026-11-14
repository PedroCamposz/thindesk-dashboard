"""Consultas e regras de negócio usadas pelos endpoints."""
from datetime import date, datetime, timedelta

from .db import agora, fmt, get_db, parse
from .erros import ErroApi, NaoEncontrado, ParametroInvalido
from .filtros import Filtro
from .regras import (PRIORIDADES, STATUS, STATUS_ATIVOS, TRANSICOES, calcular_prazo_sla, classificar_saude,
                     transicao_valida)

HORAS_RESOLUCAO = "(julianday(c.resolvido_em) - julianday(c.aberto_em)) * 24"
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
ROTULO_STATUS = {"aberto": "Aberto", "em_andamento": "Em andamento", "aguardando": "Aguardando usuário",
                 "resolvido": "Resolvido", "cancelado": "Cancelado"}


def _r(valor, casas=1):
    return round(valor, casas) if valor is not None else None


# ---------------------------------------------------------------- RF01
def indicadores(f: Filtro) -> dict:
    db = get_db()
    where, params = f.where()
    agora_txt = fmt(agora())
    linha = db.execute(f"""
        SELECT COUNT(*) AS total,
               SUM(c.status = 'aberto')       AS abertos,
               SUM(c.status = 'em_andamento') AS em_andamento,
               SUM(c.status = 'aguardando')   AS aguardando,
               SUM(c.status = 'resolvido')    AS resolvidos,
               SUM(c.status = 'cancelado')    AS cancelados,
               SUM(c.status IN ('aberto','em_andamento','aguardando') AND c.prazo_sla < ?) AS atrasados,
               AVG(CASE WHEN c.status = 'resolvido' THEN {HORAS_RESOLUCAO} END) AS tempo_medio,
               AVG(CASE WHEN c.status = 'resolvido' THEN (c.resolvido_em <= c.prazo_sla) * 100.0 END) AS taxa_sla,
               AVG(c.satisfacao) AS satisfacao
        FROM chamados c {where}""", [agora_txt, *params]).fetchone()

    total = linha["total"] or 0
    backlog = (linha["abertos"] or 0) + (linha["em_andamento"] or 0) + (linha["aguardando"] or 0)
    resultado = {
        "total_chamados": total,
        "abertos": linha["abertos"] or 0,
        "em_andamento": linha["em_andamento"] or 0,
        "aguardando": linha["aguardando"] or 0,
        "resolvidos": linha["resolvidos"] or 0,
        "cancelados": linha["cancelados"] or 0,
        "backlog": backlog,
        "atrasados": linha["atrasados"] or 0,
        "taxa_resolucao_pct": _r((linha["resolvidos"] or 0) * 100 / total) if total else 0.0,
        "tempo_medio_resolucao_horas": _r(linha["tempo_medio"]),
        "taxa_cumprimento_sla_pct": _r(linha["taxa_sla"]),
        "satisfacao_media": _r(linha["satisfacao"], 2),
        "variacao_periodo_anterior_pct": None,
    }

    # Comparação com o período anterior de mesmo tamanho (só quando há intervalo de datas)
    if f.data_inicio and f.data_fim:
        dias = (f.data_fim - f.data_inicio).days + 1
        anterior = Filtro(**{**f.__dict__, "data_inicio": f.data_inicio - timedelta(days=dias),
                             "data_fim": f.data_inicio - timedelta(days=1)})
        w2, p2 = anterior.where()
        total_ant = db.execute(f"SELECT COUNT(*) FROM chamados c {w2}", p2).fetchone()[0]
        resultado["total_periodo_anterior"] = total_ant
        if total_ant:
            resultado["variacao_periodo_anterior_pct"] = _r((total - total_ant) * 100 / total_ant)
    return resultado


# ---------------------------------------------------------------- RF02
def _chave_bucket(d: date, agrupamento: str) -> str:
    if agrupamento == "semana":
        return (d - timedelta(days=d.weekday())).isoformat()  # segunda-feira da semana
    if agrupamento == "mes":
        return d.strftime("%Y-%m")
    return d.isoformat()


def serie_periodo(f: Filtro, inicio: date, fim: date, agrupamento: str) -> dict:
    db = get_db()
    where_sem_data, params = f.where(usar_datas=False)
    conector = " AND " if where_sem_data else " WHERE "
    ini_txt, fim_txt = f"{inicio} 00:00:00", f"{fim} 23:59:59"

    buckets = {}
    d = inicio
    while d <= fim:
        buckets.setdefault(_chave_bucket(d, agrupamento),
                           {"abertos": 0, "resolvidos": 0, "resolvidos_no_sla": 0, "_horas": 0.0})
        d += timedelta(days=1)

    for row in db.execute(f"SELECT date(c.aberto_em) AS dia, COUNT(*) AS n FROM chamados c {where_sem_data}"
                          f"{conector} c.aberto_em BETWEEN ? AND ? GROUP BY dia", [*params, ini_txt, fim_txt]):
        buckets[_chave_bucket(date.fromisoformat(row["dia"]), agrupamento)]["abertos"] += row["n"]

    for row in db.execute(f"""SELECT date(c.resolvido_em) AS dia, COUNT(*) AS n,
                                     SUM(c.resolvido_em <= c.prazo_sla) AS no_sla, SUM({HORAS_RESOLUCAO}) AS horas
                              FROM chamados c {where_sem_data}{conector} c.status = 'resolvido'
                                   AND c.resolvido_em BETWEEN ? AND ? GROUP BY dia""",
                          [*params, ini_txt, fim_txt]):
        b = buckets[_chave_bucket(date.fromisoformat(row["dia"]), agrupamento)]
        b["resolvidos"] += row["n"]
        b["resolvidos_no_sla"] += row["no_sla"]
        b["_horas"] += row["horas"]

    serie = []
    for chave, b in buckets.items():
        serie.append({
            "periodo": chave,
            "abertos": b["abertos"],
            "resolvidos": b["resolvidos"],
            "saldo": b["abertos"] - b["resolvidos"],
            "taxa_sla_pct": _r(b["resolvidos_no_sla"] * 100 / b["resolvidos"]) if b["resolvidos"] else None,
            "tempo_medio_resolucao_horas": _r(b["_horas"] / b["resolvidos"]) if b["resolvidos"] else None,
        })
    return {
        "agrupamento": agrupamento,
        "data_inicio": str(inicio),
        "data_fim": str(fim),
        "totais": {"abertos": sum(s["abertos"] for s in serie), "resolvidos": sum(s["resolvidos"] for s in serie)},
        "serie": serie,
    }


# ---------------------------------------------------------------- RF03
def situacao(f: Filtro) -> dict:
    where, params = f.where()
    contagem = {s: 0 for s in STATUS}
    for row in get_db().execute(f"SELECT c.status, COUNT(*) n FROM chamados c {where} GROUP BY c.status", params):
        contagem[row["status"]] = row["n"]
    total = sum(contagem.values())
    por_prioridade = {p: 0 for p in PRIORIDADES}
    w2, p2 = f.where()
    w2 += (" AND " if w2 else " WHERE ") + "c.status IN ('aberto','em_andamento','aguardando')"
    for row in get_db().execute(f"SELECT c.prioridade, COUNT(*) n FROM chamados c {w2} GROUP BY c.prioridade", p2):
        por_prioridade[row["prioridade"]] = row["n"]
    return {
        "total": total,
        "status": [{"status": s, "rotulo": ROTULO_STATUS[s], "quantidade": n,
                    "percentual": _r(n * 100 / total) if total else 0.0} for s, n in contagem.items()],
        "backlog_por_prioridade": por_prioridade,
    }


# ---------------------------------------------------------------- RF04
def ranking_tipos(f: Filtro, limite: int) -> dict:
    where, params = f.where()
    rows = get_db().execute(f"""
        SELECT t.id, t.nome, t.sla_horas, COUNT(c.id) AS total,
               SUM(c.status = 'resolvido') AS resolvidos,
               AVG(CASE WHEN c.status = 'resolvido' THEN {HORAS_RESOLUCAO} END) AS tempo_medio,
               AVG(CASE WHEN c.status = 'resolvido' THEN (c.resolvido_em <= c.prazo_sla) * 100.0 END) AS taxa_sla
        FROM chamados c JOIN tipos_chamado t ON t.id = c.tipo_id {where}
        GROUP BY t.id ORDER BY total DESC, t.nome LIMIT ?""", [*params, limite]).fetchall()
    total_geral = get_db().execute(f"SELECT COUNT(*) FROM chamados c {where}", params).fetchone()[0]
    return {
        "total_geral": total_geral,
        "ranking": [{
            "posicao": i + 1, "tipo_id": r["id"], "tipo": r["nome"], "sla_base_horas": r["sla_horas"],
            "total": r["total"], "resolvidos": r["resolvidos"] or 0,
            "participacao_pct": _r(r["total"] * 100 / total_geral) if total_geral else 0.0,
            "tempo_medio_resolucao_horas": _r(r["tempo_medio"]), "taxa_cumprimento_sla_pct": _r(r["taxa_sla"]),
        } for i, r in enumerate(rows)],
    }


def desempenho_tecnicos(f: Filtro) -> list:
    where, params = f.where()
    rows = get_db().execute(f"""
        SELECT tc.id, tc.nome, tc.nivel, COUNT(c.id) AS atribuidos,
               SUM(c.status = 'resolvido') AS resolvidos,
               SUM(c.status IN ('aberto','em_andamento','aguardando')) AS em_fila,
               AVG(CASE WHEN c.status = 'resolvido' THEN {HORAS_RESOLUCAO} END) AS tempo_medio,
               AVG(CASE WHEN c.status = 'resolvido' THEN (c.resolvido_em <= c.prazo_sla) * 100.0 END) AS taxa_sla,
               AVG(c.satisfacao) AS satisfacao
        FROM chamados c JOIN tecnicos tc ON tc.id = c.tecnico_id {where}
        GROUP BY tc.id ORDER BY resolvidos DESC, tc.nome""", params).fetchall()
    return [{"tecnico_id": r["id"], "nome": r["nome"], "nivel": r["nivel"], "atribuidos": r["atribuidos"],
             "resolvidos": r["resolvidos"] or 0, "em_fila": r["em_fila"] or 0,
             "tempo_medio_resolucao_horas": _r(r["tempo_medio"]), "taxa_cumprimento_sla_pct": _r(r["taxa_sla"]),
             "satisfacao_media": _r(r["satisfacao"], 2)} for r in rows]


# ---------------------------------------------------------------- Insights (diferencial)
def mapa_calor(f: Filtro) -> dict:
    where, params = f.where()
    matriz = [[0] * 24 for _ in range(7)]
    for row in get_db().execute(f"""SELECT CAST(strftime('%w', c.aberto_em) AS INTEGER) dow,
                                           CAST(strftime('%H', c.aberto_em) AS INTEGER) hora, COUNT(*) n
                                    FROM chamados c {where} GROUP BY dow, hora""", params):
        matriz[(row["dow"] + 6) % 7][row["hora"]] = row["n"]  # SQLite: 0=domingo -> 6
    maximo = max(max(l) for l in matriz)
    pico = None
    if maximo:
        d, h = next((d, h) for d in range(7) for h in range(24) if matriz[d][h] == maximo)
        pico = {"dia": DIAS_SEMANA[d], "hora": h, "quantidade": maximo}
    return {"dias": DIAS_SEMANA, "horas": list(range(24)), "matriz": matriz, "maximo": maximo, "pico": pico}


def sla_em_risco(f: Filtro, limite: int) -> dict:
    agora_dt = agora()
    filtro_ativos = Filtro(**{**f.__dict__, "status": [s for s in (f.status or STATUS_ATIVOS) if s in STATUS_ATIVOS]})
    if not filtro_ativos.status:
        return {"resumo": {"estourado": 0, "critico": 0, "atencao": 0, "no_prazo": 0}, "chamados": []}
    where, params = filtro_ativos.where()
    rows = get_db().execute(f"""
        SELECT c.id, c.titulo, c.status, c.prioridade, c.aberto_em, c.prazo_sla,
               t.nome AS tipo, tc.nome AS tecnico, s.nome AS setor
        FROM chamados c JOIN tipos_chamado t ON t.id = c.tipo_id JOIN setores s ON s.id = c.setor_id
        LEFT JOIN tecnicos tc ON tc.id = c.tecnico_id {where}""", params).fetchall()
    itens, resumo = [], {"estourado": 0, "critico": 0, "atencao": 0, "no_prazo": 0}
    for r in rows:
        aberto, prazo = parse(r["aberto_em"]), parse(r["prazo_sla"])
        janela = max((prazo - aberto).total_seconds(), 1)
        consumido = (agora_dt - aberto).total_seconds() / janela * 100
        restantes = (prazo - agora_dt).total_seconds() / 3600
        nivel = "estourado" if restantes < 0 else "critico" if consumido >= 75 else \
            "atencao" if consumido >= 50 else "no_prazo"
        resumo[nivel] += 1
        itens.append({"id": r["id"], "titulo": r["titulo"], "status": r["status"], "prioridade": r["prioridade"],
                      "tipo": r["tipo"], "setor": r["setor"], "tecnico": r["tecnico"], "prazo_sla": r["prazo_sla"],
                      "horas_restantes": _r(restantes), "sla_consumido_pct": _r(consumido), "nivel": nivel})
    itens.sort(key=lambda x: x["horas_restantes"])
    return {"resumo": resumo, "chamados": [i for i in itens if i["nivel"] != "no_prazo"][:limite]}


def saude_operacao(f: Filtro) -> dict:
    """Índice de Saúde (0-100): 40% cumprimento de SLA + 30% satisfação + 30% backlog sem atraso."""
    ind = indicadores(f)
    sla = ind["taxa_cumprimento_sla_pct"]
    sat = ind["satisfacao_media"]
    comp_sla = sla if sla is not None else 100.0
    comp_sat = (sat - 1) / 4 * 100 if sat is not None else 100.0
    comp_backlog = 100.0 - (ind["atrasados"] * 100 / ind["backlog"]) if ind["backlog"] else 100.0
    score = round(0.4 * comp_sla + 0.3 * comp_sat + 0.3 * comp_backlog, 1)

    alertas = []
    if comp_sla < 80:
        alertas.append(f"Cumprimento de SLA em {comp_sla:.1f}% (meta: 80%).")
    if ind["backlog"] and comp_backlog < 70:
        alertas.append(f"{ind['atrasados']} de {ind['backlog']} chamados da fila estão com SLA estourado.")
    if sat is not None and sat < 3.5:
        alertas.append(f"Satisfação média baixa ({sat:.2f}/5).")
    return {
        "indice": score,
        "classificacao": classificar_saude(score),
        "componentes": {"sla": round(comp_sla, 1), "satisfacao": round(comp_sat, 1),
                        "backlog_sem_atraso": round(comp_backlog, 1)},
        "pesos": {"sla": 0.4, "satisfacao": 0.3, "backlog_sem_atraso": 0.3},
        "alertas": alertas,
    }


# ---------------------------------------------------------------- Chamados (CRUD parcial - RF07)
ORDENACOES = {
    "id": "c.id", "aberto_em": "c.aberto_em", "prazo_sla": "c.prazo_sla", "status": "c.status",
    "prioridade": "CASE c.prioridade WHEN 'critica' THEN 4 WHEN 'alta' THEN 3 WHEN 'media' THEN 2 ELSE 1 END",
}

SELECT_CHAMADO = """
    SELECT c.*, t.nome AS tipo, s.nome AS setor, tc.nome AS tecnico
    FROM chamados c JOIN tipos_chamado t ON t.id = c.tipo_id JOIN setores s ON s.id = c.setor_id
    LEFT JOIN tecnicos tc ON tc.id = c.tecnico_id"""


def _serializar(r) -> dict:
    d = {k: r[k] for k in ("id", "titulo", "descricao", "tipo_id", "tipo", "setor_id", "setor", "tecnico_id",
                           "tecnico", "prioridade", "status", "aberto_em", "prazo_sla", "resolvido_em",
                           "satisfacao", "atualizado_em")}
    if r["resolvido_em"]:
        d["horas_resolucao"] = _r((parse(r["resolvido_em"]) - parse(r["aberto_em"])).total_seconds() / 3600)
        d["dentro_sla"] = r["resolvido_em"] <= r["prazo_sla"]
    else:
        d["horas_resolucao"] = None
        d["dentro_sla"] = None if r["status"] == "cancelado" else fmt(agora()) <= r["prazo_sla"]
    return d


def listar_chamados(f: Filtro, busca: str | None, pagina: int, por_pagina: int, ordenar: str, direcao: str) -> dict:
    where, params = f.where()
    if busca:
        where += (" AND " if where else " WHERE ") + "(c.titulo LIKE ? OR CAST(c.id AS TEXT) = ?)"
        params += [f"%{busca}%", busca]
    total = get_db().execute(f"SELECT COUNT(*) FROM chamados c {where}", params).fetchone()[0]
    rows = get_db().execute(f"{SELECT_CHAMADO} {where} ORDER BY {ORDENACOES[ordenar]} {direcao.upper()}, c.id DESC "
                            f"LIMIT ? OFFSET ?", [*params, por_pagina, (pagina - 1) * por_pagina]).fetchall()
    return {"pagina": pagina, "por_pagina": por_pagina, "total": total,
            "total_paginas": (total + por_pagina - 1) // por_pagina, "dados": [_serializar(r) for r in rows]}


def obter_chamado(chamado_id: int) -> dict:
    db = get_db()
    r = db.execute(f"{SELECT_CHAMADO} WHERE c.id = ?", (chamado_id,)).fetchone()
    if not r:
        raise NaoEncontrado(f"Chamado {chamado_id} não encontrado.")
    d = _serializar(r)
    d["consideracoes_tecnicas"] = [dict(x) for x in db.execute(
        """SELECT ct.id, ct.texto, ct.criado_em, ct.tecnico_id, tc.nome AS tecnico
           FROM consideracoes_tecnicas ct JOIN tecnicos tc ON tc.id = ct.tecnico_id
           WHERE ct.chamado_id = ? ORDER BY ct.criado_em, ct.id""", (chamado_id,))]
    return d


def _texto(corpo, campo, minimo, maximo, obrigatorio=True):
    valor = corpo.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obrigatorio:
            return None, f"'{campo}' é obrigatório."
        return None, None
    if not isinstance(valor, str):
        return None, f"'{campo}' deve ser texto."
    valor = " ".join(valor.split()) if campo == "titulo" else valor.strip()
    if not (minimo <= len(valor) <= maximo):
        return None, f"'{campo}' deve ter entre {minimo} e {maximo} caracteres."
    return valor, None


def _id_existente(corpo, campo, tabela, obrigatorio):
    valor = corpo.get(campo)
    if valor is None:
        return None, (f"'{campo}' é obrigatório." if obrigatorio else None)
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None, f"'{campo}' deve ser um número inteiro."
    if not get_db().execute(f"SELECT 1 FROM {tabela} WHERE id = ?", (valor,)).fetchone():
        return None, f"'{campo}' = {valor} não existe."
    return valor, None


def criar_chamado(corpo: dict) -> dict:
    erros = {}
    titulo, e = _texto(corpo, "titulo", 3, 120)
    if e: erros["titulo"] = e
    descricao, e = _texto(corpo, "descricao", 0, 2000, obrigatorio=False)
    if e: erros["descricao"] = e
    tipo_id, e = _id_existente(corpo, "tipo_id", "tipos_chamado", True)
    if e: erros["tipo_id"] = e
    setor_id, e = _id_existente(corpo, "setor_id", "setores", True)
    if e: erros["setor_id"] = e
    tecnico_id, e = _id_existente(corpo, "tecnico_id", "tecnicos", False)
    if e: erros["tecnico_id"] = e
    prioridade = corpo.get("prioridade", "media")
    if prioridade not in PRIORIDADES:
        erros["prioridade"] = f"Use um destes valores: {', '.join(PRIORIDADES)}."
    if erros:
        raise ErroApi(422, "VALIDACAO", "Dados do chamado inválidos.", erros)

    db = get_db()
    sla = db.execute("SELECT sla_horas FROM tipos_chamado WHERE id = ?", (tipo_id,)).fetchone()[0]
    agora_dt = agora()
    cur = db.execute("""INSERT INTO chamados (titulo, descricao, tipo_id, setor_id, tecnico_id, prioridade, status,
                                              aberto_em, prazo_sla, atualizado_em)
                        VALUES (?,?,?,?,?,?, 'aberto', ?,?,?)""",
                     (titulo, descricao, tipo_id, setor_id, tecnico_id, prioridade, fmt(agora_dt),
                      fmt(calcular_prazo_sla(agora_dt, sla, prioridade)), fmt(agora_dt)))
    db.commit()
    return obter_chamado(cur.lastrowid)


def atualizar_status(chamado_id: int, corpo: dict) -> dict:
    db = get_db()
    atual = db.execute("SELECT status FROM chamados WHERE id = ?", (chamado_id,)).fetchone()
    if not atual:
        raise NaoEncontrado(f"Chamado {chamado_id} não encontrado.")
    novo = corpo.get("status")
    if novo not in STATUS:
        raise ErroApi(422, "VALIDACAO", "Status inválido.", {"status": f"Use um destes valores: {', '.join(STATUS)}."})
    if not transicao_valida(atual["status"], novo):
        raise ErroApi(409, "TRANSICAO_INVALIDA",
                      f"Não é permitido mudar de '{atual['status']}' para '{novo}'.",
                      {"status_atual": atual["status"], "permitidos": sorted(TRANSICOES[atual["status"]])})
    satisfacao = corpo.get("satisfacao")
    if satisfacao is not None and (novo != "resolvido" or isinstance(satisfacao, bool)
                                   or not isinstance(satisfacao, int) or not 1 <= satisfacao <= 5):
        raise ErroApi(422, "VALIDACAO", "Satisfação inválida.",
                      {"satisfacao": "Inteiro de 1 a 5, enviado apenas ao resolver o chamado."})
    tecnico_id, e = _id_existente(corpo, "tecnico_id", "tecnicos", False)
    if e:
        raise ErroApi(422, "VALIDACAO", "Técnico inválido.", {"tecnico_id": e})

    agora_txt = fmt(agora())
    resolvido_em = agora_txt if novo == "resolvido" else None
    db.execute("""UPDATE chamados SET status = ?, resolvido_em = ?, satisfacao = ?,
                         tecnico_id = COALESCE(?, tecnico_id), atualizado_em = ? WHERE id = ?""",
               (novo, resolvido_em, satisfacao if novo == "resolvido" else None, tecnico_id, agora_txt, chamado_id))
    db.commit()
    return obter_chamado(chamado_id)


def adicionar_consideracao(chamado_id: int, corpo: dict) -> dict:
    db = get_db()
    if not db.execute("SELECT 1 FROM chamados WHERE id = ?", (chamado_id,)).fetchone():
        raise NaoEncontrado(f"Chamado {chamado_id} não encontrado.")
    erros = {}
    texto, e = _texto(corpo, "texto", 5, 1000)
    if e: erros["texto"] = e
    tecnico_id, e = _id_existente(corpo, "tecnico_id", "tecnicos", True)
    if e: erros["tecnico_id"] = e
    if erros:
        raise ErroApi(422, "VALIDACAO", "Consideração técnica inválida.", erros)
    agora_txt = fmt(agora())
    cur = db.execute("INSERT INTO consideracoes_tecnicas (chamado_id, tecnico_id, texto, criado_em) VALUES (?,?,?,?)",
                     (chamado_id, tecnico_id, texto, agora_txt))
    db.execute("UPDATE chamados SET atualizado_em = ? WHERE id = ?", (agora_txt, chamado_id))
    db.commit()
    r = db.execute("""SELECT ct.id, ct.chamado_id, ct.texto, ct.criado_em, ct.tecnico_id, tc.nome AS tecnico
                      FROM consideracoes_tecnicas ct JOIN tecnicos tc ON tc.id = ct.tecnico_id WHERE ct.id = ?""",
                   (cur.lastrowid,)).fetchone()
    return dict(r)


def opcoes_filtros() -> dict:
    db = get_db()
    limites = db.execute("SELECT MIN(date(aberto_em)) ini, MAX(date(aberto_em)) fim FROM chamados").fetchone()
    return {
        "tipos": [dict(r) for r in db.execute("SELECT id, nome, sla_horas FROM tipos_chamado ORDER BY nome")],
        "tecnicos": [dict(r) for r in db.execute("SELECT id, nome, nivel FROM tecnicos WHERE ativo = 1 ORDER BY nome")],
        "setores": [dict(r) for r in db.execute("SELECT id, nome FROM setores ORDER BY nome")],
        "status": [{"valor": s, "rotulo": ROTULO_STATUS[s]} for s in STATUS],
        "prioridades": list(PRIORIDADES),
        "periodo_disponivel": {"data_inicio": limites["ini"], "data_fim": limites["fim"]},
    }
