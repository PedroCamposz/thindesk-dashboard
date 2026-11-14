"""Chamados: listagem, detalhe e atualização de dados (RF07)."""


def corpo(resp):
    return resp.get_json()


# ------------------------------------------------------------------ listagem / detalhe
def test_listagem_paginada(client):
    d = corpo(client.get("/api/v1/chamados?por_pagina=7&pagina=2"))["dados"]
    assert d["pagina"] == 2 and d["por_pagina"] == 7 and len(d["dados"]) == 7
    assert d["total_paginas"] == -(-d["total"] // 7)


def test_listagem_ordenada_por_data(client_mini):
    d = corpo(client_mini.get("/api/v1/chamados?ordenar=aberto_em&direcao=asc"))["dados"]["dados"]
    datas = [c["aberto_em"] for c in d]
    assert datas == sorted(datas)


def test_busca_por_titulo_e_numero(client_mini):
    assert corpo(client_mini.get("/api/v1/chamados?busca=vpn"))["dados"]["total"] == 1
    assert corpo(client_mini.get("/api/v1/chamados?busca=4"))["dados"]["dados"][0]["titulo"] == "Rede lenta"


def test_detalhe_com_consideracoes_tecnicas(client_mini):
    r = client_mini.get("/api/v1/chamados/1")
    assert r.status_code == 200
    c = corpo(r)["dados"]
    assert c["tipo"] == "Rede" and c["setor"] == "TI" and c["tecnico"] == "Ana"
    assert c["horas_resolucao"] == 4.0 and c["dentro_sla"] is True
    assert c["consideracoes_tecnicas"][0]["texto"] == "Roteador reiniciado."


def test_detalhe_inexistente_404(client_mini):
    r = client_mini.get("/api/v1/chamados/9999")
    assert r.status_code == 404 and corpo(r)["erro"]["codigo"] == "NAO_ENCONTRADO"


# ------------------------------------------------------------------ criação
def test_criar_chamado_calcula_sla_pela_prioridade(client_mini):
    r = client_mini.post("/api/v1/chamados", json={"titulo": "  Switch   queimado ", "tipo_id": 1, "setor_id": 1,
                                                    "prioridade": "critica"})
    assert r.status_code == 201
    c = corpo(r)["dados"]
    assert r.headers["Location"] == f"/api/v1/chamados/{c['id']}"
    assert c["titulo"] == "Switch queimado"         # espaços normalizados
    assert c["status"] == "aberto" and c["tecnico_id"] is None
    assert c["aberto_em"] == "2026-11-14 12:00:00"
    assert c["prazo_sla"] == "2026-11-14 14:00:00"  # 8h x 0,25 (crítica) = 2h
    # o novo chamado já entra nos indicadores
    assert corpo(client_mini.get("/api/v1/indicadores"))["dados"]["total_chamados"] == 6


def test_criar_chamado_validacao_422(client_mini):
    r = client_mini.post("/api/v1/chamados", json={"titulo": "x", "tipo_id": 99, "prioridade": "urgente",
                                                    "tecnico_id": "1"})
    assert r.status_code == 422
    det = corpo(r)["erro"]["detalhes"]
    assert set(det) == {"titulo", "tipo_id", "setor_id", "prioridade", "tecnico_id"}


def test_criar_chamado_json_invalido_400(client_mini):
    r = client_mini.post("/api/v1/chamados", data="isso não é json", content_type="application/json")
    assert r.status_code == 400 and corpo(r)["erro"]["codigo"] == "JSON_INVALIDO"
    r = client_mini.post("/api/v1/chamados", json=[1, 2, 3])
    assert r.status_code == 400


# ------------------------------------------------------------------ status
def test_fluxo_completo_de_status(client_mini):
    r = client_mini.patch("/api/v1/chamados/3/status", json={"status": "em_andamento", "tecnico_id": 2})
    assert r.status_code == 200
    c = corpo(r)["dados"]
    assert c["status"] == "em_andamento" and c["tecnico"] == "Bruno"

    r = client_mini.patch("/api/v1/chamados/3/status", json={"status": "resolvido", "satisfacao": 4})
    c = corpo(r)["dados"]
    assert c["status"] == "resolvido" and c["resolvido_em"] == "2026-11-14 12:00:00" and c["satisfacao"] == 4
    assert c["dentro_sla"] is False  # prazo era 10:00

    r = client_mini.patch("/api/v1/chamados/3/status", json={"status": "em_andamento"})  # reabertura
    c = corpo(r)["dados"]
    assert c["resolvido_em"] is None and c["satisfacao"] is None


def test_transicao_invalida_409(client_mini):
    r = client_mini.patch("/api/v1/chamados/3/status", json={"status": "resolvido"})  # aberto -> resolvido
    assert r.status_code == 409
    e = corpo(r)["erro"]
    assert e["codigo"] == "TRANSICAO_INVALIDA" and e["detalhes"]["permitidos"] == ["cancelado", "em_andamento"]
    assert client_mini.patch("/api/v1/chamados/5/status", json={"status": "aberto"}).status_code == 409  # cancelado


def test_status_inexistente_e_satisfacao_invalida_422(client_mini):
    assert client_mini.patch("/api/v1/chamados/4/status", json={"status": "fechado"}).status_code == 422
    r = client_mini.patch("/api/v1/chamados/4/status", json={"status": "resolvido", "satisfacao": 9})
    assert r.status_code == 422 and "satisfacao" in corpo(r)["erro"]["detalhes"]
    r = client_mini.patch("/api/v1/chamados/4/status", json={"status": "aguardando", "satisfacao": 5})
    assert r.status_code == 422


def test_status_chamado_inexistente_404(client_mini):
    assert client_mini.patch("/api/v1/chamados/777/status", json={"status": "cancelado"}).status_code == 404


# ------------------------------------------------------------------ considerações técnicas
def test_adicionar_consideracao(client_mini):
    r = client_mini.post("/api/v1/chamados/4/consideracoes",
                         json={"tecnico_id": 1, "texto": "Trocado o cabo de rede do switch."})
    assert r.status_code == 201
    assert corpo(r)["dados"]["tecnico"] == "Ana"
    detalhe = corpo(client_mini.get("/api/v1/chamados/4"))["dados"]
    assert detalhe["consideracoes_tecnicas"][-1]["texto"] == "Trocado o cabo de rede do switch."


def test_consideracao_invalida(client_mini):
    r = client_mini.post("/api/v1/chamados/4/consideracoes", json={"texto": "ok"})
    assert r.status_code == 422 and set(corpo(r)["erro"]["detalhes"]) == {"texto", "tecnico_id"}
    assert client_mini.post("/api/v1/chamados/999/consideracoes",
                            json={"tecnico_id": 1, "texto": "teste longo"}).status_code == 404
