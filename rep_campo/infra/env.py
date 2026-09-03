# -*- coding: utf-8 -*-
"""Re-export canônico do carregamento de .env para os scripts."""
from rep_campo.config import BASE_DIR, carregar_env

__all__ = ["BASE_DIR", "carregar_env"]
