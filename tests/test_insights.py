"""Diferenciais: Índice de Saúde, Radar de SLA e Mapa de calor."""
from app.regras import calcular_prazo_sla, classificar_saude, transicao_valida
from datetime import datetime


def dados(resp):
    assert resp.status_code == 200
    return resp.get_json()["dados"]


def test_indice_de_saude_calculo(client_mini):
    d = dados(client_mini.get("/api/v1/insights/saude"))
    # SLA 50 | satisfação (4-1)/4 = 75 | fila sem atraso 1 - 1/2 = 50
    assert d["componentes"] == {"sla": 50.0, "satisfacao": 75.0, "backlog_sem_atraso": 50.0}
    assert d["indice"] == 57.5  # 0,4*50 + 0,3*75 + 0,3*50
    assert d["classificacao"] == "Atenção"
    assert len(d["alertas"]) == 2


def test_indice_de_saude_sem_dados(client_mini):
    d = dados(client_mini.get("/api/v1/insights/saude?tipo_id=2"))
    assert d["indice"] == 100.0 and d["alertas"] == []


def test_radar_de_sla(client_mini):
    d = dados(client_mini.get("/api/v1/insights/sla-risco"))
    assert d["resumo"] == {"estourado": 1, "critico": 0, "atencao": 1, "no_prazo": 0}
    primeiro, segundo = d["chamados"]
    assert primeiro["id"] == 3 and primeiro["nivel"] == "estourado" and primeiro["horas_restantes"] == -2.0
    assert segundo["id"] == 4 and segundo["nivel"] == "atencao" and segundo["sla_consumido_pct"] == 50.0


def test_radar_ignora_status_finalizados(client_mini):
    d = dados(client_mini.get("/api/v1/insights/sla-risco?status=resolvido"))
    assert d["chamados"] == [] and sum(d["resumo"].values()) == 0


def test_mapa_de_calor(client_mini):
    d = dados(client_mini.get("/api/v1/insights/mapa-calor"))
    assert d["dias"][0] == "Seg" and len(d["matriz"]) == 7 and all(len(l) == 24 for l in d["matriz"])
    assert d["matriz"][1][9] == 1 and d["matriz"][1][10] == 1  # terça 10/11, 9h e 10h
    assert d["matriz"][5][2] == 1                             # sábado 14/11, 2h
    assert sum(map(sum, d["matriz"])) == 5


def test_regras_de_negocio_unitarias():
    base = datetime(2026, 1, 1, 8, 0)
    assert calcular_prazo_sla(base, 8, "critica") == datetime(2026, 1, 1, 10, 0)
    assert calcular_prazo_sla(base, 8, "baixa") == datetime(2026, 1, 1, 20, 0)
    assert transicao_valida("aberto", "em_andamento") and not transicao_valida("cancelado", "aberto")
    assert [classificar_saude(v) for v in (90, 75, 55, 10)] == ["Excelente", "Boa", "Atenção", "Crítica"]


def test_seed_e_deterministico(tmp_path):
    from app import create_app, inicializar_banco
    agora = datetime(2026, 11, 14, 12, 0)
    resultados = []
    for i in range(2):
        app = create_app({"TESTING": True, "DATABASE": str(tmp_path / f"s{i}.db"), "NOW": agora})
        inicializar_banco(app)
        resultados.append(app.test_client().get("/api/v1/indicadores").get_json()["dados"])
    assert resultados[0] == resultados[1]
