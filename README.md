# Descarregador de Fotos — versão Web

Versão web (servidor local + navegador) do Descarregador de Fotos do Ministério. O servidor Python roda no
computador que recebe o cartão SD; a interface é aberta no navegador (`http://localhost:50007`).

## Como rodar
```bash
./rodar.sh        # Linux/macOS      |   rodar.bat  # Windows
```
Na primeira execução o ambiente virtual e as dependências são instalados automaticamente.
Copie `.env-example` para `.env` se quiser definir credenciais do Google, webhook ou porta.

## Módulos (equivalentes ao app desktop)
| Módulo | Onde |
|---|---|
| Dias de Servir (criar, editar, excluir, ativar) e Modo Avulso | Painel inicial |
| Detecção de cartão SD / origem manual, seleção de pastas (DCIM) | Tela de descarregamento |
| Cópia paralela, numeração `Fotografo_001`, marcador "já descarregadas", subpastas `_2`, `_3`, aviso de RAW | `app/transfer.py` |
| Seleção de fotos (miniaturas, teclado, desfazer, apagar) | Botão "Selecionar Fotos" |
| Upload para o Google Drive | Tela de descarregamento |
| Conta Google (credenciais, login OAuth, teste, desconectar) | Painel → Login Google |
| Pastas do Drive e pastas locais do dia | Painel → Config Drive |
| Histórico | Painel → Histórico |
| Rede local Líder/Auxiliar (UDP 50008 + HTTP 50007) e Finalizar Servir (webhook) | Painel / `app/lan.py` |
| Painel de acompanhamento pelo celular (QR code ao iniciar o Servir): PCs livres/ocupados, quem está descarregando e há quanto tempo, quem já descarregou e quem falta | `app/painel.py` / `/painel` |
| Atualização via Git (aviso na tela, `git pull` com um clique) | `app/main.py` |

A rede local usa o **mesmo protocolo** do app desktop (`/preset`, `/stats`, `/register`, `/finalize`),
então estações desktop e web podem trabalhar juntas.

## Segurança
O servidor escuta em `0.0.0.0` somente para a rede local Líder/Auxiliar. Por padrão, **apenas a própria máquina**
acessa a interface e a API (`/api/*`); de outros computadores só respondem os endpoints do protocolo de rede (`/preset`, `/stats`, `/register`,
`/finalize`, `/numeracao`, `/atividade`) e o painel somente leitura (`/painel`, `/painel/dados`).
Para liberar a interface na rede (ex.: usar de um tablet) defina `ALLOW_REMOTE_UI=1` — só em rede confiável,
pois a interface lê e apaga arquivos do disco.

## Testes
```bash
.venv/bin/pip install pytest httpx
.venv/bin/python -m pytest tests -q
```

## Estrutura
```
app/core.py      estado, caminhos, JSON, regras de destino      app/stats.py   EXIF e estatísticas
app/transfer.py  cartão, plano e cópia                          app/review.py  JPEG para o revisor (RAW via rawpy)
app/drive.py     Google Drive                                   app/lan.py     rede local e webhook
app/main.py      API FastAPI                                    app/static/    interface (HTML/CSS/JS)
app/painel.py    painel de acompanhamento (QR code)
```
Dados do usuário ficam em `data/` e as fotos em `Fotos_Sistema/` (ambos fora do Git).
