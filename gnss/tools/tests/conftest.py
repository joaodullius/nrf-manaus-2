# -*- coding: utf-8 -*-
"""Coloca as ferramentas do lab 4 no sys.path dos testes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
