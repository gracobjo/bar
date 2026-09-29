"""Servidor de los JSON del bar, en el ordenador que guarda los datos.

Arranca solo con la app, en el puerto 8765, para que otro ordenador de la
misma red use las mismas mesas y el mismo número de ticket.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import almacen

_hilo: threading.Thread | None = None
_httpd: ThreadingHTTPServer | None = None
_error_arranque = ""


def error_arranque() -> str:
    return _error_arranque


def _parar() -> None:
    global _hilo, _httpd
    servidor = _httpd
    _httpd = None
    _hilo = None
    if servidor is not None:
        servidor.shutdown()
        servidor.server_close()


class ServidorDatos(ThreadingHTTPServer):
    def handle_error(self, request, client_address) -> None:
        """Un cliente que cierra el puerto no es un fallo de los datos."""
        return


def asegurar_servidor() -> None:
    """Abre el puerto una sola vez. Si este proceso pasa a ser cliente, lo cierra."""
    global _hilo, _httpd, _error_arranque
    if os.environ.get("BAR_SIN_SERVIDOR") or almacen.es_remoto():
        _parar()
        return
    if _hilo and _hilo.is_alive():
        return
    try:
        _httpd = ServidorDatos(("0.0.0.0", almacen.PUERTO), Manejador)
    except OSError as exc:
        _error_arranque = (
            f"No se pudo abrir el puerto {almacen.PUERTO} para los otros ordenadores ({exc})."
        )
        _httpd = None
        return
    _error_arranque = ""
    _hilo = threading.Thread(target=_httpd.serve_forever, name="datos-bar", daemon=True)
    _hilo.start()


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path == "/api/salud":
            config = almacen.leer_disco_config()
            self._json(
                200,
                {
                    "ok": True,
                    "nombre": config.get("nombre_bar") or "Cuenta del Bar",
                },
            )
            return
        if self.path.startswith("/api/fichero/"):
            nombre = self.path.removeprefix("/api/fichero/")
            if nombre not in almacen.FICHEROS:
                self._json(404, {"error": "no encontrado"})
                return
            with almacen.CANDADO:
                texto = almacen._leer_disco(nombre)
            if texto is None:
                self._json(404, {"error": "no encontrado"})
                return
            self._texto(200, texto)
            return
        if self.path == "/api/logo":
            with almacen.CANDADO:
                carpeta = almacen.RAIZ / "assets"
                encontrado = None
                if carpeta.exists():
                    for ruta in carpeta.glob("marca_bar.*"):
                        encontrado = ruta
                        break
                if encontrado is None:
                    self._json(404, {"error": "sin logo"})
                    return
                datos = encontrado.read_bytes()
                nombre = encontrado.name
            self._bytes(200, datos, {"X-Nombre": nombre, "Content-Type": "application/octet-stream"})
            return
        self._json(404, {"error": "no encontrado"})

    def do_PUT(self) -> None:
        if self.path.startswith("/api/fichero/"):
            nombre = self.path.removeprefix("/api/fichero/")
            if nombre not in almacen.FICHEROS:
                self._json(404, {"error": "no encontrado"})
                return
            cuerpo = self._cuerpo()
            try:
                texto = cuerpo.decode("utf-8")
                json.loads(texto)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "json no válido"})
                return
            forzar = self.headers.get("X-Forzar-Numero") == "1"
            with almacen.CANDADO:
                if nombre == "config_bar.json" and not forzar:
                    texto = almacen._combinar_proximo(texto)
                almacen._escribir_disco(nombre, texto)
            self._json(200, {"ok": True})
            return
        if self.path == "/api/logo":
            nombre = self.headers.get("X-Nombre") or ""
            if not nombre.startswith("marca_bar."):
                self._json(400, {"error": "nombre de logo no válido"})
                return
            datos = self._cuerpo()
            with almacen.CANDADO:
                almacen._escribir_logo_disco(nombre, datos)
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "no encontrado"})

    def do_POST(self) -> None:
        if self.path != "/api/siguiente-ticket":
            self._json(404, {"error": "no encontrado"})
            return
        with almacen.CANDADO:
            datos = almacen._reservar_disco()
        self._json(200, datos)

    def do_DELETE(self) -> None:
        if self.path != "/api/logo":
            self._json(404, {"error": "no encontrado"})
            return
        with almacen.CANDADO:
            almacen._borrar_logo_disco()
        self._json(200, {"ok": True})

    def log_message(self, formato: str, *args) -> None:
        return

    def _cuerpo(self) -> bytes:
        try:
            largo = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            largo = 0
        if largo < 0 or largo > 8_000_000:
            return b""
        return self.rfile.read(largo) if largo else b""

    def _json(self, estado: int, payload: dict) -> None:
        self._texto(estado, json.dumps(payload, ensure_ascii=False))

    def _texto(self, estado: int, texto: str) -> None:
        datos = texto.encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _bytes(self, estado: int, datos: bytes, cabeceras: dict) -> None:
        self.send_response(estado)
        for clave, valor in cabeceras.items():
            self.send_header(clave, valor)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)
