"""Thindesk Insight - Dashboard Administrativo + API de chamados.

Autor: Pedro Henrique Campos - Sistemas de Informação (UMC)
"""
import os
from pathlib import Path

from flask import Flask, send_from_directory

from . import db, erros
from .api import bp as api_bp

RAIZ = Path(__file__).resolve().parent.parent


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.update(
        DATABASE=os.environ.get("THINDESK_DB", str(RAIZ / "instance" / "thindesk.db")),
        JSON_SORT_KEYS=False,
        NOW=None,
    )
    if config:
        app.config.update(config)
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    db.init_app(app)
    erros.registrar(app)
    app.register_blueprint(api_bp)

    @app.get("/")
    def dashboard():
        return send_from_directory(app.static_folder, "index.html")

    @app.cli.command("init-db")
    def init_db_cmd():
        """Recria o banco e popula com dados de exemplo."""
        inicializar_banco(app)
        print(f"Banco criado em {app.config['DATABASE']}")

    return app


def inicializar_banco(app: Flask, quantidade=900, dias=180, semente=2026):
    from datetime import datetime
    from .seed import popular

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    con = db.conectar(app.config["DATABASE"])
    try:
        db.criar_schema(con)
        referencia = app.config.get("NOW") or datetime.now().replace(microsecond=0)
        popular(con, referencia, quantidade, dias, semente)
    finally:
        con.close()
