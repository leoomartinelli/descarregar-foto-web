#!/usr/bin/env bash
# Linux / macOS: cria o ambiente virtual na primeira vez e inicia o servidor.
# As dependencias sao (re)instaladas sempre que o requirements.txt mudar (ex.: depois de uma atualizacao).
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
cmp -s requirements.txt .venv/requirements.txt || { .venv/bin/pip install -r requirements.txt && cp requirements.txt .venv/requirements.txt; }
.venv/bin/python run.py
