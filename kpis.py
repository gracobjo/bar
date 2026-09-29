"""Cálculo de indicadores a partir de cuentas cerradas y mesas abiertas."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

ZONAS = ("barra", "mesas", "terraza")
ZONA_ETIQUETA = {"barra": "Barra", "mesas": "Mesas", "terraza": "Terraza"}


def dinero(valor) -> Decimal:
    try:
        return Decimal(str(valor if valor is not None else "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def parse_fecha(valor: str) -> datetime | None:
    texto = str(valor or "").strip()
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def en_periodo(fecha: str, dias: int | None, ahora: datetime | None = None) -> bool:
    if dias is None:
        return True
    momento = parse_fecha(fecha)
    if momento is None:
        return False
    limite = (ahora or datetime.now()) - timedelta(days=dias)
    return momento >= limite


def fusionar_cuentas(archivadas: list[dict], abiertas: list[dict]) -> list[dict]:
    """La mesa abierta sustituye su copia archivada mientras siga en sala."""
    vivas = {(c.get("mesa"), c.get("abierta_en")) for c in abiertas}
    historicas = [
        c
        for c in archivadas
        if (c.get("mesa"), c.get("abierta_en")) not in vivas
    ]
    return historicas + list(abiertas)


def _horas(minutos) -> Decimal:
    try:
        valor = Decimal(str(minutos if minutos is not None else 0))
    except InvalidOperation:
        valor = Decimal(0)
    if valor < 1:
        valor = Decimal(1)
    return (valor / Decimal(60)).quantize(Decimal("0.01"))


def _pct(parte: Decimal, total: Decimal) -> Decimal | None:
    if total <= 0:
        return None
    return (parte / total * Decimal(100)).quantize(Decimal("0.1"))


def calcular(
    cuentas: list[dict],
    costes_hora: dict | None = None,
    personal: list[dict] | None = None,
    incidencias: list[dict] | None = None,
    dias: int | None = None,
    plantilla_actual: int = 0,
    mesas_ahora: list[dict] | None = None,
    ahora: datetime | None = None,
) -> dict:
    """Indicadores del periodo. `dias` None significa todo el histórico."""
    ahora = ahora or datetime.now()
    costes_hora = costes_hora or {}
    personal = personal or []
    incidencias = incidencias or []
    mesas_ahora = mesas_ahora or []
    del_periodo = [c for c in cuentas if en_periodo(str(c.get("fecha", "")), dias, ahora)]

    ventas = Decimal("0.00")
    comensales = 0
    asiento_horas = Decimal("0.00")
    minutos_mesa = []
    minutos_servicio = []
    ventas_zona = {zona: Decimal("0.00") for zona in ZONAS}
    comensales_zona = {zona: 0 for zona in ZONAS}
    asiento_horas_zona = {zona: Decimal("0.00") for zona in ZONAS}
    ventas_zona_eur = {zona: Decimal("0.00") for zona in ZONAS}
    coste_conocido = Decimal("0.00")
    venta_con_coste = Decimal("0.00")
    margen_producto: dict[str, Decimal] = {}
    sin_coste: set[str] = set()
    nombres: dict[str, int] = {}
    ventas_barman: dict[str, Decimal] = {}
    minutos_barman: dict[str, int] = {}
    terraza_por_hora = {hora: 0 for hora in range(24)}

    for cuenta in del_periodo:
        total = dinero(cuenta.get("total"))
        ventas += total
        n = int(cuenta.get("n_comensales") or 0)
        if n <= 0:
            n = max(len(cuenta.get("comensales") or []), 1)
        comensales += n
        zona = cuenta.get("zona") if cuenta.get("zona") in ZONAS else "mesas"
        ventas_zona[zona] += total
        comensales_zona[zona] += n
        horas = _horas(cuenta.get("minutos_mesa"))
        asientos = int(cuenta.get("asientos") or 0)
        if asientos > 0:
            bloque = Decimal(asientos) * horas
            asiento_horas += bloque
            asiento_horas_zona[zona] += bloque
            ventas_zona_eur[zona] += total
        if cuenta.get("minutos_mesa") is not None:
            minutos_mesa.append(int(cuenta["minutos_mesa"]))
        if cuenta.get("minutos_servicio") is not None:
            minutos_servicio.append(int(cuenta["minutos_servicio"]))
        for nombre in cuenta.get("comensales") or []:
            clave = str(nombre).strip().casefold()
            if clave:
                nombres[clave] = nombres.get(clave, 0) + 1
        barman = str(cuenta.get("barman") or "").strip()
        if barman and barman != "(sin identificar)":
            ventas_barman[barman] = ventas_barman.get(barman, Decimal("0.00")) + total
            minutos_barman[barman] = minutos_barman.get(barman, 0) + int(
                cuenta.get("minutos_mesa") or 1
            )
        if zona == "terraza":
            momento = parse_fecha(str(cuenta.get("fecha", "")))
            if momento:
                terraza_por_hora[momento.hour] += 1
        for linea in cuenta.get("lineas") or []:
            producto = str(linea.get("producto") or "Producto")
            cantidad = int(linea.get("cantidad") or 0)
            subtotal = dinero(linea.get("subtotal"))
            coste_unit = linea.get("coste")
            if coste_unit is None:
                sin_coste.add(producto)
                continue
            coste = dinero(coste_unit) * cantidad
            coste_conocido += coste
            venta_con_coste += subtotal
            margen_producto[producto] = margen_producto.get(producto, Decimal("0.00")) + (
                subtotal - coste
            )

    def medio(total_zona: Decimal, personas: int) -> Decimal | None:
        if personas <= 0:
            return None
        return (total_zona / Decimal(personas)).quantize(Decimal("0.01"))

    revpash = None
    if asiento_horas > 0:
        revpash = (ventas / asiento_horas).quantize(Decimal("0.01"))
    revpash_zona = {}
    for zona in ZONAS:
        if asiento_horas_zona[zona] > 0:
            revpash_zona[zona] = (
                ventas_zona_eur[zona] / asiento_horas_zona[zona]
            ).quantize(Decimal("0.01"))
        else:
            revpash_zona[zona] = None

    horas_personal = Decimal("0.00")
    coste_personal = Decimal("0.00")
    sin_tarifa = []
    ventas_hora = {}
    for nombre, minutos in minutos_barman.items():
        horas = _horas(minutos)
        horas_personal += horas
        venta = ventas_barman.get(nombre, Decimal("0.00"))
        ventas_hora[nombre] = (venta / horas).quantize(Decimal("0.01")) if horas > 0 else None
        tarifa = costes_hora.get(nombre)
        if tarifa is None or str(tarifa).strip() == "":
            sin_tarifa.append(nombre)
            continue
        coste_personal += (horas * dinero(tarifa)).quantize(Decimal("0.01"))

    incidencias_periodo = [
        i for i in incidencias if en_periodo(str(i.get("ts", "")), dias, ahora)
    ]
    bajas = [
        e
        for e in personal
        if e.get("accion") == "baja" and en_periodo(str(e.get("ts", "")), dias, ahora)
    ]
    altas = [
        e
        for e in personal
        if e.get("accion") == "alta" and en_periodo(str(e.get("ts", "")), dias, ahora)
    ]
    plantilla_fin = plantilla_actual
    plantilla_inicio = plantilla_fin - len(altas) + len(bajas)
    if plantilla_inicio < 0:
        plantilla_inicio = 0
    media = Decimal(plantilla_inicio + plantilla_fin) / Decimal(2)
    rotacion = _pct(Decimal(len(bajas)), media) if media > 0 else (Decimal("0.0") if not bajas else None)

    repetidos = sum(1 for veces in nombres.values() if veces >= 2)
    distintos = len(nombres)
    retencion = _pct(Decimal(repetidos), Decimal(distintos)) if distintos else None

    terraza_total = sum(1 for m in mesas_ahora if m.get("zona") == "terraza")
    terraza_ocupadas = sum(
        1 for m in mesas_ahora if m.get("zona") == "terraza" and int(m.get("ocupada") or 0) > 0
    )
    ocupacion = _pct(Decimal(terraza_ocupadas), Decimal(terraza_total)) if terraza_total else None

    margen_ordenado = sorted(margen_producto.items(), key=lambda par: par[1], reverse=True)

    return {
        "cuentas": len(del_periodo),
        "ventas": ventas,
        "ticket_medio": medio(ventas, comensales),
        "ticket_medio_zona": {
            zona: medio(ventas_zona[zona], comensales_zona[zona]) for zona in ZONAS
        },
        "coste_producto_pct": _pct(coste_conocido, venta_con_coste),
        "hay_costes": venta_con_coste > 0,
        "revpash": revpash,
        "revpash_zona": revpash_zona,
        "margen": margen_ordenado,
        "sin_coste": sorted(sin_coste),
        "rotacion_minutos": (
            round(sum(minutos_mesa) / len(minutos_mesa)) if minutos_mesa else None
        ),
        "espera_minutos": (
            round(sum(minutos_servicio) / len(minutos_servicio)) if minutos_servicio else None
        ),
        "ocupacion_terraza": ocupacion,
        "terraza_ocupadas": terraza_ocupadas,
        "terraza_total": terraza_total,
        "terraza_por_hora": terraza_por_hora,
        "coste_personal_pct": _pct(coste_personal, ventas),
        "coste_personal": coste_personal,
        "sin_tarifa": sin_tarifa,
        "ventas_hora": ventas_hora,
        "rotacion_personal_pct": rotacion,
        "bajas": len(bajas),
        "retencion_pct": retencion,
        "clientes_distintos": distintos,
        "clientes_repetidos": repetidos,
        "incidencias": len(incidencias_periodo),
        "incidencias_pct": _pct(Decimal(len(incidencias_periodo)), Decimal(len(del_periodo)))
        if del_periodo
        else None,
    }
