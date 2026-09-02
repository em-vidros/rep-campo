# -*- coding: utf-8 -*-
"""Ponto de entrada da Vercel.

A Vercel procura um objeto WSGI chamado `app` dentro de api/. O codigo continua
inteiro no app.py da raiz, e este arquivo so aponta para la.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401
