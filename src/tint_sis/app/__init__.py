"""Capa de aplicacion de escritorio de TINT_SIS.

Envuelve el motor `tint_sis` (CLI) en una ventana pywebview + FastAPI local:
`main.py` abre la ventana, `server.py` monta la API y la UI estatica, `api.py`
llama al motor (`pipeline` / `preview` / `config`), `_runner.py` corre el ciclo
lento en un hilo aparte. La UI (HTML/CSS/JS) vive en `ui/`.
"""
