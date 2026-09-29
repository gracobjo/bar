"""Tickets fiscales en PDF (térmica 80 mm y A4) con QR de verificación."""

from __future__ import annotations

import hashlib
import io
import json
import os
import unicodedata
from decimal import Decimal
from pathlib import Path

import segno
from fpdf import FPDF

IVA_OPCIONES = (0, 4, 10, 21)

# Térmica: ancho fijo 80 mm. El alto parte de 200 mm y crece si el pedido no cabe.
ANCHO_TERMICA_MM = 80
ALTO_TERMICA_MIN_MM = 200
MARGEN_TERMICA_MM = 3
MARGEN_A4_MM = 15


def desglose_iva(total: Decimal, porcentaje: int) -> dict:
    """Precios con IVA incluido. Si el tipo es 0, no hay cuota que desglosar."""
    importe = Decimal(total).quantize(Decimal("0.01"))
    if porcentaje <= 0:
        return {
            "iva_porcentaje": 0,
            "base": f"{importe:.2f}",
            "cuota_iva": "0.00",
            "total": f"{importe:.2f}",
        }
    tipo = Decimal(porcentaje) / Decimal(100)
    base = (importe / (Decimal(1) + tipo)).quantize(Decimal("0.01"))
    cuota = (importe - base).quantize(Decimal("0.01"))
    return {
        "iva_porcentaje": int(porcentaje),
        "base": f"{base:.2f}",
        "cuota_iva": f"{cuota:.2f}",
        "total": f"{importe:.2f}",
    }


def huella_cuenta(mesa: str, lineas: list, total: str, fiscal: dict) -> str:
    """Identifica la cuenta. Misma huella = mismo número de ticket."""
    canon = {
        "mesa": mesa,
        "lineas": lineas,
        "total": total,
        "nif": fiscal.get("nif", ""),
        "iva": fiscal.get("iva_porcentaje", 0),
        "serie": fiscal.get("serie_ticket", "A"),
        "razon": fiscal.get("razon_social", ""),
        "direccion": fiscal.get("direccion_fiscal", ""),
    }
    bruto = json.dumps(canon, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _ascii(valor: str) -> str:
    """Quita tildes y eñes. Así el lector no las cambia por caracteres chinos."""
    normal = unicodedata.normalize("NFD", str(valor or ""))
    sin_marcas = "".join(ch for ch in normal if unicodedata.category(ch) != "Mn")
    return " ".join(sin_marcas.encode("ascii", "ignore").decode("ascii").split())


def texto_qr(datos: dict) -> str:
    """Texto del QR, en lineas y solo con letras ASCII."""
    lineas_txt = [f"TICKET {_ascii(datos.get('ticket', ''))}"]
    razon = _ascii(datos.get("razon_social") or datos.get("nombre_bar") or "")
    if razon:
        lineas_txt.append(razon)
    nif = _ascii(datos.get("nif", ""))
    if nif:
        lineas_txt.append(f"NIF {nif}")
    direccion = _ascii(datos.get("direccion", ""))
    if direccion:
        lineas_txt.append(direccion)
    fecha = _ascii(datos.get("fecha", ""))
    if fecha:
        lineas_txt.append(fecha)
    mesa = _ascii(datos.get("mesa", ""))
    if mesa:
        lineas_txt.append(f"Mesa {mesa}")
    barman = _ascii(datos.get("barman", ""))
    if barman:
        lineas_txt.append(f"Barman {barman}")
    for linea in datos.get("lineas") or []:
        cantidad = int(linea.get("cantidad") or 0)
        producto = _ascii(linea.get("producto", ""))
        subtotal = _ascii(linea.get("subtotal", "0.00"))
        lineas_txt.append(f"{cantidad} {producto} {subtotal} EUR")
    iva = int(datos.get("iva_porcentaje") or 0)
    if iva <= 0:
        lineas_txt.append("IVA incluido en los precios")
    else:
        base = _ascii(datos.get("base", "0.00"))
        cuota = _ascii(datos.get("cuota_iva", "0.00"))
        lineas_txt.append(f"Base {base} EUR")
        lineas_txt.append(f"IVA {iva}% {cuota} EUR")
    lineas_txt.append(f"TOTAL {_ascii(datos.get('total', '0.00'))} EUR")
    return "\n".join(lineas_txt)


def generar_qr_ticket(datos: dict) -> bytes:
    """PNG del QR. Zona en blanco ancha para que la termica no recorte el borde."""
    texto = texto_qr(datos)
    codigo = segno.make(texto, error="m", micro=False, boost_error=False)
    buffer = io.BytesIO()
    codigo.save(buffer, kind="png", scale=12, border=4)
    return buffer.getvalue()


def _fuente_unicode(pdf: FPDF) -> bool:
    """Registra Arial si está en Windows. Si no, se usa Helvetica (sin €)."""
    windir = os.environ.get("WINDIR", r"C:\Windows")
    regular = Path(windir) / "Fonts" / "arial.ttf"
    negrita = Path(windir) / "Fonts" / "arialbd.ttf"
    if not regular.is_file() or not negrita.is_file():
        return False
    try:
        pdf.add_font("Ticket", "", str(regular))
        pdf.add_font("Ticket", "B", str(negrita))
    except (OSError, RuntimeError):
        return False
    return True


def _texto(valor: str, unicode_ok: bool) -> str:
    texto = " ".join(str(valor or "").replace("\n", " ").split())
    if unicode_ok:
        return texto
    return texto.replace("€", " EUR").encode("latin-1", "replace").decode("latin-1")


def _euros(importe: str, unicode_ok: bool) -> str:
    limpio = str(importe or "0.00")
    if unicode_ok:
        return f"{limpio} €"
    return f"{limpio} EUR"


def _alto_png(png: bytes, ancho_mm: float) -> float:
    from PIL import Image

    imagen = Image.open(io.BytesIO(png))
    ancho_px, alto_px = imagen.size
    if ancho_px <= 0:
        return ancho_mm
    return ancho_mm * alto_px / ancho_px


def _colocar_png(pdf: FPDF, png: bytes, ancho_max: float, alto_max: float) -> None:
    try:
        ancho = ancho_max
        alto = _alto_png(png, ancho)
        if alto > alto_max and alto > 0:
            ancho = ancho_max * alto_max / alto
            alto = alto_max
        x = pdf.l_margin + max((pdf.epw - ancho) / 2, 0)
        y = pdf.get_y()
        pdf.image(io.BytesIO(png), x=x, y=y, w=ancho, h=alto)
        pdf.set_y(y + alto + 2)
    except (OSError, RuntimeError, ValueError):
        return


def _separador(pdf: FPDF) -> None:
    y = pdf.get_y() + 0.8
    pdf.set_draw_color(0)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.set_y(y + 2)


def _parrafo(pdf: FPDF, texto: str, alto: float, alineacion: str = "L") -> None:
    if not texto:
        return
    pdf.multi_cell(
        0,
        alto,
        texto,
        align=alineacion,
        new_x="LMARGIN",
        new_y="NEXT",
    )


def _alto_termica(datos: dict, con_logo: bool) -> float:
    direccion = str(datos.get("direccion") or "")
    lineas = datos.get("lineas") or []
    alto = 16
    alto += 22 if con_logo else 0
    alto += 24 + max(1, len(direccion) // 28) * 4
    alto += 28
    alto += max(len(lineas), 1) * 11
    alto += 36
    alto += 90
    return max(float(ALTO_TERMICA_MIN_MM), float(alto))


def generar_pdf_ticket(
    datos: dict,
    formato: str,
    logo_png: bytes | None = None,
) -> bytes:
    """PDF del ticket. `formato` es 'termica' (80 mm) o 'a4'."""
    termica = formato != "a4"
    if termica:
        pdf = FPDF(
            orientation="P",
            unit="mm",
            format=(ANCHO_TERMICA_MM, _alto_termica(datos, bool(logo_png))),
        )
        pdf.set_margins(MARGEN_TERMICA_MM, MARGEN_TERMICA_MM, MARGEN_TERMICA_MM)
        pdf.set_auto_page_break(auto=True, margin=MARGEN_TERMICA_MM)
        tam_titulo, tam_cuerpo, tam_peque, tam_total = 11, 8, 7, 12
        alto_linea, alto_peque = 3.6, 3.2
        logo_w, logo_h, qr_mm = 36, 16, 68
    else:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_margins(MARGEN_A4_MM, MARGEN_A4_MM, MARGEN_A4_MM)
        pdf.set_auto_page_break(auto=True, margin=MARGEN_A4_MM)
        tam_titulo, tam_cuerpo, tam_peque, tam_total = 16, 11, 9, 16
        alto_linea, alto_peque = 6, 5
        logo_w, logo_h, qr_mm = 48, 26, 42

    unicode_ok = _fuente_unicode(pdf)
    familia = "Ticket" if unicode_ok else "Helvetica"
    pdf.add_page()
    pdf.set_title(_texto(f"Ticket {datos.get('ticket', '')}", unicode_ok))
    autor = datos.get("razon_social") or datos.get("nombre_bar") or "Cuenta del Bar"
    pdf.set_author(_texto(str(autor), unicode_ok))

    if logo_png:
        _colocar_png(pdf, logo_png, logo_w, logo_h)

    pdf.set_font(familia, "B", tam_titulo)
    _parrafo(
        pdf,
        _texto(str(datos.get("razon_social") or datos.get("nombre_bar") or ""), unicode_ok),
        alto_linea + 0.6,
        "C",
    )
    nombre_bar = str(datos.get("nombre_bar") or "")
    razon = str(datos.get("razon_social") or "")
    if nombre_bar and nombre_bar != razon:
        pdf.set_font(familia, "", tam_cuerpo)
        _parrafo(pdf, _texto(nombre_bar, unicode_ok), alto_linea, "C")

    pdf.set_font(familia, "", tam_cuerpo)
    nif = str(datos.get("nif") or "").strip() or "(no indicado)"
    _parrafo(pdf, _texto(f"NIF: {nif}", unicode_ok), alto_linea, "C")
    direccion = str(datos.get("direccion") or "").strip()
    if direccion:
        pdf.set_font(familia, "", tam_peque)
        _parrafo(pdf, _texto(direccion, unicode_ok), alto_peque, "C")

    _separador(pdf)
    pdf.set_font(familia, "B", tam_titulo)
    _parrafo(pdf, _texto(f"TICKET {datos.get('ticket', '')}", unicode_ok), alto_linea + 0.6, "C")
    pdf.set_font(familia, "", tam_cuerpo)
    _parrafo(pdf, _texto(f"Fecha: {datos.get('fecha', '')}", unicode_ok), alto_linea)
    _parrafo(pdf, _texto(f"Mesa: {datos.get('mesa', '')}", unicode_ok), alto_linea)
    _parrafo(pdf, _texto(f"Barman: {datos.get('barman', '')}", unicode_ok), alto_linea)

    _separador(pdf)
    pdf.set_font(familia, "B", tam_peque)
    _parrafo(pdf, _texto("DESCRIPCION", unicode_ok), alto_peque)

    pdf.set_font(familia, "", tam_cuerpo)
    lineas = datos.get("lineas") or []
    if not lineas:
        _parrafo(pdf, _texto("Sin productos", unicode_ok), alto_linea)
    for linea in lineas:
        producto = _texto(str(linea.get("producto", "")), unicode_ok)
        cantidad = int(linea.get("cantidad") or 0)
        precio = _euros(str(linea.get("precio", "0.00")), unicode_ok)
        subtotal = _euros(str(linea.get("subtotal", "0.00")), unicode_ok)
        _parrafo(pdf, f"{cantidad} x {producto}", alto_linea)
        pdf.set_font(familia, "", tam_peque)
        _parrafo(
            pdf,
            _texto(f"{precio} / ud    {subtotal}", unicode_ok),
            alto_peque,
            "R",
        )
        pdf.set_font(familia, "", tam_cuerpo)

    _separador(pdf)
    iva = int(datos.get("iva_porcentaje") or 0)
    if iva <= 0:
        pdf.set_font(familia, "", tam_cuerpo)
        _parrafo(pdf, _texto("IVA incluido en los precios", unicode_ok), alto_linea, "C")
    else:
        pdf.set_font(familia, "", tam_cuerpo)
        _parrafo(
            pdf,
            _texto(f"Base imponible    {_euros(str(datos.get('base', '0.00')), unicode_ok)}", unicode_ok),
            alto_linea,
            "R",
        )
        _parrafo(
            pdf,
            _texto(
                f"IVA {iva} %    {_euros(str(datos.get('cuota_iva', '0.00')), unicode_ok)}",
                unicode_ok,
            ),
            alto_linea,
            "R",
        )
        pdf.set_font(familia, "", tam_peque)
        _parrafo(
            pdf,
            _texto("Precios con IVA incluido", unicode_ok),
            alto_peque,
            "R",
        )

    pdf.set_font(familia, "B", tam_total)
    _parrafo(
        pdf,
        _texto(f"TOTAL    {_euros(str(datos.get('total', '0.00')), unicode_ok)}", unicode_ok),
        alto_linea + 1,
        "R",
    )

    _separador(pdf)
    pdf.set_auto_page_break(auto=False)
    qr = generar_qr_ticket(datos)
    ancho_qr = min(qr_mm, pdf.epw)
    _colocar_png(pdf, qr, ancho_qr, ancho_qr)
    pdf.set_font(familia, "", tam_peque)
    _parrafo(pdf, _texto("QR de verificacion del ticket", unicode_ok), alto_peque, "C")
    pdf.ln(1)
    pdf.set_font(familia, "", tam_cuerpo)
    _parrafo(pdf, _texto("Gracias por su visita", unicode_ok), alto_linea, "C")

    salida = pdf.output()
    return bytes(salida)
