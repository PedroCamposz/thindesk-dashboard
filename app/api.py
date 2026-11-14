"""Endpoints REST da API Thindesk Insight (prefixo /api/v1)."""
from flask import Blueprint, jsonify, request, url_for

from . import servicos
from .db import agora, fmt, get_db
from .erros import ErroApi, ParametroInvalido
from .filtros import ler_filtro, ler_inteiro, periodo_padrao

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _ok(dados, filtro=None, status=200):
    corpo = {"dados": dados, "meta": {"gerado_em": fmt(agora())}}
    if filtro is not None:
        corpo["meta"]["filtros_aplicados"] = filtro.como_dict()
    return jsonify(corpo), status


def _corpo_json() -> dict:
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        raise ErroApi(400, "JSON_INVALIDO", "O corpo da requisição deve ser um objeto JSON válido.")
    return corpo


@bp.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ------------------------------------------------------------------ utilitários
@bp.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return _ok({"status": "ok", "banco": "conectado", "versao": "1.0.0"})


@bp.get("/filtros")
def filtros():
    return _ok(servicos.opcoes_filtros())


# ------------------------------------------------------------------ RF01
@bp.get("/indicadores")
def indicadores():
    f = ler_filtro(request.args)
    return _ok(servicos.indicadores(f), f)


# ------------------------------------------------------------------ RF02
@bp.get("/chamados/periodo")
def chamados_periodo():
    f = ler_filtro(request.args)
    agrupamento = (request.args.get("agrupamento") or "dia").lower()
    if agrupamento not in ("dia", "semana", "mes"):
        raise ParametroInvalido("'agrupamento' deve ser 'dia', 'semana' ou 'mes'.",
                                {"parametro": "agrupamento", "permitidos": ["dia", "semana", "mes"]})
    inicio, fim = periodo_padrao(f, agora().date())
    if inicio > fim:
        raise ParametroInvalido("'data_inicio' não pode ser maior que 'data_fim'.")
    if (fim - inicio).days > 731:
        raise ParametroInvalido("O intervalo máximo para séries temporais é de 2 anos.")
    return _ok(servicos.serie_periodo(f, inicio, fim, agrupamento), f)


# ------------------------------------------------------------------ RF03
@bp.get("/chamados/situacao")
def chamados_situacao():
    f = ler_filtro(request.args)
    return _ok(servicos.situacao(f), f)


# ------------------------------------------------------------------ RF04
@bp.get("/tipos/ranking")
def tipos_ranking():
    f = ler_filtro(request.args)
    limite = ler_inteiro(request.args.get("limite"), "limite", 1, 50, padrao=5)
    return _ok(servicos.ranking_tipos(f, limite), f)


@bp.get("/tecnicos/desempenho")
def tecnicos_desempenho():
    f = ler_filtro(request.args)
    return _ok(servicos.desempenho_tecnicos(f), f)


# ------------------------------------------------------------------ Insights (diferencial)
@bp.get("/insights/saude")
def insights_saude():
    f = ler_filtro(request.args)
    return _ok(servicos.saude_operacao(f), f)


@bp.get("/insights/mapa-calor")
def insights_mapa_calor():
    f = ler_filtro(request.args)
    return _ok(servicos.mapa_calor(f), f)


@bp.get("/insights/sla-risco")
def insights_sla_risco():
    f = ler_filtro(request.args)
    limite = ler_inteiro(request.args.get("limite"), "limite", 1, 100, padrao=10)
    return _ok(servicos.sla_em_risco(f, limite), f)


# ------------------------------------------------------------------ Chamados
@bp.get("/chamados")
def listar_chamados():
    f = ler_filtro(request.args)
    pagina = ler_inteiro(request.args.get("pagina"), "pagina", 1, 100000, padrao=1)
    por_pagina = ler_inteiro(request.args.get("por_pagina"), "por_pagina", 1, 100, padrao=20)
    ordenar = request.args.get("ordenar", "aberto_em")
    if ordenar not in servicos.ORDENACOES:
        raise ParametroInvalido("Campo de ordenação inválido.",
                                {"parametro": "ordenar", "permitidos": list(servicos.ORDENACOES)})
    direcao = request.args.get("direcao", "desc").lower()
    if direcao not in ("asc", "desc"):
        raise ParametroInvalido("'direcao' deve ser 'asc' ou 'desc'.")
    busca = (request.args.get("busca") or "").strip()[:100] or None
    return _ok(servicos.listar_chamados(f, busca, pagina, por_pagina, ordenar, direcao), f)


@bp.post("/chamados")
def criar_chamado():
    chamado = servicos.criar_chamado(_corpo_json())
    resp, status = _ok(chamado, status=201)
    resp.headers["Location"] = url_for("api.obter_chamado", chamado_id=chamado["id"])
    return resp, status


@bp.get("/chamados/<int:chamado_id>")
def obter_chamado(chamado_id):
    return _ok(servicos.obter_chamado(chamado_id))


@bp.patch("/chamados/<int:chamado_id>/status")
def atualizar_status(chamado_id):
    return _ok(servicos.atualizar_status(chamado_id, _corpo_json()))


@bp.post("/chamados/<int:chamado_id>/consideracoes")
def adicionar_consideracao(chamado_id):
    return _ok(servicos.adicionar_consideracao(chamado_id, _corpo_json()), status=201)
