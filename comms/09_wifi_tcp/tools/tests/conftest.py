# -*- coding: utf-8 -*-
"""Shim dos testes do lab 9: coloca tools/ no sys.path para importar payload_ref."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
