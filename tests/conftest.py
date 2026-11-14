"""Fixtures de teste. Cada teste usa um banco SQLite temporário e isolado."""
from datetime import datetime

import pytest

from app import create_app, inicializar_banco
from app import db as dbmod

AGORA = datetime(2026, 11, 14, 12, 0, 0)


@pytest.fixture
def app(tmp_path):
    """App com a massa de dados completa (seed determinístico)."""
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "teste.db"), "NOW": AGORA})
    inicializar_banco(app)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def client_mini(tmp_path):
    """App com uma massa pequena e conhecida, para conferir os cálculos com valores exatos.

    Chamados (todos com tipo 'Rede' SLA 8h, prioridade média -> prazo = abertura + 8h):
      1. resolvido em 4h  (dentro do SLA)  satisfação 5  - aberto 10/11 09:00 (terça)
      2. resolvido em 10h (fora do SLA)    satisfação 3  - aberto 10/11 10:00
      3. aberto, prazo 14/11 10:00 -> estourado          - aberto 14/11 02:00
      4. em_andamento, aberto 14/11 08:00 (prazo 16:00)  -> 50% consumido = atenção
    "Agora" fixo nos testes: 14/11/2026 12:00 (sábado).
      5. cancelado                                        - aberto 12/11 09:00
    """
    caminho = str(tmp_path / "mini.db")
    app = create_app({"TESTING": True, "DATABASE": caminho, "NOW": AGORA})
    con = dbmod.conectar(caminho)
    dbmod.criar_schema(con)
    con.execute("INSERT INTO setores (nome) VALUES ('TI'), ('RH')")
    con.execute("INSERT INTO tipos_chamado (nome, sla_horas) VALUES ('Rede', 8), ('Hardware', 24)")
    con.execute("INSERT INTO tecnicos (nome, nivel) VALUES ('Ana', 'N2'), ('Bruno', 'N1')")
    linhas = [
        ("Sem internet", 1, 1, 1, "media", "resolvido", "2026-11-10 09:00:00", "2026-11-10 17:00:00", "2026-11-10 13:00:00", 5),
        ("Wi-Fi caindo", 1, 2, 2, "media", "resolvido", "2026-11-10 10:00:00", "2026-11-10 18:00:00", "2026-11-10 20:00:00", 3),
        ("VPN fora", 1, 1, None, "media", "aberto", "2026-11-14 02:00:00", "2026-11-14 10:00:00", None, None),
        ("Rede lenta", 1, 1, 1, "media", "em_andamento", "2026-11-14 08:00:00", "2026-11-14 16:00:00", None, None),
        ("Cabo rompido", 1, 2, 2, "media", "cancelado", "2026-11-12 09:00:00", "2026-11-12 17:00:00", None, None),
    ]
    for l in linhas:
        con.execute("""INSERT INTO chamados (titulo, tipo_id, setor_id, tecnico_id, prioridade, status, aberto_em,
                       prazo_sla, resolvido_em, satisfacao, atualizado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (*l, l[6]))
    con.execute("INSERT INTO consideracoes_tecnicas (chamado_id, tecnico_id, texto, criado_em) "
                "VALUES (1, 1, 'Roteador reiniciado.', '2026-11-10 12:00:00')")
    con.commit()
    con.close()
    return app.test_client()
