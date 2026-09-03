# -*- coding: utf-8 -*-
"""Ponto de entrada da Vercel. Procura um objeto WSGI chamado `app` em api/."""
from rep_campo import create_app

app = create_app()
