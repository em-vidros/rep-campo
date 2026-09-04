# -*- coding: utf-8 -*-
"""REP Campo. Hexagonal enxuto.

Dentro: `dominio` (regras puras + portas) <- `aplicacao` (casos de uso).
Fora: `infra` (Postgres, Blob, relógio, segurança) e `web` (Flask) são
adapters. `aplicacao` nunca importa `infra` no topo — recebe foto/relógio
por argumento. `web` nunca monta SQL — chama `aplicacao` ou
`infra/repositorios.py`. Dependência só para dentro, rumo ao centro."""
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

    from rep_campo.web import (auth, fichas, gestor, importar, recados,
                               sistema, viagens)
    for bp in (auth.bp, fichas.bp, gestor.bp, viagens.bp, importar.bp,
               recados.bp, sistema.bp):
        app.register_blueprint(bp)

    return app
