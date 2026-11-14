"""Inicia a API + Dashboard.  Uso:  python run.py   (acesse http://localhost:5000)

Na primeira execução o banco SQLite é criado e populado automaticamente.
Use  python run.py --reset  para recriar os dados de exemplo.
"""
import sys
from pathlib import Path

from app import create_app, inicializar_banco

app = create_app()

if __name__ == "__main__":
    if "--reset" in sys.argv or not Path(app.config["DATABASE"]).exists():
        inicializar_banco(app)
        print(f"[Thindesk] Banco criado e populado em {app.config['DATABASE']}")
    print("[Thindesk] Dashboard: http://localhost:5000   |   API: http://localhost:5000/api/v1/health")
    app.run(host="0.0.0.0", port=5000, debug=False)
