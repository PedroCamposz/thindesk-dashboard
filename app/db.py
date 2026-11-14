"""Acesso ao banco SQLite (conexão por requisição + inicialização)."""
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import current_app, g

FORMATO_DATA_HORA = "%Y-%m-%d %H:%M:%S"
SCHEMA = Path(__file__).with_name("schema.sql")


def agora() -> datetime:
    """'Agora' da aplicação. Pode ser fixado via config NOW (útil nos testes)."""
    fixo = current_app.config.get("NOW")
    return fixo if fixo else datetime.now().replace(microsecond=0)


def fmt(dt: datetime) -> str:
    return dt.strftime(FORMATO_DATA_HORA)


def parse(texto: str) -> datetime:
    return datetime.strptime(texto, FORMATO_DATA_HORA)


def conectar(caminho: str) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = conectar(current_app.config["DATABASE"])
    return g.db


def fechar_db(_exc=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


def criar_schema(con: sqlite3.Connection):
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.commit()


def init_app(app):
    app.teardown_appcontext(fechar_db)
