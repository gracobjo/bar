"""Lectura y escritura de los JSON del bar, en este ordenador o en otro de la red.

El ordenador que no tiene `servidor` en conexion_bar.json guarda los ficheros.
El resto llama por HTTP. El número de ticket solo avanza dentro del candado,
para que dos pantallas no saquen el mismo A-00001.
"""

from __future__ import annotations

import json
import os
import re
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONEXION_FILE = RAIZ / "conexion_bar.json"
PUERTO = int(os.environ.get("BAR_PUERTO", "8765"))

FICHEROS = {
    "config_bar.json",
    "menu_bar.json",
    "mesas_bar.json",
    "costes_bar.json",
    "ventas_bar.json",
    "personal_bar.json",
    "incidencias_bar.json",
}

CANDADO = threading.RLock()


class ErrorAlmacen(Exception):
    """El otro ordenador no contestó o rechazó el cambio."""


def url_configurada() -> str:
    entorno = os.environ.get("BAR_SERVIDOR", "").strip()
    if entorno:
        return _normalizar_url(entorno)
    if not CONEXION_FILE.exists():
        return ""
    try:
        datos = json.loads(CONEXION_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return ""
    if not isinstance(datos, dict):
        return ""
    return _normalizar_url(str(datos.get("servidor") or ""))


def es_remoto() -> bool:
    return bool(url_configurada())


def guardar_url(url: str) -> None:
    limpia = _normalizar_url(url)
    CONEXION_FILE.write_text(
        json.dumps({"servidor": limpia}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def direccion_lan() -> str:
    sonda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sonda.connect(("8.8.8.8", 80))
        return sonda.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sonda.close()


def url_publica() -> str:
    return f"http://{direccion_lan()}:{PUERTO}"


def probar(url: str) -> str:
    """Devuelve el nombre del bar si /api/salud responde. Si no, cadena vacía."""
    destino = _normalizar_url(url)
    if not destino:
        return ""
    try:
        estado, cuerpo = _pedir("GET", destino + "/api/salud", timeout=3)
    except ErrorAlmacen:
        return ""
    if estado != 200:
        return ""
    try:
        datos = json.loads(cuerpo)
    except json.JSONDecodeError:
        return ""
    if not isinstance(datos, dict) or not datos.get("ok"):
        return ""
    return str(datos.get("nombre") or "el bar")


def leer(nombre: str) -> str | None:
    _exigir_fichero(nombre)
    if es_remoto():
        estado, cuerpo = _pedir("GET", f"{url_configurada()}/api/fichero/{nombre}")
        if estado == 404:
            return None
        if estado != 200:
            raise ErrorAlmacen(_mensaje_http(estado, cuerpo))
        return cuerpo
    with CANDADO:
        return _leer_disco(nombre)


def escribir(nombre: str, texto: str, forzar_numero: bool = False) -> None:
    _exigir_fichero(nombre)
    if es_remoto():
        cabeceras = {}
        if forzar_numero:
            cabeceras["X-Forzar-Numero"] = "1"
        estado, cuerpo = _pedir(
            "PUT",
            f"{url_configurada()}/api/fichero/{nombre}",
            texto.encode("utf-8"),
            cabeceras,
        )
        if estado != 200:
            raise ErrorAlmacen(_mensaje_http(estado, cuerpo))
        return
    with CANDADO:
        if nombre == "config_bar.json" and not forzar_numero:
            texto = _combinar_proximo(texto)
        _escribir_disco(nombre, texto)


def leer_logo() -> tuple[str, bytes] | None:
    if es_remoto():
        estado, cuerpo, cabeceras = _pedir_bytes("GET", f"{url_configurada()}/api/logo")
        if estado == 404:
            return None
        if estado != 200:
            raise ErrorAlmacen("No se pudo leer el logo del otro ordenador.")
        nombre = cabeceras.get("X-Nombre") or "marca_bar.png"
        return nombre, cuerpo
    with CANDADO:
        carpeta = RAIZ / "assets"
        if not carpeta.exists():
            return None
        for ruta in carpeta.glob("marca_bar.*"):
            return ruta.name, ruta.read_bytes()
        return None


def escribir_logo(nombre: str, datos: bytes) -> None:
    nombre_ok = Path(nombre).name
    if not nombre_ok.startswith("marca_bar."):
        raise ErrorAlmacen("Nombre de logo no válido.")
    if es_remoto():
        estado, cuerpo, _ = _pedir_bytes(
            "PUT",
            f"{url_configurada()}/api/logo",
            datos,
            {"X-Nombre": nombre_ok, "Content-Type": "application/octet-stream"},
        )
        if estado != 200:
            raise ErrorAlmacen(_mensaje_http(estado, cuerpo.decode("utf-8", "replace")))
        return
    with CANDADO:
        _escribir_logo_disco(nombre_ok, datos)


def borrar_logo() -> None:
    if es_remoto():
        estado, cuerpo, _ = _pedir_bytes("DELETE", f"{url_configurada()}/api/logo")
        if estado not in (200, 404):
            raise ErrorAlmacen(_mensaje_http(estado, cuerpo.decode("utf-8", "replace")))
        return
    with CANDADO:
        _borrar_logo_disco()


def reservar_numero() -> dict:
    """Reserva el siguiente ticket. En red lo hace el ordenador que guarda los datos."""
    if es_remoto():
        estado, cuerpo = _pedir("POST", f"{url_configurada()}/api/siguiente-ticket")
        if estado != 200:
            raise ErrorAlmacen(_mensaje_http(estado, cuerpo))
        datos = json.loads(cuerpo)
        if not isinstance(datos, dict) or not datos.get("codigo"):
            raise ErrorAlmacen("El otro ordenador no devolvió un número de ticket.")
        return datos
    with CANDADO:
        return _reservar_disco()


def leer_disco_config() -> dict:
    texto = _leer_disco("config_bar.json")
    if not texto:
        return {}
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _reservar_disco() -> dict:
    datos = leer_disco_config()
    serie = re.sub(r"[^A-Za-z0-9]", "", str(datos.get("serie_ticket") or "")).upper()
    serie = (serie or "A")[:10]
    try:
        numero = int(datos.get("proximo_numero_ticket") or 1)
    except (TypeError, ValueError):
        numero = 1
    if numero < 1:
        numero = 1
    datos["proximo_numero_ticket"] = numero + 1
    datos["serie_ticket"] = serie
    _escribir_disco("config_bar.json", json.dumps(datos, ensure_ascii=False, indent=2))
    return {
        "codigo": f"{serie}-{numero:05d}",
        "serie": serie,
        "numero": numero,
        "proximo": numero + 1,
    }


def _combinar_proximo(texto_nuevo: str) -> str:
    """No deja que una pantalla atrasada baje el correlativo que otra acaba de usar."""
    try:
        nuevo = json.loads(texto_nuevo)
    except json.JSONDecodeError:
        return texto_nuevo
    if not isinstance(nuevo, dict):
        return texto_nuevo
    anterior = leer_disco_config()
    try:
        proximo_nuevo = int(nuevo.get("proximo_numero_ticket") or 1)
    except (TypeError, ValueError):
        proximo_nuevo = 1
    try:
        proximo_anterior = int(anterior.get("proximo_numero_ticket") or 1)
    except (TypeError, ValueError):
        proximo_anterior = 1
    nuevo["proximo_numero_ticket"] = max(proximo_nuevo, proximo_anterior, 1)
    return json.dumps(nuevo, ensure_ascii=False, indent=2)


def _exigir_fichero(nombre: str) -> None:
    if nombre not in FICHEROS:
        raise ErrorAlmacen("Fichero no permitido.")


def _ruta(nombre: str) -> Path:
    return RAIZ / nombre


def _leer_disco(nombre: str) -> str | None:
    ruta = _ruta(nombre)
    if not ruta.exists():
        return None
    return ruta.read_text(encoding="utf-8")


def _escribir_disco(nombre: str, texto: str) -> None:
    _ruta(nombre).write_text(texto, encoding="utf-8")


def _escribir_logo_disco(nombre: str, datos: bytes) -> None:
    carpeta = RAIZ / "assets"
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob("marca_bar.*"):
        viejo.unlink(missing_ok=True)
    (carpeta / nombre).write_bytes(datos)


def _borrar_logo_disco() -> None:
    carpeta = RAIZ / "assets"
    if not carpeta.exists():
        return
    for viejo in carpeta.glob("marca_bar.*"):
        viejo.unlink(missing_ok=True)


def _normalizar_url(url: str) -> str:
    texto = (url or "").strip().rstrip("/")
    if texto and not texto.startswith(("http://", "https://")):
        texto = "http://" + texto
    return texto


def _mensaje_http(estado: int, cuerpo: str) -> str:
    if estado == 0:
        return "No hay conexión con el ordenador que guarda los datos."
    return f"El ordenador de los datos respondió {estado}."


def _pedir(
    metodo: str,
    url: str,
    datos: bytes | None = None,
    cabeceras: dict | None = None,
    timeout: float = 5,
) -> tuple[int, str]:
    estado, cuerpo, _ = _pedir_bytes(metodo, url, datos, cabeceras, timeout)
    return estado, cuerpo.decode("utf-8")


def _pedir_bytes(
    metodo: str,
    url: str,
    datos: bytes | None = None,
    cabeceras: dict | None = None,
    timeout: float = 5,
) -> tuple[int, bytes, dict]:
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras or {}, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            cabeceras_resp = {k: v for k, v in respuesta.headers.items()}
            return respuesta.status, respuesta.read(), cabeceras_resp
    except urllib.error.HTTPError as exc:
        cuerpo = exc.read()
        return exc.code, cuerpo, {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ErrorAlmacen("No hay conexión con el ordenador que guarda los datos.") from exc
