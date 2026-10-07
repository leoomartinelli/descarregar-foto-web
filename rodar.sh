#!/usr/bin/env bash
# Linux / macOS: cria o ambiente virtual na primeira vez e inicia o servidor.
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
.venv/bin/python run.py
