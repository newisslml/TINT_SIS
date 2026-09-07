"""Arranque de la app: levanta uvicorn en un hilo y abre la ventana pywebview.

    python -m tint_sis.app            # ventana de escritorio (pywebview)
    python -m tint_sis.app --browser  # abre en el navegador (util para iterar)
"""
from __future__ import annotations

import argparse
import socket
import threading
import time

import uvicorn

from .server import app

WINDOW_TITLE = "TINT_SIS"
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="tint_sis.app")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Abre la UI en el navegador por defecto en vez de la ventana pywebview",
    )
    parser.add_argument("--port", type=int, default=0, help="Puerto fijo (0 = efimero)")
    args = parser.parse_args()

    port = args.port or _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=_serve, args=(server,), daemon=True)
    thread.start()

    # esperar a que uvicorn termine de levantar
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)

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
