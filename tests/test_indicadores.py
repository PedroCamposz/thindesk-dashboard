"""RF01, RF02, RF03, RF04 - indicadores, séries, situação e rankings."""


def dados(resp):
    assert resp.is_json
    return resp.get_json()["dados"]


# ------------------------------------------------------------------ RF01
def test_indicadores_valores_exatos(client_mini):
    r = client_mini.get("/api/v1/indicadores")
    assert r.status_code == 200
    d = dados(r)
    assert d["total_chamados"] == 5
    assert (d["abertos"], d["em_andamento"], d["aguardando"]) == (1, 1, 0)
    assert (d["resolvidos"], d["cancelados"]) == (2, 1)
    assert d["backlog"] == 2
    assert d["atrasados"] == 1                      # só o chamado 3 passou do prazo
    assert d["taxa_resolucao_pct"] == 40.0
    assert d["tempo_medio_resolucao_horas"] == 7.0  # (4h + 10h) / 2
    assert d["taxa_cumprimento_sla_pct"] == 50.0
    assert d["satisfacao_media"] == 4.0


def test_indicadores_comparacao_periodo_anterior(client_mini):
    d = dados(client_mini.get("/api/v1/indicadores?data_inicio=2026-11-10&data_fim=2026-11-14"))
    assert d["total_chamados"] == 5
    assert d["total_periodo_anterior"] == 0
    assert d["variacao_periodo_anterior_pct"] is None  # sem base de comparação


def test_indicadores_massa_completa_consistente(client):
    d = dados(client.get("/api/v1/indicadores"))
    soma = d["abertos"] + d["em_andamento"] + d["aguardando"] + d["resolvidos"] + d["cancelados"]
    assert soma == d["total_chamados"] > 0
    assert 0 <= d["taxa_cumprimento_sla_pct"] <= 100
    assert 1 <= d["satisfacao_media"] <= 5


def test_meta_informa_filtros_aplicados(client_mini):
    corpo = client_mini.get("/api/v1/indicadores?status=resolvido&tipo_id=1").get_json()
    assert corpo["meta"]["filtros_aplicados"] == {"status": ["resolvido"], "tipo_id": 1}
    assert "gerado_em" in corpo["meta"]


# ------------------------------------------------------------------ RF02
def test_periodo_por_dia_preenche_dias_sem_chamados(client_mini):
    d = dados(client_mini.get("/api/v1/chamados/periodo?data_inicio=2026-11-10&data_fim=2026-11-14"))
    assert [s["periodo"] for s in d["serie"]] == ["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14"]
    por_dia = {s["periodo"]: s for s in d["serie"]}
    assert por_dia["2026-11-10"]["abertos"] == 2 and por_dia["2026-11-10"]["resolvidos"] == 2
    assert por_dia["2026-11-10"]["taxa_sla_pct"] == 50.0
    assert por_dia["2026-11-10"]["tempo_medio_resolucao_horas"] == 7.0
    assert por_dia["2026-11-11"]["abertos"] == 0 and por_dia["2026-11-11"]["taxa_sla_pct"] is None
    assert d["totais"] == {"abertos": 5, "resolvidos": 2}


def test_periodo_por_semana_e_mes(client_mini):
    sem = dados(client_mini.get("/api/v1/chamados/periodo?agrupamento=semana&data_inicio=2026-11-10&data_fim=2026-11-14"))
    assert sem["serie"] == [{"periodo": "2026-11-09", "abertos": 5, "resolvidos": 2, "saldo": 3,
                             "taxa_sla_pct": 50.0, "tempo_medio_resolucao_horas": 7.0}]
    mes = dados(client_mini.get("/api/v1/chamados/periodo?agrupamento=mes&data_inicio=2026-10-01&data_fim=2026-11-30"))
    assert [s["periodo"] for s in mes["serie"]] == ["2026-10", "2026-11"]
    assert mes["serie"][1]["abertos"] == 5


def test_periodo_padrao_ultimos_30_dias(client):
    d = dados(client.get("/api/v1/chamados/periodo"))
    assert len(d["serie"]) == 30
    assert d["data_fim"] == "2026-11-14" and d["data_inicio"] == "2026-10-16"


# ------------------------------------------------------------------ RF03
def test_situacao_lista_todos_os_status(client_mini):
    d = dados(client_mini.get("/api/v1/chamados/situacao"))
    mapa = {s["status"]: s for s in d["status"]}
    assert set(mapa) == {"aberto", "em_andamento", "aguardando", "resolvido", "cancelado"}
    assert mapa["resolvido"]["quantidade"] == 2 and mapa["resolvido"]["percentual"] == 40.0
    assert mapa["aguardando"]["quantidade"] == 0
    assert d["backlog_por_prioridade"] == {"baixa": 0, "media": 2, "alta": 0, "critica": 0}


# ------------------------------------------------------------------ RF04
def test_ranking_tipos(client_mini):
    d = dados(client_mini.get("/api/v1/tipos/ranking"))
    assert d["total_geral"] == 5
    assert len(d["ranking"]) == 1  # 'Hardware' não tem chamados
    top = d["ranking"][0]
    assert (top["posicao"], top["tipo"], top["total"], top["participacao_pct"]) == (1, "Rede", 5, 100.0)


def test_ranking_tipos_ordenado_e_limitado(client):
    ranking = dados(client.get("/api/v1/tipos/ranking?limite=3"))["ranking"]
    assert len(ranking) == 3
    totais = [t["total"] for t in ranking]
    assert totais == sorted(totais, reverse=True)


def test_desempenho_tecnicos(client_mini):
    lista = dados(client_mini.get("/api/v1/tecnicos/desempenho"))
    assert [t["nome"] for t in lista] == ["Ana", "Bruno"]
    ana = lista[0]
    assert (ana["atribuidos"], ana["resolvidos"], ana["em_fila"]) == (2, 1, 1)
    assert ana["taxa_cumprimento_sla_pct"] == 100.0 and ana["satisfacao_media"] == 5.0
