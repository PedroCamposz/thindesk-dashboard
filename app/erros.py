"""Erros padronizados da API. Todo erro sai no formato:
{"erro": {"codigo": "...", "mensagem": "...", "detalhes": {...}}}
"""
from flask import jsonify, request
from werkzeug.exceptions import HTTPException


class ErroApi(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, detalhes=None):
        super().__init__(mensagem)
        self.status, self.codigo, self.mensagem, self.detalhes = status, codigo, mensagem, detalhes


class ParametroInvalido(ErroApi):
    def __init__(self, mensagem, detalhes=None):
        super().__init__(400, "PARAMETRO_INVALIDO", mensagem, detalhes)


class NaoEncontrado(ErroApi):
    def __init__(self, mensagem):
        super().__init__(404, "NAO_ENCONTRADO", mensagem)


def _resposta(status, codigo, mensagem, detalhes=None):
    corpo = {"erro": {"codigo": codigo, "mensagem": mensagem}}
    if detalhes:
        corpo["erro"]["detalhes"] = detalhes
    return jsonify(corpo), status


def registrar(app):
    @app.errorhandler(ErroApi)
    def _erro_api(e: ErroApi):
        return _resposta(e.status, e.codigo, e.mensagem, e.detalhes)

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        if not request.path.startswith("/api"):
            return e
        codigos = {404: ("ROTA_NAO_ENCONTRADA", "Endpoint não encontrado."),
                   405: ("METODO_NAO_PERMITIDO", "Método HTTP não permitido para este endpoint."),
                   400: ("REQUISICAO_INVALIDA", "Requisição malformada."),
                   415: ("TIPO_CONTEUDO_INVALIDO", "Envie o corpo como application/json.")}
        codigo, msg = codigos.get(e.code, ("ERRO_HTTP", e.description))
        return _resposta(e.code, codigo, msg)

    @app.errorhandler(Exception)
    def _inesperado(e):
        app.logger.exception("Erro inesperado: %s", e)
        return _resposta(500, "ERRO_INTERNO", "Erro interno no servidor. Tente novamente.")
