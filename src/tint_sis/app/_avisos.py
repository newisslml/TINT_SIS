"""Avisos de fin de trabajo (pedido del usuario 2026-10-01): cuando termina el
analisis del maestro, la preparacion de los expertos o un ciclo.

Cada aviso queda en una lista en memoria que la UI consulta por polling
(`/api/avisos?desde=<id>`): main.js lo muestra como un cartel en cualquier
vista. Ademas, si la app lo activo (`activar_sistema`, solo el arranque de la
app; los tests y la CLI no) y la configuracion no lo apago
(`AppConfig.notificaciones`), sale una notificacion de Windows y parpadea el
boton de la ventana en la barra de tareas, para enterarse con la app minimizada
o detras de otra ventana.

La notificacion usa la API de Windows (ToastNotificationManager) via
PowerShell, con un AppUserModelID propio registrado en HKCU para que aparezca
como "TINT_SIS" y no como PowerShell. Si algo falla solo se anota en el log:
el cartel dentro de la app sale igual.
"""
from __future__ import annotations

import base64
import ctypes
import subprocess
import sys
import threading
import time
from pathlib import Path
from xml.sax.saxutils import escape

AUMID = "Codelpa.TINT_SIS"
_MAX_AVISOS = 50

_lock = threading.Lock()
_avisos: list[dict] = []
_ultimo_id = 0
_sistema = False
_titulo_ventana: str | None = None


def activar_sistema(titulo_ventana: str | None = None) -> None:
    """Habilita la notificacion de Windows (y el parpadeo de la ventana con ese
    titulo, si es la app de escritorio)."""
    global _sistema, _titulo_ventana
    _sistema = sys.platform == "win32"
    _titulo_ventana = titulo_ventana


def avisar(titulo: str, texto: str, *, nivel: str = "ok", vista: str | None = None, sistema: bool = True) -> dict:
    """Registra un aviso para la UI. `nivel`: ok | advertencia | error | info
    (advertencia = naranjo); `vista`: a donde lleva el boton del cartel.
    `sistema=False` (o notificaciones apagadas en Configuracion) no lo manda a
    Windows."""
    global _ultimo_id
    with _lock:
        _ultimo_id += 1
        aviso = {
            "id": _ultimo_id,
            "titulo": titulo,
            "texto": texto,
            "nivel": nivel,
            "vista": vista,
            "hora": time.strftime("%H:%M"),
        }
        _avisos.append(aviso)
        del _avisos[:-_MAX_AVISOS]
    if sistema and _sistema:
        threading.Thread(target=_notificar_windows, args=(titulo, texto, nivel), daemon=True).start()
    return aviso


def desde(ultimo: int) -> dict:
    """Los avisos posteriores a `ultimo` (id) y el id del mas nuevo. La UI
    arranca pidiendo con -1 solo para saber el ultimo id (no repite avisos
    viejos al recargar)."""
    with _lock:
        nuevos = [] if ultimo < 0 else [a for a in _avisos if a["id"] > ultimo]
        return {"ultimo": _ultimo_id, "avisos": nuevos}


# --------------------------------------------------------------------------- #
# Windows
# --------------------------------------------------------------------------- #
def _icono() -> Path | None:
    """assets/tint_sis.ico: junto al exe (lo empaqueta tint_sis.spec) o en el repo."""
    if getattr(sys, "frozen", False):
        candidato = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets" / "tint_sis.ico"
    else:
        candidato = Path(__file__).resolve().parents[3] / "assets" / "tint_sis.ico"
    return candidato if candidato.is_file() else None


def _registrar_app() -> None:
    """Nombre e icono con que Windows muestra las notificaciones de AUMID."""
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}") as clave:
        winreg.SetValueEx(clave, "DisplayName", 0, winreg.REG_SZ, "TINT_SIS")
        icono = _icono()
        if icono is not None:
            winreg.SetValueEx(clave, "IconUri", 0, winreg.REG_SZ, str(icono))


_LLAMATIVOS = ("advertencia", "error")


def _script_toast(titulo: str, texto: str, nivel: str = "ok") -> str:
    """Script de PowerShell que muestra la notificacion. Una notificacion no
    tiene color: las de advertencia/error llevan ⚠ en el titulo y quedan en
    pantalla hasta cerrarlas (scenario "reminder" con el boton Cerrar del
    sistema), para que no pasen desapercibidas."""
    llamativo = nivel in _LLAMATIVOS
    if llamativo:
        titulo = f"⚠ {titulo}"
    xml = (
        ('<toast scenario="reminder">' if llamativo else "<toast>")
        + '<visual><binding template="ToastGeneric">'
        f"<text>{escape(titulo)}</text><text>{escape(texto)}</text>"
        "</binding></visual>"
        + ('<actions><action activationType="system" arguments="dismiss" content="Cerrar"/></actions>'
           if llamativo else "")
        + "</toast>"
    ).replace("'", "''")  # dentro de un string de PowerShell entre comillas simples
    return (
        "$ErrorActionPreference = 'Stop';"
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$xml.LoadXml('{xml}');"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{AUMID}')"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($xml))"
    )


def _notificar_windows(titulo: str, texto: str, nivel: str = "ok") -> None:
    try:
        _parpadear()
        _registrar_app()
        script = base64.b64encode(_script_toast(titulo, texto, nivel).encode("utf-16-le")).decode("ascii")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0:
            print(f"No se pudo mostrar la notificacion de Windows: {r.stderr.strip()[-500:]}")
    except Exception as exc:  # noqa: BLE001 - un aviso que falla no debe tirar la app
        print(f"No se pudo mostrar la notificacion de Windows: {exc}")


class _FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("dwFlags", ctypes.c_uint),
        ("uCount", ctypes.c_uint),
        ("dwTimeout", ctypes.c_uint),
    ]


_FLASHW_ALL = 0x3
_FLASHW_TIMERNOFG = 0xC  # hasta que la ventana pase al frente


def _parpadear() -> None:
    """Hace parpadear el boton de la ventana de TINT_SIS en la barra de tareas
    si no es la ventana activa."""
    if not _titulo_ventana:
        return
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    hwnd = user32.FindWindowW(None, _titulo_ventana)
    if not hwnd or hwnd == user32.GetForegroundWindow():
        return
    info = _FLASHWINFO(ctypes.sizeof(_FLASHWINFO), hwnd, _FLASHW_ALL | _FLASHW_TIMERNOFG, 0, 0)
    user32.FlashWindowEx(ctypes.byref(info))
