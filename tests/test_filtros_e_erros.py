"""RF05 (filtros) e tratamento de erros da API."""
import pytest


def erro(resp):
    assert resp.is_json
    return resp.get_json()["erro"]


@pytest.mark.parametrize("query,esperado", [
    ("status=resolvido", 2),
    ("status=aberto,em_andamento", 2),
    ("tecnico_id=2", 2),
    ("setor_id=2", 2),
    ("prioridade=media", 5),
    ("prioridade=critica", 0),
    ("data_inicio=2026-11-14", 2),
    ("data_fim=2026-11-10", 2),
    ("data_inicio=2026-11-12&data_fim=2026-11-12", 1),
    ("tipo_id=2", 0),
])
def test_filtros_reduzem_resultado(client_mini, query, esperado):
    r = client_mini.get(f"/api/v1/indicadores?{query}")
    assert r.status_code == 200
    assert r.get_json()["dados"]["total_chamados"] == esperado


def test_filtros_combinados(client_mini):
    d = client_mini.get("/api/v1/chamados?status=resolvido&tecnico_id=1").get_json()["dados"]
    assert d["total"] == 1 and d["dados"][0]["titulo"] == "Sem internet"


def test_endpoint_de_opcoes_de_filtro(client):
    d = client.get("/api/v1/filtros").get_json()["dados"]
    assert len(d["tipos"]) == 8 and len(d["tecnicos"]) == 6 and len(d["setores"]) == 7
    assert d["prioridades"] == ["baixa", "media", "alta", "critica"]
    assert d["periodo_disponivel"]["data_fim"] == "2026-11-14"


@pytest.mark.parametrize("query,trecho", [
    ("data_inicio=14/11/2026", "AAAA-MM-DD"),
    ("data_inicio=2026-11-14&data_fim=2026-11-01", "maior"),
    ("status=fechado", "status"),
    ("prioridade=urgente", "prioridade"),
    ("tipo_id=abc", "inteiro"),
    ("tipo_id=999", "não existe"),
    ("tecnico_id=0", "entre"),
])
def test_filtros_invalidos_retornam_400(client_mini, query, trecho):
    r = client_mini.get(f"/api/v1/indicadores?{query}")
    assert r.status_code == 400
    e = erro(r)
    assert e["codigo"] == "PARAMETRO_INVALIDO"
    assert trecho in e["mensagem"]


def test_agrupamento_invalido(client_mini):
    r = client_mini.get("/api/v1/chamados/periodo?agrupamento=ano")
    assert r.status_code == 400 and "agrupamento" in erro(r)["mensagem"]


def test_limite_fora_da_faixa(client_mini):
    assert client_mini.get("/api/v1/tipos/ranking?limite=0").status_code == 400
    assert client_mini.get("/api/v1/tipos/ranking?limite=51").status_code == 400


def test_paginacao_e_ordenacao_invalidas(client_mini):
    assert erro(client_mini.get("/api/v1/chamados?pagina=0"))["codigo"] == "PARAMETRO_INVALIDO"
    assert erro(client_mini.get("/api/v1/chamados?por_pagina=500"))["codigo"] == "PARAMETRO_INVALIDO"
    assert erro(client_mini.get("/api/v1/chamados?ordenar=senha"))["codigo"] == "PARAMETRO_INVALIDO"
    assert erro(client_mini.get("/api/v1/chamados?direcao=lado"))["codigo"] == "PARAMETRO_INVALIDO"


def test_tentativa_de_sql_injection_e_tratada(client_mini):
    r = client_mini.get("/api/v1/chamados?busca=' OR 1=1 --")
    assert r.status_code == 200 and r.get_json()["dados"]["total"] == 0
    assert client_mini.get("/api/v1/indicadores?status=aberto'--").status_code == 400


def test_rota_inexistente_404_json(client_mini):
    r = client_mini.get("/api/v1/nao-existe")
    assert r.status_code == 404 and erro(r)["codigo"] == "ROTA_NAO_ENCONTRADA"


def test_metodo_nao_permitido_405_json(client_mini):
    r = client_mini.delete("/api/v1/indicadores")
    assert r.status_code == 405 and erro(r)["codigo"] == "METODO_NAO_PERMITIDO"


def test_health_e_cors(client_mini):
    r = client_mini.get("/api/v1/health")
    assert r.status_code == 200 and r.get_json()["dados"]["banco"] == "conectado"
    assert r.headers["Access-Control-Allow-Origin"] == "*"


def test_dashboard_e_arquivos_estaticos(client_mini):
    r = client_mini.get("/")
    assert r.status_code == 200 and b"Thindesk Insight" in r.data and b"Pedro Henrique Campos" in r.data
    for arq in ("js/api.js", "js/graficos.js", "js/app.js", "css/style.css"):
        assert client_mini.get(f"/static/{arq}").status_code == 200
