"""Arranque de la app: levanta uvicorn en un hilo y abre la ventana pywebview.

    python -m tint_sis.app            # ventana de escritorio (pywebview)
    python -m tint_sis.app --browser  # abre en el navegador (util para iterar)
"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time

import uvicorn

from tint_sis import __version__
from tint_sis.config import load_config
from tint_sis.paths import app_data_dir, is_frozen

from .server import app

WINDOW_TITLE = f"TINT_SIS {__version__}"
WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1100, 720)


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _serve(server: uvicorn.Server) -> None:
    server.run()


def _redirect_output_to_log() -> None:
    # Con el .exe sin consola, stdout/stderr son None: se mandan a un log para poder diagnosticar.
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_dir = app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "tint_sis.log", "w", encoding="utf-8", buffering=1)
    sys.stdout = log
    sys.stderr = log


def _ensure_data_dirs() -> None:
    config = load_config()
    for folder in (config.input_dir, config.output_dir):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"No se pudo crear {folder}: {exc}")


def _show_error(message: str) -> None:
    print(message)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "TINT_SIS", 0x10)


def main() -> None:
    frozen = is_frozen()
    if frozen:
        _redirect_output_to_log()
        _ensure_data_dirs()

    parser = argparse.ArgumentParser(prog="tint_sis.app")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Abre la UI en el navegador por defecto en vez de la ventana pywebview",
    )
    parser.add_argument("--port", type=int, default=0, help="Puerto fijo (0 = efimero)")
    args = parser.parse_args()

    port = args.port or _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        log_config=None if frozen else uvicorn.config.LOGGING_CONFIG,
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=_serve, args=(server,), daemon=True)
    thread.start()

    # esperar a que uvicorn termine de levantar
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    else:
        _show_error(
            "No se pudo iniciar el servidor interno de TINT_SIS.\n"
            f"Revisa el log en {app_data_dir() / 'logs' / 'tint_sis.log'}"
        )
        return

    url = f"http://127.0.0.1:{port}/"

    if args.browser:
        import webbrowser

        print(f"TINT_SIS servido en {url}  (Ctrl+C para cortar)")
        webbrowser.open(url)
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        return

    import webview

    webview.create_window(
        WINDOW_TITLE,
        url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=MIN_WINDOW_SIZE,
    )
    webview.start()


if __name__ == "__main__":
    main()
