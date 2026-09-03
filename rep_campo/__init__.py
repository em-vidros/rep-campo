# -*- coding: utf-8 -*-
"""REP Campo. Camadas: dominio (regras puras) -> aplicacao (casos de uso)
-> infra (db, blob, seguranca) -> web (Flask). Dependência só para dentro."""
from flask import Flask

from rep_campo import config as _config

_config.carregar_env()


def create_app():
    app = Flask(__name__, root_path=_config.BASE_DIR,
                instance_path=_config.BASE_DIR + "/instance")
    app.secret_key = _config.secret_key()
    app.config.update(_config.flask_config())

    from rep_campo.infra.db import close_db
    app.teardown_appcontext(close_db)

    from rep_campo.web import auth, fichas, gestor, importar, sistema, viagens
    for bp in (auth.bp, fichas.bp, gestor.bp, viagens.bp, importar.bp, sistema.bp):
        app.register_blueprint(bp)

    return app
