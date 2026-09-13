# -*- coding: utf-8 -*-
"""Shim dos testes do lab 13: coloca tools/ no sys.path para importar wifi_locate."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
