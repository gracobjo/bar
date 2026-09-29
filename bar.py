import io
import json
import re
import urllib.parse
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import streamlit as st

from ticket_fiscal import IVA_OPCIONES, desglose_iva, generar_pdf_ticket, huella_cuenta

# ============================================
# CONFIGURACIÓN
# ============================================
st.set_page_config(
    page_title="Cuenta del Bar",
    page_icon="🍺",
    layout="wide",
    initial_sidebar_state="expanded",
)

MENU_FILE = Path(__file__).with_name("menu_bar.json")
CONFIG_FILE = Path(__file__).with_name("config_bar.json")
MESAS_FILE = Path(__file__).with_name("mesas_bar.json")
VENTAS_FILE = Path(__file__).with_name("ventas_bar.json")
COSTES_FILE = Path(__file__).with_name("costes_bar.json")
PERSONAL_FILE = Path(__file__).with_name("personal_bar.json")
INCIDENCIAS_FILE = Path(__file__).with_name("incidencias_bar.json")
MARCA_DIR = Path(__file__).with_name("assets")
MARCA_FILE = MARCA_DIR / "marca_bar"

CONFIG_DEFAULT = {
    "whatsapp_telefono": "",  # Prefijo país + número, sin + ni espacios. Ej: 34612345678
    "nombre_bar": "Cuenta del Bar",
    "imagen_marca": "",  # Nombre de archivo dentro de assets/, vacío si no hay
    "barmans": [],  # Nombres de los barmans que usan la app en el móvil
    "razon_social": "",
    "nif": "",
    "direccion_fiscal": "",
    "iva_porcentaje": 10,  # IVA incluido en los precios del menú
    "serie_ticket": "A",
    "proximo_numero_ticket": 1,
    "administrador_nombre": "administrador",
    "administrador_pin": "",
    "coste_hora": {},
    "nota_google": None,
    "nota_tripadvisor": None,
}

ZONAS_MESA = ("barra", "mesas", "terraza")
ZONA_MESA_ETIQUETA = {"barra": "Barra", "mesas": "Mesas", "terraza": "Terraza"}

EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

MENU_DEFAULT = {
    "🍺 Caña": "1.90",
    "🍻 Cerveza": "2.50",
    "💧 Agua": "1.00",
    "🥔 Pincho tortilla": "3.50",
}

# Iconos seleccionables para productos del menú
ICONO_NINGUNO = "(Sin icono)"
ICONOS_PRODUCTO = [
    ICONO_NINGUNO,
    "🍺",  # Caña / cerveza de barril
    "🍻",  # Cervezas
    "🥂",  # Copas
    "🍷",  # Vino
    "🍸",  # Cóctel
    "🍹",  # Combinado
    "🥃",  # Cubata / whisky
    "🍾",  # Cava / champán
    "🧃",  # Zumo
    "🥤",  # Refresco
    "💧",  # Agua
    "☕",  # Café
    "🍵",  # Té
    "🥛",  # Leche
    "🥔",  # Tortilla / tapa
    "🥪",  # Bocadillo
    "🍔",  # Hamburguesa
    "🍕",  # Pizza
    "🌮",  # Taco
    "🥗",  # Ensalada
    "🍝",  # Pasta
    "🍖",  # Carne
    "🍤",  # Marisco
    "🧀",  # Queso
    "🍫",  # Postre
    "🍦",  # Helado
    "🍰",  # Tarta
    "🍪",  # Galleta
    "🥜",  # Frutos secos
]

# Estilos ligeros para una UX más clara
st.markdown(
    """
    <style>
    /* Dejar espacio bajo la barra de Streamlit para que las pestañas no se corten */
    .block-container { padding-top: 3.5rem; padding-bottom: 2rem; }
    div[data-testid="stTabs"] { margin-top: 0.5rem; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    .producto-chip {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        margin: 0.2rem;
        border-radius: 999px;
        background: #f0f2f6;
        font-size: 0.9rem;
    }
    /* Indicador visual de foco para teclado */
    button:focus-visible, a:focus-visible, input:focus-visible {
        outline: 3px solid #1f77b4 !important;
        outline-offset: 2px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================
# PERSISTENCIA DEL MENÚ Y CONFIGURACIÓN
# ============================================
def cargar_menu() -> dict[str, Decimal]:
    if MENU_FILE.exists():
        try:
            raw = json.loads(MENU_FILE.read_text(encoding="utf-8"))
            return {nombre: Decimal(str(precio)) for nombre, precio in raw.items()}
        except (json.JSONDecodeError, InvalidOperation, TypeError, ValueError):
            pass
    return {k: Decimal(v) for k, v in MENU_DEFAULT.items()}


def guardar_menu(menu: dict[str, Decimal]) -> None:
    payload = {nombre: f"{precio:.2f}" for nombre, precio in menu.items()}
    MENU_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalizar_nif(valor: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", valor or "").upper()


def normalizar_serie_ticket(valor: str) -> str:
    serie = re.sub(r"[^A-Za-z0-9]", "", valor or "").upper()
    return (serie or "A")[:10]


def normalizar_numero_ticket(valor) -> int:
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return 1
    return numero if numero >= 1 else 1


def normalizar_iva(valor) -> int:
    try:
        iva = int(valor)
    except (TypeError, ValueError):
        return int(CONFIG_DEFAULT["iva_porcentaje"])
    return iva if iva in IVA_OPCIONES else int(CONFIG_DEFAULT["iva_porcentaje"])


def normalizar_config(config: dict | None) -> dict:
    base = dict(CONFIG_DEFAULT)
    if isinstance(config, dict):
        for clave in CONFIG_DEFAULT:
            if clave in config and config[clave] is not None:
                base[clave] = config[clave]
    base["whatsapp_telefono"] = normalizar_telefono(str(base.get("whatsapp_telefono", "")))
    base["nombre_bar"] = (
        str(base.get("nombre_bar") or CONFIG_DEFAULT["nombre_bar"]).strip()
        or CONFIG_DEFAULT["nombre_bar"]
    )
    base["imagen_marca"] = str(base.get("imagen_marca") or "").strip()
    if base["imagen_marca"] and not (MARCA_DIR / base["imagen_marca"]).exists():
        base["imagen_marca"] = ""
    barmans = base.get("barmans") or []
    if not isinstance(barmans, list):
        barmans = []
    base["barmans"] = sorted(
        {str(b).strip() for b in barmans if str(b).strip()},
        key=str.casefold,
    )
    base["razon_social"] = " ".join(str(base.get("razon_social") or "").split())
    base["nif"] = normalizar_nif(str(base.get("nif") or ""))
    base["direccion_fiscal"] = str(base.get("direccion_fiscal") or "").strip()
    base["iva_porcentaje"] = normalizar_iva(base.get("iva_porcentaje"))
    base["serie_ticket"] = normalizar_serie_ticket(str(base.get("serie_ticket") or "A"))
    base["proximo_numero_ticket"] = normalizar_numero_ticket(
        base.get("proximo_numero_ticket")
    )
    base["administrador_nombre"] = (
        " ".join(str(base.get("administrador_nombre") or "").split()) or "administrador"
    )
    base["administrador_pin"] = str(base.get("administrador_pin") or "")
    tarifas = base.get("coste_hora") or {}
    base["coste_hora"] = tarifas if isinstance(tarifas, dict) else {}
    for clave_nota in ("nota_google", "nota_tripadvisor"):
        nota = base.get(clave_nota)
        if nota in ("", None):
            base[clave_nota] = None
            continue
        try:
            base[clave_nota] = float(nota)
        except (TypeError, ValueError):
            base[clave_nota] = None
    return base


def cargar_config() -> dict:
    config = dict(CONFIG_DEFAULT)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                config.update(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return normalizar_config(config)


def guardar_config(config: dict) -> None:
    payload = normalizar_config(config)
    CONFIG_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalizar_telefono(valor: str) -> str:
    """Deja solo dígitos (código de país + número). Quita +, espacios y guiones."""
    digitos = re.sub(r"\D", "", valor or "")
    if digitos.startswith("00"):
        digitos = digitos[2:]
    return digitos


def ahora_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def formatear_ts(ts: str) -> str:
    """Muestra fecha/hora legible; acepta ISO con espacio o T."""
    if not ts:
        return "—"
    try:
        bruto = ts.replace("T", " ", 1)
        dt = datetime.fromisoformat(bruto)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return ts


def ruta_imagen_marca(config: dict | None = None) -> Path | None:
    cfg = config if config is not None else st.session_state.get("config", {})
    nombre = str((cfg or {}).get("imagen_marca") or "").strip()
    if not nombre:
        return None
    ruta = MARCA_DIR / nombre
    return ruta if ruta.exists() else None


def png_logo_marca() -> bytes | None:
    """Convierte el logo del bar a PNG para incrustarlo en el PDF."""
    ruta = ruta_imagen_marca()
    if ruta is None:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        imagen = Image.open(ruta)
        if imagen.mode in ("RGBA", "LA") or (
            imagen.mode == "P" and "transparency" in imagen.info
        ):
            fondo = Image.new("RGB", imagen.size, (255, 255, 255))
            rgba = imagen.convert("RGBA")
            fondo.paste(rgba, mask=rgba.split()[-1])
            imagen = fondo
        else:
            imagen = imagen.convert("RGB")
        imagen.thumbnail((480, 240))
        buffer = io.BytesIO()
        imagen.save(buffer, format="PNG")
        return buffer.getvalue()
    except (OSError, ValueError):
        return None


def guardar_imagen_marca(archivo) -> str:
    """Guarda la imagen subida en assets/ y devuelve el nombre de archivo."""
    MARCA_DIR.mkdir(parents=True, exist_ok=True)
    extension = Path(archivo.name).suffix.lower()
    if extension not in EXTENSIONES_IMAGEN:
        raise ValueError("Formato no válido. Usa PNG, JPG, WEBP o GIF.")
    for viejo in MARCA_DIR.glob("marca_bar.*"):
        viejo.unlink(missing_ok=True)
    destino = MARCA_DIR / f"marca_bar{extension}"
    destino.write_bytes(archivo.getvalue())
    return destino.name


def eliminar_imagen_marca() -> None:
    if MARCA_DIR.exists():
        for viejo in MARCA_DIR.glob("marca_bar.*"):
            viejo.unlink(missing_ok=True)


def inferir_zona(nombre: str) -> str:
    texto = (nombre or "").casefold()
    if "barra" in texto:
        return "barra"
    if "terraza" in texto:
        return "terraza"
    return "mesas"


def normalizar_estructura_mesa(datos, nombre: str = "") -> dict:
    """Garantiza comensales + historial + abierta_en."""
    if not isinstance(datos, dict):
        return {
            "abierta_en": ahora_iso(),
            "comensales": {},
            "historial": [],
            "zona": inferir_zona(nombre),
            "asientos": 4,
            "incidencias": 0,
        }
    comensales = datos.get("comensales")
    if not isinstance(comensales, dict):
        comensales = {}
    # Normalizar cantidades a int
    limpios = {}
    for persona, consumo in comensales.items():
        if isinstance(consumo, dict):
            limpios[str(persona)] = {
                str(prod): int(cant)
                for prod, cant in consumo.items()
                if int(cant) > 0
            }
    historial = datos.get("historial")
    if not isinstance(historial, list):
        historial = []
    mesa = {
        "abierta_en": str(datos.get("abierta_en") or ahora_iso()),
        "comensales": limpios,
        "historial": historial,
    }
    ticket = datos.get("ticket_fiscal")
    if (
        isinstance(ticket, dict)
        and isinstance(ticket.get("huella"), str)
        and isinstance(ticket.get("datos"), dict)
        and ticket["datos"].get("ticket")
    ):
        mesa["ticket_fiscal"] = {
            "huella": ticket["huella"],
            "datos": ticket["datos"],
        }
    zona = datos.get("zona") if isinstance(datos, dict) else None
    mesa["zona"] = zona if zona in ZONAS_MESA else inferir_zona(nombre)
    try:
        asientos = int(datos.get("asientos")) if isinstance(datos, dict) else 4
    except (TypeError, ValueError):
        asientos = 4
    mesa["asientos"] = asientos if asientos >= 1 else 4
    try:
        mesa["incidencias"] = max(int(datos.get("incidencias") or 0), 0) if isinstance(datos, dict) else 0
    except (TypeError, ValueError):
        mesa["incidencias"] = 0
    return mesa


def cargar_mesas() -> dict:
    if not MESAS_FILE.exists():
        return {}
    try:
        raw = json.loads(MESAS_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {
            str(nombre): normalizar_estructura_mesa(datos, str(nombre))
            for nombre, datos in raw.items()
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def guardar_mesas() -> None:
    payload = {}
    for nombre, datos in st.session_state.mesas.items():
        mesa = normalizar_estructura_mesa(datos, nombre)
        payload[nombre] = mesa
        st.session_state.mesas[nombre] = mesa
    MESAS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _leer_lista_json(ruta: Path) -> list:
    if not ruta.exists():
        return []
    try:
        raw = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return raw if isinstance(raw, list) else []


def _escribir_json(ruta: Path, payload) -> None:
    ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cargar_ventas() -> list:
    return _leer_lista_json(VENTAS_FILE)


def cargar_incidencias() -> list:
    return _leer_lista_json(INCIDENCIAS_FILE)


def cargar_personal() -> list:
    return _leer_lista_json(PERSONAL_FILE)


def cargar_costes() -> dict[str, Decimal]:
    if not COSTES_FILE.exists():
        return {}
    try:
        raw = json.loads(COSTES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    costes = {}
    for nombre, valor in raw.items():
        try:
            importe = Decimal(str(valor)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            continue
        if importe > 0:
            costes[str(nombre)] = importe
    return costes


def guardar_costes(costes: dict[str, Decimal]) -> None:
    payload = {nombre: f"{importe:.2f}" for nombre, importe in costes.items() if importe > 0}
    _escribir_json(COSTES_FILE, payload)
    st.session_state.costes = cargar_costes()


def registrar_personal(accion: str, nombre: str) -> None:
    eventos = cargar_personal()
    eventos.append({"ts": ahora_iso(), "accion": accion, "nombre": nombre})
    _escribir_json(PERSONAL_FILE, eventos)


def asegurar_personal_inicial() -> None:
    if PERSONAL_FILE.exists():
        return
    eventos = [
        {"ts": "2020-01-01 00:00:00", "accion": "alta", "nombre": nombre}
        for nombre in lista_barmans()
    ]
    _escribir_json(PERSONAL_FILE, eventos)


def minutos_entre(inicio: str, fin: str) -> int | None:
    if not inicio or not fin:
        return None
    try:
        arranque = datetime.fromisoformat(str(inicio))
        cierre = datetime.fromisoformat(str(fin))
    except ValueError:
        return None
    return max(int((cierre - arranque).total_seconds() // 60), 0)


def cuenta_desde_mesa(nombre: str) -> dict | None:
    """Foto de una mesa con consumo, para el panel. None si no hay importe."""
    datos = st.session_state.mesas.get(nombre)
    if not datos:
        return None
    cantidades: dict[str, int] = {}
    for consumo in (datos.get("comensales") or {}).values():
        if not isinstance(consumo, dict):
            continue
        for producto, cantidad in consumo.items():
            cantidades[producto] = cantidades.get(producto, 0) + int(cantidad)
    if not cantidades:
        return None
    costes = st.session_state.get("costes") or {}
    lineas = []
    total = Decimal("0.00")
    for producto, cantidad in cantidades.items():
        precio = st.session_state.menu.get(producto, Decimal("0.00"))
        subtotal = (precio * cantidad).quantize(Decimal("0.01"))
        total += subtotal
        coste = costes.get(producto)
        lineas.append(
            {
                "producto": nombre_limpio(producto) or str(producto),
                "cantidad": cantidad,
                "precio": f"{precio:.2f}",
                "subtotal": f"{subtotal:.2f}",
                "coste": f"{coste:.2f}" if coste is not None else None,
            }
        )
    if total <= 0:
        return None
    abierta = str(datos.get("abierta_en") or ahora_iso())
    ticket = (datos.get("ticket_fiscal") or {}).get("datos") or {}
    fin = str(ticket.get("fecha") or ahora_iso())
    historial = datos.get("historial") or []
    primer = next(
        (
            evento.get("ts")
            for evento in historial
            if evento.get("accion") == "añadir" and evento.get("ts")
        ),
        None,
    )
    por_barman: dict[str, list[str]] = {}
    for evento in historial:
        barman = str(evento.get("barman") or "").strip()
        marca = evento.get("ts")
        if not barman or barman == "(sin identificar)" or not marca:
            continue
        por_barman.setdefault(barman, []).append(str(marca))
    minutos_barman = {}
    for barman, marcas in por_barman.items():
        tramo = minutos_entre(min(marcas), max(marcas))
        minutos_barman[barman] = tramo if tramo and tramo > 0 else 1
    zona = datos.get("zona") if datos.get("zona") in ZONAS_MESA else inferir_zona(nombre)
    return {
        "mesa": nombre,
        "abierta_en": abierta,
        "fecha": fin,
        "ticket": ticket.get("ticket") or "",
        "cerrada": bool(ticket.get("ticket")),
        "zona": zona,
        "asientos": int(datos.get("asientos") or 4),
        "n_comensales": len(datos.get("comensales") or {}),
        "comensales": list((datos.get("comensales") or {}).keys()),
        "barman": ticket.get("barman") or barman_activo() or "",
        "minutos_mesa": minutos_entre(abierta, fin),
        "minutos_servicio": minutos_entre(str(primer), fin) if primer else None,
        "minutos_barman": minutos_barman,
        "lineas": lineas,
        "total": f"{total:.2f}",
    }


def archivar_mesa(nombre: str) -> None:
    cuenta = cuenta_desde_mesa(nombre)
    if not cuenta:
        return
    ventas = [
        venta
        for venta in cargar_ventas()
        if not (
            venta.get("mesa") == cuenta["mesa"]
            and venta.get("abierta_en") == cuenta["abierta_en"]
        )
    ]
    ventas.append(cuenta)
    _escribir_json(VENTAS_FILE, ventas)


def cuentas_abiertas() -> list:
    abiertas = []
    for nombre in st.session_state.mesas:
        cuenta = cuenta_desde_mesa(nombre)
        if cuenta:
            abiertas.append(cuenta)
    return abiertas


def resumen_mesas_ahora() -> list:
    resumen = []
    for nombre, datos in st.session_state.mesas.items():
        zona = datos.get("zona") if datos.get("zona") in ZONAS_MESA else inferir_zona(nombre)
        resumen.append({"zona": zona, "ocupada": len(datos.get("comensales") or {})})
    return resumen


def registrar_incidencia(mesa: str, nota: str) -> None:
    if mesa not in st.session_state.mesas:
        return
    st.session_state.mesas[mesa]["incidencias"] = int(
        st.session_state.mesas[mesa].get("incidencias") or 0
    ) + 1
    guardar_mesas()
    eventos = cargar_incidencias()
    eventos.append(
        {
            "ts": ahora_iso(),
            "mesa": mesa,
            "barman": barman_activo() or "(sin identificar)",
            "nota": " ".join((nota or "").split()),
        }
    )
    _escribir_json(INCIDENCIAS_FILE, eventos)


def es_admin() -> bool:
    return bool(st.session_state.get("admin_ok"))


def init_state() -> None:
    if "menu" not in st.session_state:
        st.session_state.menu = cargar_menu()
    st.session_state.costes = cargar_costes()
    # Config y mesas siempre desde disco (varios móviles / barmans)
    st.session_state.config = cargar_config()
    if "pedidos" in st.session_state and st.session_state.pedidos:
        legacy = {
            "Mesa 1": normalizar_estructura_mesa(
                {"comensales": dict(st.session_state.pedidos)}
            )
        }
        del st.session_state.pedidos
        if not MESAS_FILE.exists():
            st.session_state.mesas = legacy
            guardar_mesas()
    st.session_state.mesas = cargar_mesas()
    if "mesa_activa" not in st.session_state:
        mesas = list(st.session_state.mesas.keys())
        st.session_state.mesa_activa = mesas[0] if mesas else None
    elif (
        st.session_state.mesa_activa
        and st.session_state.mesa_activa not in st.session_state.mesas
    ):
        mesas = list(st.session_state.mesas.keys())
        st.session_state.mesa_activa = mesas[0] if mesas else None
    if "persona_activa" not in st.session_state:
        st.session_state.persona_activa = None
    if "ultimo_aviso" not in st.session_state:
        st.session_state.ultimo_aviso = None
    if "barman_activo" not in st.session_state:
        st.session_state.barman_activo = None
    if "pedidos" in st.session_state:
        del st.session_state.pedidos
    barmans = st.session_state.config.get("barmans") or []
    if st.session_state.barman_activo not in barmans:
        st.session_state.barman_activo = None
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False
    asegurar_personal_inicial()


def set_menu(menu: dict[str, Decimal]) -> None:
    st.session_state.menu = menu
    guardar_menu(menu)


def set_config(cambios: dict) -> None:
    """Actualiza la configuración fusionando con la actual y persistiendo."""
    actual = dict(st.session_state.config)
    actual.update(cambios)
    st.session_state.config = normalizar_config(actual)
    guardar_config(st.session_state.config)
    if st.session_state.get("barman_activo") not in st.session_state.config["barmans"]:
        st.session_state.barman_activo = None


def nombre_del_bar() -> str:
    return str(
        st.session_state.config.get("nombre_bar") or CONFIG_DEFAULT["nombre_bar"]
    )


def lista_barmans() -> list[str]:
    return list(st.session_state.config.get("barmans") or [])


def barman_activo() -> str | None:
    return st.session_state.get("barman_activo")


def exigir_barman() -> bool:
    """True si hay barman identificado; si no, muestra aviso."""
    if barman_activo():
        return True
    st.warning(
        "Identifícate como barman en la barra lateral (**Quién soy**) "
        "antes de registrar pedidos. Así queda trazabilidad de quién apuntó cada cosa."
    )
    return False


def registrar_evento(
    mesa: str,
    accion: str,
    *,
    comensal: str = "",
    producto: str = "",
    cantidad_delta: int = 0,
    cantidad_resultante: int = 0,
    detalle: str = "",
    persistir: bool = True,
) -> None:
    if mesa not in st.session_state.mesas:
        return
    st.session_state.mesas[mesa].setdefault("historial", []).append(
        {
            "ts": ahora_iso(),
            "barman": barman_activo() or "(sin identificar)",
            "comensal": comensal,
            "accion": accion,
            "producto": producto,
            "cantidad_delta": int(cantidad_delta),
            "cantidad_resultante": int(cantidad_resultante),
            "detalle": detalle,
        }
    )
    if persistir:
        guardar_mesas()



# ============================================
# MESAS Y COMENSALES
# ============================================
def comensales_de(mesa: str | None = None) -> dict[str, dict]:
    """Devuelve el dict de comensales de una mesa (por defecto la activa)."""
    nombre = mesa if mesa is not None else st.session_state.mesa_activa
    if not nombre or nombre not in st.session_state.mesas:
        return {}
    return st.session_state.mesas[nombre]["comensales"]


def encontrar_mesa_de_comensal(nombre: str) -> str | None:
    """Devuelve la mesa donde está sentado el comensal, o None."""
    for mesa, datos in st.session_state.mesas.items():
        if nombre in datos["comensales"]:
            return mesa
    return None


def asegurar_mesa_activa() -> str | None:
    """Corrige mesa_activa si apunta a una mesa inexistente."""
    mesas = st.session_state.mesas
    if not mesas:
        st.session_state.mesa_activa = None
        st.session_state.persona_activa = None
        return None
    if st.session_state.mesa_activa not in mesas:
        st.session_state.mesa_activa = next(iter(mesas))
    return st.session_state.mesa_activa


def mover_comensal(nombre: str, mesa_destino: str) -> str | None:
    """Mueve un comensal (y su consumo) a otra mesa. Mantiene una sola mesa por persona."""
    if mesa_destino not in st.session_state.mesas:
        return f"La mesa «{mesa_destino}» no existe."
    origen = encontrar_mesa_de_comensal(nombre)
    if origen == mesa_destino:
        return None
    if origen:
        consumo = st.session_state.mesas[origen]["comensales"].pop(nombre)
    else:
        consumo = {}
    destino = st.session_state.mesas[mesa_destino]["comensales"]
    if nombre in destino:
        for producto, cantidad in consumo.items():
            destino[nombre][producto] = destino[nombre].get(producto, 0) + cantidad
    else:
        destino[nombre] = consumo
    return None


def asignar_comensal_a_mesa(nombre: str, mesa_destino: str) -> tuple[str | None, str]:
    """
    Asigna un comensal nuevo o existente a una mesa.
    Devuelve (error, mensaje_exito).
    """
    nombre_ok = " ".join(nombre.strip().split())
    if not nombre_ok:
        return "Escribe un nombre válido.", ""
    if mesa_destino not in st.session_state.mesas:
        return f"La mesa «{mesa_destino}» no existe.", ""

    origen = encontrar_mesa_de_comensal(nombre_ok)
    if origen == mesa_destino:
        return f"{nombre_ok} ya está en «{mesa_destino}».", ""

    if origen:
        mover_comensal(nombre_ok, mesa_destino)
        registrar_evento(
            mesa_destino,
            "mover",
            comensal=nombre_ok,
            detalle=f"Movido de «{origen}» a «{mesa_destino}»",
            persistir=False,
        )
        aviso = (
            f"{nombre_ok} movido de «{origen}» a «{mesa_destino}» "
            "(conserva sus consumiciones)."
        )
    else:
        st.session_state.mesas[mesa_destino]["comensales"][nombre_ok] = {}
        registrar_evento(
            mesa_destino,
            "asignar",
            comensal=nombre_ok,
            detalle=f"Comensal asignado a «{mesa_destino}»",
            persistir=False,
        )
        aviso = f"{nombre_ok} asignado a la mesa «{mesa_destino}»."

    st.session_state.mesa_activa = mesa_destino
    st.session_state.persona_activa = nombre_ok
    guardar_mesas()
    return None, aviso


def crear_mesa(nombre: str, zona: str = "mesas", asientos: int = 4) -> str | None:
    nombre_ok = " ".join(nombre.strip().split())
    if not nombre_ok:
        return "El nombre de la mesa no puede estar vacío."
    if nombre_ok in st.session_state.mesas:
        return f"Ya existe la mesa «{nombre_ok}»."
    abierta = ahora_iso()
    zona_ok = zona if zona in ZONAS_MESA else inferir_zona(nombre_ok)
    try:
        sitios = int(asientos)
    except (TypeError, ValueError):
        sitios = 4
    st.session_state.mesas[nombre_ok] = {
        "abierta_en": abierta,
        "comensales": {},
        "historial": [],
        "zona": zona_ok,
        "asientos": sitios if sitios >= 1 else 4,
        "incidencias": 0,
    }
    registrar_evento(
        nombre_ok,
        "abrir",
        detalle=f"Mesa abierta a las {formatear_ts(abierta)}",
        persistir=False,
    )
    st.session_state.mesa_activa = nombre_ok
    st.session_state.persona_activa = None
    guardar_mesas()
    return None


def eliminar_mesa(nombre: str) -> None:
    archivar_mesa(nombre)
    st.session_state.mesas.pop(nombre, None)
    if st.session_state.mesa_activa == nombre:
        restantes = list(st.session_state.mesas.keys())
        st.session_state.mesa_activa = restantes[0] if restantes else None
        st.session_state.persona_activa = None
    guardar_mesas()


def renombrar_mesa(antiguo: str, nuevo: str) -> str | None:
    nuevo_ok = " ".join(nuevo.strip().split())
    if not nuevo_ok:
        return "El nombre de la mesa no puede estar vacío."
    if nuevo_ok != antiguo and nuevo_ok in st.session_state.mesas:
        return f"Ya existe la mesa «{nuevo_ok}»."
    if nuevo_ok == antiguo:
        return None
    st.session_state.mesas[nuevo_ok] = st.session_state.mesas.pop(antiguo)
    if st.session_state.mesa_activa == antiguo:
        st.session_state.mesa_activa = nuevo_ok
    registrar_evento(
        nuevo_ok,
        "renombrar",
        detalle=f"Renombrada de «{antiguo}» a «{nuevo_ok}»",
        persistir=False,
    )
    guardar_mesas()
    return None


def vaciar_mesa(nombre: str) -> None:
    if nombre in st.session_state.mesas:
        registrar_evento(
            nombre,
            "vaciar",
            detalle="Mesa vaciada (comensales y consumiciones)",
            persistir=False,
        )
        archivar_mesa(nombre)
        st.session_state.mesas[nombre]["comensales"] = {}
        st.session_state.mesas[nombre].pop("ticket_fiscal", None)
        st.session_state.mesas[nombre]["abierta_en"] = ahora_iso()
        st.session_state.mesas[nombre]["incidencias"] = 0
        if st.session_state.mesa_activa == nombre:
            st.session_state.persona_activa = None
        guardar_mesas()


def total_mesa(mesa: str, menu: dict[str, Decimal]) -> Decimal:
    total = Decimal("0.00")
    for consumo in comensales_de(mesa).values():
        for producto, cantidad in consumo.items():
            total += menu.get(producto, Decimal("0.00")) * cantidad
    return total


def renombrar_producto_en_pedidos(antiguo: str, nuevo: str) -> None:
    for mesa in st.session_state.mesas.values():
        for consumo in mesa["comensales"].values():
            if antiguo in consumo:
                cantidad = consumo.pop(antiguo)
                consumo[nuevo] = consumo.get(nuevo, 0) + cantidad
    costes = dict(st.session_state.get("costes") or {})
    if antiguo in costes:
        costes[nuevo] = costes.pop(antiguo)
        guardar_costes(costes)
    guardar_mesas()


def eliminar_producto_de_pedidos(producto: str) -> None:
    for mesa in st.session_state.mesas.values():
        for consumo in mesa["comensales"].values():
            consumo.pop(producto, None)
    costes = dict(st.session_state.get("costes") or {})
    if producto in costes:
        costes.pop(producto, None)
        guardar_costes(costes)
    guardar_mesas()


# ============================================
# WHATSAPP
# ============================================
# Emojis y simbolos que a menudo se rompen en la pagina intermedia de WhatsApp
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F2FF"
    "\U000FE000-\U000FE0FF"
    "\U0000200D"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)


def nombre_limpio(producto: str) -> str:
    """Quita emojis y espacios sobrantes del nombre del producto."""
    limpio = _EMOJI_RE.sub("", producto)
    return " ".join(limpio.split())


def separar_icono_nombre(producto: str) -> tuple[str, str]:
    """Separa el icono inicial del nombre de texto."""
    nombre = nombre_limpio(producto)
    icono = producto.replace(nombre, "", 1).strip() if nombre else producto.strip()
    # Si el icono no está en la lista, lo añadimos visualmente al selector
    if not icono:
        icono = ICONO_NINGUNO
    return icono, nombre


def componer_producto(icono: str, nombre: str) -> str:
    """Une icono + nombre para la clave visible del menú."""
    nombre_ok = " ".join(nombre.strip().split())
    if not nombre_ok:
        return ""
    if not icono or icono == ICONO_NINGUNO:
        return nombre_ok
    return f"{icono} {nombre_ok}"


def opciones_icono(icono_actual: str | None = None) -> list[str]:
    """Lista de iconos; incluye el actual si no estaba en el catálogo."""
    opciones = list(ICONOS_PRODUCTO)
    if icono_actual and icono_actual not in opciones and icono_actual != ICONO_NINGUNO:
        opciones.insert(1, icono_actual)
    return opciones


def generar_mensaje_whatsapp(
    pedidos: dict,
    menu: dict[str, Decimal],
    nombre_bar: str = "",
    nombre_mesa: str = "",
    historial: list | None = None,
) -> str:
    """Mensaje en texto plano (sin emojis) para que WhatsApp no muestre caracteres rotos."""
    titulo = (nombre_bar or "Cuenta del Bar").strip()
    lineas = [f"*{titulo}*", "*CUENTA*"]
    if nombre_mesa:
        lineas.append(f"*Mesa: {nombre_mesa}*")
    lineas.append(f"Emitido: {formatear_ts(ahora_iso())}")
    if barman_activo():
        lineas.append(f"Barman: {barman_activo()}")
    lineas.append("")
    total_general = Decimal("0.00")

    for persona, consumo in pedidos.items():
        if not consumo:
            continue

        lineas.append(f"*{persona}*")
        total_persona = Decimal("0.00")

        for producto, cantidad in consumo.items():
            precio = menu.get(producto, Decimal("0.00"))
            subtotal = precio * cantidad
            total_persona += subtotal
            lineas.append(
                f"- {cantidad}x {nombre_limpio(producto)} = {subtotal:.2f} EUR"
            )

        lineas.append(f"*Total {persona}: {total_persona:.2f} EUR*")
        lineas.append("")
        total_general += total_persona

    lineas.append("-" * 20)
    if nombre_mesa:
        lineas.append(f"*TOTAL {nombre_mesa}: {total_general:.2f} EUR*")
    else:
        lineas.append(f"*TOTAL MESA: {total_general:.2f} EUR*")
    lineas.append("")
    lineas.append("Cuadre perfecto - No falta nada")

    if historial:
        lineas.append("")
        lineas.append("*TRAZABILIDAD (ultimos movimientos)*")
        for ev in historial[-12:]:
            ts = formatear_ts(str(ev.get("ts", "")))
            barman = ev.get("barman", "?")
            accion = ev.get("accion", "")
            comensal = ev.get("comensal", "")
            producto = nombre_limpio(str(ev.get("producto", "")))
            delta = ev.get("cantidad_delta", 0)
            if producto:
                lineas.append(
                    f"- {ts} | {barman} | {accion} {comensal} {producto} ({delta:+d})"
                )
            else:
                detalle = ev.get("detalle") or accion
                lineas.append(f"- {ts} | {barman} | {detalle}")
    return "\n".join(lineas)


def crear_enlace_whatsapp(mensaje: str, telefono: str = "") -> str:
    """Codifica el mensaje; si hay teléfono, abre el chat directo con ese número."""
    texto = urllib.parse.quote(mensaje, safe="", encoding="utf-8")
    telefono_ok = normalizar_telefono(telefono)
    if telefono_ok:
        return f"https://api.whatsapp.com/send?phone={telefono_ok}&text={texto}"
    return f"https://api.whatsapp.com/send?text={texto}"


# ============================================
# CRUD MENÚ
# ============================================
def ui_crud_menu() -> None:
    menu = st.session_state.menu

    st.subheader("Gestión del menú")
    st.caption(
        "Crea, edita o elimina productos y precios. "
        "Elige un icono de la lista para cada producto. "
        "Pasa el ratón o enfoca con Tab para ver la descripción de cada botón."
    )

    # --- CREAR ---
    with st.expander("Añadir producto nuevo", expanded=not menu):
        with st.form("form_nuevo_producto", clear_on_submit=True):
            c0, c1, c2 = st.columns([1, 2, 1])
            icono = c0.selectbox(
                "Icono",
                options=opciones_icono(),
                index=1,  # 🍺 por defecto
                help="Icono que se muestra junto al nombre del producto.",
            )
            nombre = c1.text_input(
                "Nombre del producto",
                placeholder="Ej: Vino tinto",
                help="Nombre del producto, sin emoji. El icono se elige a la izquierda.",
            )
            precio = c2.number_input(
                "Precio en euros",
                min_value=0.0,
                value=2.0,
                step=0.10,
                format="%.2f",
                help="Precio de venta. Lleva el IVA incluido.",
            )
            coste = st.number_input(
                "Coste en euros",
                min_value=0.0,
                value=0.0,
                step=0.05,
                format="%.2f",
                help="Lo que cuesta producir una unidad. 0 significa que todavía no lo sabes.",
            )
            vista_previa = componer_producto(icono, nombre or "…")
            st.caption(f"Vista previa: **{vista_previa}**")

            if st.form_submit_button(
                "Guardar producto",
                use_container_width=True,
                type="primary",
                help="Añade este producto al menú con el icono y el precio indicados.",
            ):
                clave = componer_producto(icono, nombre)
                if not clave:
                    st.error("El nombre no puede estar vacío.")
                elif clave in menu:
                    st.error(f"«{clave}» ya existe en el menú.")
                elif any(nombre_limpio(p).casefold() == nombre_limpio(clave).casefold() for p in menu):
                    st.error(
                        f"Ya existe un producto llamado «{nombre_limpio(clave)}» "
                        "(aunque tenga otro icono)."
                    )
                else:
                    nuevo = dict(menu)
                    nuevo[clave] = Decimal(f"{precio:.2f}")
                    set_menu(nuevo)
                    if coste > 0:
                        costes = dict(st.session_state.costes)
                        costes[clave] = Decimal(f"{coste:.2f}")
                        guardar_costes(costes)
                    st.success(f"Producto añadido: {clave} a {precio:.2f} euros.")
                    st.rerun()

    if not menu:
        st.info("Todavía no hay productos. Añade el primero arriba.")
        return

    st.markdown("---")
    st.markdown(f"#### Productos actuales ({len(menu)})")

    # --- LEER / ACTUALIZAR / ELIMINAR ---
    for producto, precio in list(menu.items()):
        icono_actual, nombre_actual = separar_icono_nombre(producto)
        with st.container(border=True):
            st.markdown(f"**Producto:** {producto} — **Precio actual:** {precio:.2f} €")
            with st.form(f"form_edit_{producto}"):
                e0, e1, e2 = st.columns([1, 2, 1])
                opciones = opciones_icono(icono_actual)
                idx = opciones.index(icono_actual) if icono_actual in opciones else 0
                nuevo_icono = e0.selectbox(
                    f"Icono de {nombre_actual or producto}",
                    options=opciones,
                    index=idx,
                    help=f"Cambia el icono de «{producto}».",
                    key=f"ico_{producto}",
                )
                nuevo_nombre = e1.text_input(
                    f"Nombre de {nombre_actual or producto}",
                    value=nombre_actual,
                    help="Nombre sin emoji. El icono se elige a la izquierda.",
                    key=f"nom_{producto}",
                )
                nuevo_precio = e2.number_input(
                    f"Precio de {nombre_actual or producto} (€)",
                    min_value=0.0,
                    value=float(precio),
                    step=0.10,
                    format="%.2f",
                    help=f"Cambia el precio de «{producto}» en euros. El IVA va incluido.",
                    key=f"pre_{producto}",
                )
                coste_actual = st.session_state.costes.get(producto)
                nuevo_coste = st.number_input(
                    f"Coste de {nombre_actual or producto} (€)",
                    min_value=0.0,
                    value=float(coste_actual or 0),
                    step=0.05,
                    format="%.2f",
                    help="Coste de producir una unidad. 0 significa desconocido y no entra en el margen.",
                    key=f"cos_{producto}",
                )
                st.caption(
                    f"Vista previa: **{componer_producto(nuevo_icono, nuevo_nombre or '…')}**"
                )

                b1, b2 = st.columns(2)
                with b1:
                    guardar = st.form_submit_button(
                        "Guardar cambios",
                        use_container_width=True,
                        type="primary",
                        help=(
                            f"Guarda el icono, el nombre y el precio de «{producto}». "
                            "Si cambian, los pedidos de la mesa se actualizan."
                        ),
                    )
                with b2:
                    borrar = st.form_submit_button(
                        "Eliminar producto",
                        use_container_width=True,
                        help=(
                            f"Elimina «{producto}» del menú y lo quita "
                            "de todos los pedidos de la mesa. No se puede deshacer."
                        ),
                    )

                if guardar:
                    clave = componer_producto(nuevo_icono, nuevo_nombre)
                    if not clave:
                        st.error("El nombre no puede estar vacío.")
                    elif clave != producto and clave in menu:
                        st.error(f"Ya existe «{clave}».")
                    elif any(
                        p != producto
                        and nombre_limpio(p).casefold() == nombre_limpio(clave).casefold()
                        for p in menu
                    ):
                        st.error(
                            f"Ya existe un producto llamado «{nombre_limpio(clave)}»."
                        )
                    else:
                        actualizado = dict(menu)
                        del actualizado[producto]
                        actualizado[clave] = Decimal(f"{nuevo_precio:.2f}")
                        if clave != producto:
                            renombrar_producto_en_pedidos(producto, clave)
                        set_menu(actualizado)
                        costes = dict(st.session_state.costes)
                        if nuevo_coste > 0:
                            costes[clave] = Decimal(f"{nuevo_coste:.2f}")
                        else:
                            costes.pop(clave, None)
                            costes.pop(producto, None)
                        guardar_costes(costes)
                        st.success(
                            f"Producto actualizado: {clave} a {nuevo_precio:.2f} euros."
                        )
                        st.rerun()

                if borrar:
                    actualizado = dict(menu)
                    del actualizado[producto]
                    eliminar_producto_de_pedidos(producto)
                    set_menu(actualizado)
                    st.success(f"Producto eliminado: {producto}.")
                    st.rerun()

    st.markdown("---")
    c_reset, c_info = st.columns([1, 2])
    with c_reset:
        if st.button(
            "Restaurar menú por defecto",
            use_container_width=True,
            help=(
                "Sustituye el menú actual por Caña, Cerveza, Agua y Pincho tortilla. "
                "También vacía la cuenta de la mesa."
            ),
        ):
            set_menu({k: Decimal(v) for k, v in MENU_DEFAULT.items()})
            for nombre_mesa_reset in list(st.session_state.mesas):
                archivar_mesa(nombre_mesa_reset)
            st.session_state.mesas = {}
            st.session_state.mesa_activa = None
            st.session_state.persona_activa = None
            guardar_mesas()
            st.success("Menú restaurado al valor por defecto. Mesas vaciadas.")
            st.rerun()
    with c_info:
        st.caption(f"Guardado en `{MENU_FILE.name}` · {len(menu)} producto(s)")


# ============================================
# MESAS (UI)
# ============================================
def ui_gestion_mesas() -> None:
    st.subheader("Gestión de mesas")
    st.caption(
        "Crea mesas y selecciónalas. Cada mesa tiene sus propios comensales. "
        "Luego ve a Pedido para apuntar consumiciones."
    )

    with st.form("form_nueva_mesa", clear_on_submit=True):
        nombre = st.text_input(
            "Nombre de la mesa",
            placeholder="Ej: Mesa 1, Terraza A, Barra",
            help="Identificador de la mesa en el local.",
        )
        c_zona, c_asientos, c_crear = st.columns([2, 1, 1])
        zona = c_zona.selectbox(
            "Zona",
            options=list(ZONAS_MESA),
            index=1,
            format_func=lambda valor: ZONA_MESA_ETIQUETA[valor],
            help="Sirve para el ticket medio y la ocupación: barra, mesas o terraza.",
        )
        asientos = c_asientos.number_input(
            "Asientos",
            min_value=1,
            value=4,
            step=1,
            help="Plazas de esta mesa. Entran en el ingreso por asiento y hora.",
        )
        crear = c_crear.form_submit_button(
            "Crear mesa",
            width="stretch",
            type="primary",
            help="Crea una mesa vacía y la deja seleccionada.",
        )
        if crear:
            if not barman_activo():
                st.error(
                    "Identifícate como barman en la barra lateral antes de abrir una mesa."
                )
            else:
                error = crear_mesa(nombre, zona, int(asientos))
                if error:
                    st.error(error)
                else:
                    st.success(
                        f"Mesa creada por {barman_activo()}: {nombre.strip()} "
                        f"({formatear_ts(ahora_iso())})"
                    )
                    st.rerun()

    mesas = st.session_state.mesas
    if not mesas:
        st.info("Todavía no hay mesas. Crea la primera arriba.")
        return

    st.markdown("---")
    st.markdown(f"#### Mesas abiertas ({len(mesas)})")
    menu = st.session_state.menu

    for nombre_mesa, datos in list(mesas.items()):
        comensales = datos["comensales"]
        n_comensales = len(comensales)
        total = total_mesa(nombre_mesa, menu)
        activa = st.session_state.mesa_activa == nombre_mesa

        with st.container(border=True):
            cab1, cab2 = st.columns([3, 1])
            with cab1:
                etiqueta = f"**{nombre_mesa}**"
                if activa:
                    etiqueta += " · *seleccionada*"
                st.markdown(etiqueta)
                st.caption(
                    f"{n_comensales} comensal(es) · Total: {total:.2f} €"
                )
            with cab2:
                if st.button(
                    "Seleccionar",
                    key=f"sel_mesa_{nombre_mesa}",
                    use_container_width=True,
                    type="primary" if activa else "secondary",
                    help=f"Trabajar con la mesa «{nombre_mesa}» en Pedido y Ticket.",
                    disabled=activa,
                ):
                    st.session_state.mesa_activa = nombre_mesa
                    st.session_state.persona_activa = None
                    st.rerun()

            if comensales:
                nombres = ", ".join(comensales.keys())
                st.caption(f"Comensales: {nombres}")
            else:
                st.caption("Sin comensales todavía.")

            with st.form(f"form_edit_mesa_{nombre_mesa}"):
                nuevo_nombre = st.text_input(
                    f"Renombrar {nombre_mesa}",
                    value=nombre_mesa,
                    help="Cambia el nombre de esta mesa.",
                    key=f"ren_mesa_{nombre_mesa}",
                )
                zona_actual = (
                    datos.get("zona") if datos.get("zona") in ZONAS_MESA else inferir_zona(nombre_mesa)
                )
                e_zona, e_asientos = st.columns(2)
                zona_mesa = e_zona.selectbox(
                    "Zona",
                    options=list(ZONAS_MESA),
                    index=list(ZONAS_MESA).index(zona_actual),
                    format_func=lambda valor: ZONA_MESA_ETIQUETA[valor],
                    key=f"zona_{nombre_mesa}",
                    help="Barra, mesas del salón o terraza.",
                )
                asientos_mesa = e_asientos.number_input(
                    "Asientos",
                    min_value=1,
                    value=int(datos.get("asientos") or 4),
                    step=1,
                    key=f"asientos_{nombre_mesa}",
                    help="Plazas para calcular el ingreso por asiento.",
                )
                b1, b2, b3 = st.columns(3)
                with b1:
                    guardar = st.form_submit_button(
                        "Guardar nombre",
                        use_container_width=True,
                        help=f"Guarda el nuevo nombre de «{nombre_mesa}».",
                    )
                with b2:
                    vaciar = st.form_submit_button(
                        "Vaciar mesa",
                        use_container_width=True,
                        help=(
                            f"Quita todos los comensales y consumiciones de «{nombre_mesa}». "
                            "La mesa sigue existiendo."
                        ),
                    )
                with b3:
                    borrar = st.form_submit_button(
                        "Cerrar mesa",
                        use_container_width=True,
                        help=f"Elimina la mesa «{nombre_mesa}» por completo.",
                    )

                if guardar:
                    error = renombrar_mesa(nombre_mesa, nuevo_nombre)
                    if error:
                        st.error(error)
                    else:
                        destino = " ".join(nuevo_nombre.strip().split()) or nombre_mesa
                        if destino in st.session_state.mesas:
                            st.session_state.mesas[destino]["zona"] = zona_mesa
                            st.session_state.mesas[destino]["asientos"] = int(asientos_mesa)
                            guardar_mesas()
                        st.success(f"Mesa actualizada: «{destino}».")
                        st.rerun()
                if vaciar:
                    vaciar_mesa(nombre_mesa)
                    st.success(f"Mesa «{nombre_mesa}» vaciada.")
                    st.rerun()
                if borrar:
                    eliminar_mesa(nombre_mesa)
                    st.success(f"Mesa «{nombre_mesa}» cerrada.")
                    st.rerun()


# ============================================
# PEDIDOS
# ============================================
def ui_personas() -> None | str:
    if not st.session_state.mesas:
        st.subheader("Pedido")
        st.info(
            "Primero crea al menos una mesa en la pestaña **Mesas**. "
            "Después podrás asignar comensales a cada mesa."
        )
        return None

    mesa = asegurar_mesa_activa()
    nombres_mesas = list(st.session_state.mesas.keys())

    st.subheader("Asignar comensales a mesas")
    st.caption(
        "Elige la mesa de destino y el nombre del comensal. "
        "Cada persona solo puede estar en una mesa."
    )

    with st.container(border=True):
        st.markdown("#### Nuevo comensal")
        c_nombre, c_mesa, c_btn = st.columns([2, 2, 1])
        with c_nombre:
            nueva = st.text_input(
                "Nombre del comensal",
                placeholder="Ej: Juan",
                help="Nombre de la persona que se sienta en la mesa elegida.",
                key="input_nueva_persona",
            )
        with c_mesa:
            idx_mesa = nombres_mesas.index(mesa) if mesa in nombres_mesas else 0
            mesa_destino = st.selectbox(
                "Mesa asignada",
                options=nombres_mesas,
                index=idx_mesa,
                help="Mesa a la que se asignará este comensal.",
                key="select_mesa_destino_comensal",
            )
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            anadir = st.button(
                "Asignar a mesa",
                use_container_width=True,
                type="primary",
                help=f"Asigna el comensal a la mesa «{mesa_destino}».",
            )

        st.caption(f"Se asignará a: **{mesa_destino}**")

        if anadir:
            if not exigir_barman():
                pass
            else:
                error, aviso = asignar_comensal_a_mesa(nueva, mesa_destino)
                if error:
                    st.warning(error)
                else:
                    st.success(aviso)
                    st.rerun()

    st.markdown("#### Comensales por mesa")
    hay_alguien = False
    for nombre_mesa, datos in st.session_state.mesas.items():
        comensales = list(datos["comensales"].keys())
        if not comensales:
            st.caption(f"**{nombre_mesa}**: (vacía)")
            continue
        hay_alguien = True
        st.markdown(
            f"**{nombre_mesa}** ({len(comensales)}): " + ", ".join(comensales)
        )
    if not hay_alguien:
        st.info("Todavía no hay comensales asignados a ninguna mesa.")
        return None

    st.markdown("---")
    st.markdown("#### ¿Quién pide ahora?")
    mesa = asegurar_mesa_activa()
    mesa_trabajo = st.selectbox(
        "Mesa en la que estás apuntando",
        options=nombres_mesas,
        index=nombres_mesas.index(mesa) if mesa in nombres_mesas else 0,
        help="Cambia de mesa para ver sus comensales y apuntar consumiciones.",
        key="select_mesa_trabajo_pedido",
    )
    if mesa_trabajo != st.session_state.mesa_activa:
        st.session_state.mesa_activa = mesa_trabajo
        st.session_state.persona_activa = None
        st.rerun()

    mesa = mesa_trabajo
    pedidos = comensales_de(mesa)
    nombres = list(pedidos.keys())
    if not nombres:
        st.info(
            f"«{mesa}» no tiene comensales. Asigna alguien arriba eligiendo "
            f"mesa «{mesa}»."
        )
        return None

    st.markdown(f"**Comensales en {mesa}** — pulsa un nombre para seleccionarlo:")
    cols = st.columns(min(len(nombres), 6))
    for i, nombre in enumerate(nombres):
        activa = st.session_state.persona_activa == nombre
        etiqueta = f"Seleccionada: {nombre}" if activa else nombre
        if cols[i % len(cols)].button(
            etiqueta,
            key=f"sel_{mesa}_{nombre}",
            use_container_width=True,
            type="primary" if activa else "secondary",
            help=(
                f"«{nombre}» (mesa «{mesa}») ya está seleccionada."
                if activa
                else f"Seleccionar a {nombre} de la mesa «{mesa}»."
            ),
        ):
            st.session_state.persona_activa = nombre
            st.rerun()

    if st.session_state.persona_activa not in pedidos:
        st.session_state.persona_activa = nombres[0]

    persona = st.session_state.persona_activa
    st.success(f"**{persona}** pide en la mesa **{mesa}**")

    otras = [m for m in nombres_mesas if m != mesa]
    c_mover, c_del = st.columns(2)
    with c_mover:
        if otras:
            mesa_nueva = st.selectbox(
                f"Mover a {persona} a otra mesa",
                options=["(elegir mesa)"] + otras,
                help=f"Cambia a {persona} de mesa conservando sus consumiciones.",
                key=f"mover_{mesa}_{persona}",
            )
            if mesa_nueva != "(elegir mesa)":
                if st.button(
                    f"Mover a {mesa_nueva}",
                    use_container_width=True,
                    help=f"Asigna a {persona} a «{mesa_nueva}».",
                    key=f"btn_mover_{mesa}_{persona}",
                ):
                    error, aviso = asignar_comensal_a_mesa(persona, mesa_nueva)
                    if error:
                        st.warning(error)
                    else:
                        st.success(aviso)
                        st.rerun()
        else:
            st.caption("Crea otra mesa para poder mover comensales.")

    with c_del:
        if st.button(
            f"Quitar a {persona} de {mesa}",
            use_container_width=True,
            help=(
                f"Elimina a {persona} y todas sus consumiciones de «{mesa}». "
                "No se puede deshacer."
            ),
        ):
            if not exigir_barman():
                st.stop()
            del pedidos[persona]
            registrar_evento(
                mesa,
                "quitar_comensal",
                comensal=persona,
                detalle=f"Comensal {persona} eliminado de «{mesa}»",
                persistir=False,
            )
            restantes = list(pedidos.keys())
            st.session_state.persona_activa = restantes[0] if restantes else None
            guardar_mesas()
            st.success(f"{persona} eliminado de «{mesa}».")
            st.rerun()

    return persona



def ui_resumen_pedido_actual(persona: str) -> None:
    """Muestra en vivo lo que lleva la persona seleccionada (sin ir al ticket)."""
    menu = st.session_state.menu
    mesa = st.session_state.mesa_activa
    consumo = comensales_de(mesa).get(persona, {})

    with st.container(border=True):
        st.markdown(f"**Pedido en curso de {persona}** · {mesa}")

        if not consumo:
            st.info(
                f"Todavía no hay consumiciones para {persona}. "
                "Pulsa un producto de abajo para añadir la primera."
            )
            return

        total = Decimal("0.00")
        unidades = 0
        for producto, cantidad in list(consumo.items()):
            precio = menu.get(producto, Decimal("0.00"))
            subtotal = precio * cantidad
            total += subtotal
            unidades += cantidad

            c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
            c1.write(f"{producto}")
            c1.caption(f"{precio:.2f} € / unidad")

            b_menos, b_cant, b_mas = c2.columns(3)
            if b_menos.button(
                "−",
                key=f"pedido_menos_{mesa}_{persona}_{producto}",
                help=f"Quitar 1 unidad de «{producto}» del pedido de {persona}.",
            ):
                if not exigir_barman():
                    st.stop()
                ajustar_cantidad(persona, producto, -1)
                st.session_state.ultimo_aviso = (
                    f"Quitada 1 unidad de «{nombre_limpio(producto)}» a {persona}."
                )
                st.rerun()
            b_cant.markdown(f"**{cantidad}**")
            if b_mas.button(
                "+",
                key=f"pedido_mas_{mesa}_{persona}_{producto}",
                help=f"Añadir 1 unidad más de «{producto}» a {persona}.",
            ):
                if not exigir_barman():
                    st.stop()
                ajustar_cantidad(persona, producto, 1)
                st.session_state.ultimo_aviso = (
                    f"Añadida 1 unidad de «{nombre_limpio(producto)}» a {persona}."
                )
                st.rerun()

            c3.write(f"{subtotal:.2f} €")
            if c4.button(
                "Quitar",
                key=f"pedido_del_{mesa}_{persona}_{producto}",
                help=f"Eliminar «{producto}» del pedido de {persona}.",
            ):
                if not exigir_barman():
                    st.stop()
                eliminar_linea_pedido(persona, producto)
                st.session_state.ultimo_aviso = (
                    f"Eliminado «{nombre_limpio(producto)}» del pedido de {persona}."
                )
                st.rerun()

        st.markdown(
            f"**Resumen:** {unidades} unidad(es) · **Total de {persona}: {total:.2f} €**"
        )


def ui_anadir_consumiciones(persona: str) -> None:
    menu = st.session_state.menu
    mesa = st.session_state.mesa_activa
    st.markdown(f"### Pedido de {persona} · {mesa}")
    if barman_activo():
        st.caption(
            f"Barman: **{barman_activo()}** · Cada pulsación se registra con fecha y hora. "
            f"Pulsa un producto para sumar una unidad a {persona} en «{mesa}»."
        )
    else:
        st.caption("Identifícate como barman para poder registrar consumiciones.")

    if not exigir_barman():
        return

    if st.session_state.ultimo_aviso:
        st.success(st.session_state.ultimo_aviso)
        st.session_state.ultimo_aviso = None

    if not menu:
        st.warning("No hay productos en el menú. Ve a la pestaña Menú para añadirlos.")
        return

    st.markdown("#### Añadir productos")
    n = len(menu)
    cols_por_fila = min(4, n)
    productos = list(menu.items())
    consumo = comensales_de(mesa).get(persona, {})

    for i in range(0, n, cols_por_fila):
        fila = productos[i : i + cols_por_fila]
        cols = st.columns(cols_por_fila)
        for j, (producto, precio) in enumerate(fila):
            cantidad_actual = consumo.get(producto, 0)
            etiqueta = f"{producto} — {precio:.2f} €"
            if cantidad_actual:
                etiqueta = f"{producto} (lleva {cantidad_actual}) — {precio:.2f} €"

            with cols[j]:
                if st.button(
                    etiqueta,
                    key=f"add_{mesa}_{persona}_{producto}",
                    use_container_width=True,
                    help=(
                        f"Añadir 1 unidad de «{producto}» "
                        f"({precio:.2f} euros) al pedido de {persona} en «{mesa}». "
                        "Queda registrado con fecha, hora y barman."
                    ),
                ):
                    ajustar_cantidad(persona, producto, 1)
                    nueva = comensales_de(mesa)[persona].get(producto, 0)
                    st.session_state.ultimo_aviso = (
                        f"Añadido: 1 × {nombre_limpio(producto)} a {persona} "
                        f"(«{mesa}») por {barman_activo()} a las "
                        f"{formatear_ts(ahora_iso())}. Ahora lleva {nueva}."
                    )
                    st.rerun()

    st.markdown("---")
    ui_resumen_pedido_actual(persona)


def ajustar_cantidad(persona: str, producto: str, delta: int) -> None:
    mesa = st.session_state.mesa_activa
    consumo = comensales_de(mesa)[persona]
    anterior = consumo.get(producto, 0)
    nueva = anterior + delta
    if nueva <= 0:
        consumo.pop(producto, None)
        nueva = 0
        accion = "eliminar" if delta < 0 and anterior > 0 else "quitar"
    else:
        consumo[producto] = nueva
        accion = "añadir" if delta > 0 else "quitar"
    registrar_evento(
        mesa,
        accion,
        comensal=persona,
        producto=producto,
        cantidad_delta=delta,
        cantidad_resultante=nueva,
        detalle=f"{accion} {nombre_limpio(producto)}",
    )


def eliminar_linea_pedido(persona: str, producto: str) -> None:
    mesa = st.session_state.mesa_activa
    consumo = comensales_de(mesa)[persona]
    anterior = consumo.pop(producto, 0)
    if anterior:
        registrar_evento(
            mesa,
            "eliminar",
            comensal=persona,
            producto=producto,
            cantidad_delta=-anterior,
            cantidad_resultante=0,
            detalle=f"Eliminadas {anterior} ud. de {nombre_limpio(producto)}",
        )


def ui_ticket() -> Decimal:
    menu = st.session_state.menu
    mesa = asegurar_mesa_activa()
    st.subheader("Ticket de la mesa")

    if not mesa:
        st.info("No hay ninguna mesa seleccionada. Crea una en la pestaña Mesas.")
        return Decimal("0.00")

    st.caption(
        f"Ticket de **{mesa}**. "
        + (
            f"Abierta: {formatear_ts(st.session_state.mesas[mesa].get('abierta_en', ''))}. "
            if mesa in st.session_state.mesas
            else ""
        )
        + "Revisa cantidades e importes. Cada cambio queda con fecha, hora y barman."
    )

    pedidos = comensales_de(mesa)
    if not pedidos:
        st.info(f"«{mesa}» no tiene comensales todavía.")
        return Decimal("0.00")

    total_general = Decimal("0.00")

    for persona, consumo in pedidos.items():
        total_persona = Decimal("0.00")
        with st.expander(f"Consumiciones de {persona}", expanded=True):
            if not consumo:
                st.caption(f"{persona} aún no tiene consumiciones.")
            else:
                cab1, cab2, cab3, cab4 = st.columns([3, 2, 1, 1])
                cab1.caption("Producto")
                cab2.caption("Cantidad")
                cab3.caption("Subtotal")
                cab4.caption("Acciones")

                for producto, cantidad in list(consumo.items()):
                    precio = menu.get(producto, Decimal("0.00"))
                    subtotal = precio * cantidad
                    total_persona += subtotal

                    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                    c1.write(f"{producto} ({precio:.2f} €/ud)")

                    b1, b2, b3 = c2.columns(3)
                    if b1.button(
                        "−",
                        key=f"menos_{mesa}_{persona}_{producto}",
                        help=(
                            f"Quitar 1 unidad de «{producto}» del pedido de {persona}. "
                            f"Cantidad actual: {cantidad}."
                        ),
                    ):
                        if not exigir_barman():
                            st.stop()
                        ajustar_cantidad(persona, producto, -1)
                        st.rerun()
                    b2.markdown(f"**{cantidad}**")
                    if b3.button(
                        "+",
                        key=f"mas_{mesa}_{persona}_{producto}",
                        help=(
                            f"Añadir 1 unidad de «{producto}» al pedido de {persona}. "
                            f"Cantidad actual: {cantidad}."
                        ),
                    ):
                        if not exigir_barman():
                            st.stop()
                        ajustar_cantidad(persona, producto, 1)
                        st.rerun()

                    c3.write(f"{subtotal:.2f} €")
                    if c4.button(
                        "Eliminar",
                        key=f"del_all_{mesa}_{persona}_{producto}",
                        help=(
                            f"Eliminar todas las unidades de «{producto}» "
                            f"({cantidad}) del pedido de {persona}."
                        ),
                    ):
                        if not exigir_barman():
                            st.stop()
                        eliminar_linea_pedido(persona, producto)
                        st.rerun()

                st.markdown(f"**Total de {persona}: {total_persona:.2f} €**")
                total_general += total_persona

    # Trazabilidad
    historial = list(st.session_state.mesas.get(mesa, {}).get("historial") or [])
    with st.expander(
        f"Trazabilidad de «{mesa}» ({len(historial)} eventos)",
        expanded=False,
    ):
        if not historial:
            st.caption("Aún no hay movimientos registrados.")
        else:
            st.caption("Útil para reclamaciones: quién apuntó qué y cuándo.")
            for ev in reversed(historial[-50:]):
                ts = formatear_ts(str(ev.get("ts", "")))
                barman = ev.get("barman", "?")
                accion = ev.get("accion", "")
                comensal = ev.get("comensal") or "—"
                producto = ev.get("producto") or ""
                detalle = ev.get("detalle") or ""
                delta = ev.get("cantidad_delta", 0)
                if producto:
                    st.markdown(
                        f"- **{ts}** · {barman} · `{accion}` · {comensal} · "
                        f"{producto} ({delta:+d})"
                    )
                else:
                    st.markdown(f"- **{ts}** · {barman} · {detalle or accion}")

    return total_general


def ui_resumen_y_whatsapp(total_general: Decimal) -> None:
    mesa = asegurar_mesa_activa()
    pedidos = comensales_de(mesa) if mesa else {}

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    personas = len(pedidos)
    items = sum(sum(c.values()) for c in pedidos.values())
    m1.metric("Mesa", mesa or "—", help="Mesa activa cuyo ticket se muestra.")
    m2.metric("Comensales", personas, help="Número de personas en la mesa activa.")
    m3.metric(
        "Consumiciones",
        items,
        help="Suma de todas las unidades pedidas en esta mesa.",
    )
    m4.metric(
        "Total mesa",
        f"{total_general:.2f} €",
        help="Importe total a pagar por esta mesa.",
    )

    if total_general > 0:
        st.success("Cuadre correcto. Todos los importes cuadran.")

    nota_incidencia = st.text_input(
        "Nota de la incidencia",
        placeholder="Ej: caña cambiada, se rompió la copa",
        help="Opcional. Queda registrada con la mesa, la hora y el barman.",
        key="nota_incidencia",
    )
    if st.button(
        "Registrar queja o error de comanda",
        help="Suma una incidencia de esta mesa para el indicador de quejas.",
    ):
        if not exigir_barman():
            pass
        elif not st.session_state.mesa_activa:
            st.error("No hay mesa activa.")
        else:
            registrar_incidencia(st.session_state.mesa_activa, nota_incidencia)
            st.success("Incidencia registrada.")
            st.rerun()

    st.markdown("---")
    st.subheader("Compartir por WhatsApp")

    telefono = st.session_state.config.get("whatsapp_telefono", "")
    if telefono:
        st.caption(f"Destino configurado: **+{telefono}** (barra lateral → WhatsApp del bar).")
    else:
        st.info(
            "No hay número del bar configurado. "
            "Se abrirá WhatsApp para que elijas el contacto. "
            "Puedes fijar el número en la barra lateral → **WhatsApp del bar**."
        )

    hay_pedidos = any(pedidos.values())
    if not mesa or not hay_pedidos:
        st.info("Añade consumiciones en la mesa activa para poder compartir la cuenta.")
        return

    mensaje = generar_mensaje_whatsapp(
        pedidos,
        st.session_state.menu,
        nombre_del_bar(),
        mesa,
        historial=list(st.session_state.mesas.get(mesa, {}).get("historial") or []),
    )
    with st.expander("Vista previa del mensaje de WhatsApp", expanded=False):
        st.code(mensaje, language=None)

    enlace = crear_enlace_whatsapp(mensaje, telefono)
    etiqueta = (
        f"Enviar cuenta de {mesa} por WhatsApp a +{telefono}"
        if telefono
        else f"Abrir WhatsApp con la cuenta de {mesa}"
    )
    st.link_button(
        etiqueta,
        enlace,
        use_container_width=True,
        type="primary",
        help=(
            f"Abre el chat de WhatsApp con +{telefono} y el resumen de «{mesa}»."
            if telefono
            else f"Abre WhatsApp con el resumen de «{mesa}» listo para elegir contacto."
        ),
    )
    ui_ticket_fiscal(mesa, pedidos)


def lineas_agrupadas(
    pedidos: dict, menu: dict[str, Decimal]
) -> tuple[list[dict], Decimal]:
    """Suma las consumiciones de todos los comensales, por producto."""
    cantidades: dict[str, int] = {}
    for consumo in pedidos.values():
        if not isinstance(consumo, dict):
            continue
        for producto, cantidad in consumo.items():
            cantidades[producto] = cantidades.get(producto, 0) + int(cantidad)
    orden = [p for p in menu if cantidades.get(p, 0) > 0]
    orden += [p for p in cantidades if p not in menu and cantidades[p] > 0]
    lineas = []
    total = Decimal("0.00")
    for producto in orden:
        cantidad = cantidades[producto]
        precio = menu.get(producto, Decimal("0.00"))
        subtotal = (precio * cantidad).quantize(Decimal("0.01"))
        total += subtotal
        lineas.append(
            {
                "producto": nombre_limpio(producto) or str(producto),
                "cantidad": cantidad,
                "precio": f"{precio:.2f}",
                "subtotal": f"{subtotal:.2f}",
            }
        )
    return lineas, total.quantize(Decimal("0.01"))


def fiscal_para_huella(config: dict) -> dict:
    return {
        "nif": config.get("nif", ""),
        "iva_porcentaje": config.get("iva_porcentaje", 0),
        "serie_ticket": config.get("serie_ticket", "A"),
        "razon_social": config.get("razon_social", ""),
        "direccion_fiscal": config.get("direccion_fiscal", ""),
    }


def ticket_de_mesa(mesa: str, huella: str) -> dict | None:
    guardado = (st.session_state.mesas.get(mesa) or {}).get("ticket_fiscal")
    if not isinstance(guardado, dict) or guardado.get("huella") != huella:
        return None
    datos = guardado.get("datos")
    if isinstance(datos, dict) and datos.get("ticket"):
        return datos
    return None


def siguiente_numero_ticket() -> tuple[str, str, int]:
    """Reserva el siguiente correlativo (A-00001) y lo guarda en la configuración."""
    config = st.session_state.config
    serie = str(config["serie_ticket"])
    numero = int(config["proximo_numero_ticket"])
    codigo = f"{serie}-{numero:05d}"
    set_config({"proximo_numero_ticket": numero + 1})
    return codigo, serie, numero


def emitir_ticket_fiscal(mesa: str, lineas: list[dict], total: Decimal) -> dict:
    """Asigna número si esta cuenta aún no tiene ticket y lo deja en la mesa."""
    config = st.session_state.config
    total_txt = f"{total:.2f}"
    huella = huella_cuenta(mesa, lineas, total_txt, fiscal_para_huella(config))
    ya = ticket_de_mesa(mesa, huella)
    if ya:
        return ya
    codigo, serie, numero = siguiente_numero_ticket()
    desglose = desglose_iva(total, int(config["iva_porcentaje"]))
    razon = str(config.get("razon_social") or "").strip() or nombre_del_bar()
    datos = {
        "ticket": codigo,
        "serie": serie,
        "numero": numero,
        "fecha": ahora_iso(),
        "razon_social": razon,
        "nombre_bar": nombre_del_bar(),
        "nif": config.get("nif") or "",
        "direccion": config.get("direccion_fiscal") or "",
        "mesa": mesa,
        "barman": barman_activo() or "(sin identificar)",
        "lineas": lineas,
        "iva_porcentaje": desglose["iva_porcentaje"],
        "base": desglose["base"],
        "cuota_iva": desglose["cuota_iva"],
        "total": desglose["total"],
    }
    st.session_state.mesas[mesa]["ticket_fiscal"] = {"huella": huella, "datos": datos}
    registrar_evento(
        mesa,
        "ticket_fiscal",
        detalle=f"Ticket fiscal {codigo} por {desglose['total']} EUR",
        persistir=True,
    )
    archivar_mesa(mesa)
    return datos


def ui_ticket_fiscal(mesa: str, pedidos: dict) -> None:
    """Botones de ticket térmico 80 mm y factura A4, con QR en el PDF."""
    st.markdown("---")
    st.subheader("Ticket fiscal")
    config = st.session_state.config
    if not config.get("razon_social") or not config.get("nif"):
        st.warning(
            "Faltan datos fiscales (razón social o NIF). "
            "Puedes completarlos en la barra lateral, en **Datos fiscales**."
        )
    else:
        st.caption(
            f"Emisor: **{config['razon_social']}** · NIF **{config['nif']}** · "
            f"IVA {config['iva_porcentaje']} % · "
            f"próximo número **{config['serie_ticket']}-{int(config['proximo_numero_ticket']):05d}**"
        )

    lineas, total = lineas_agrupadas(pedidos, st.session_state.menu)
    if not lineas or total <= 0:
        st.info("Añade consumiciones con importe para emitir el ticket fiscal.")
        return

    huella = huella_cuenta(
        mesa, lineas, f"{total:.2f}", fiscal_para_huella(config)
    )
    datos = ticket_de_mesa(mesa, huella)
    st.caption(
        "Los productos se agrupan sin distinguir comensal. "
        "Térmica 80 mm o A4. El QR se lee en el movil: la eñe y las tildes "
        "salen sin acento para que el lector no las cambie. "
        "La misma cuenta no consume otro número si vuelves a descargarla."
    )

    if datos is None:
        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                "🧾 Ticket térmico (80 mm)",
                use_container_width=True,
                type="primary",
                help="Asigna el número de ticket y prepara el PDF para impresora de 80 mm.",
            ):
                if exigir_barman():
                    emitir_ticket_fiscal(mesa, lineas, total)
                    st.rerun()
        with c2:
            if st.button(
                "📄 Factura A4",
                use_container_width=True,
                type="primary",
                help="Asigna el número de ticket y prepara el PDF en formato A4.",
            ):
                if exigir_barman():
                    emitir_ticket_fiscal(mesa, lineas, total)
                    st.rerun()
        return

    logo = png_logo_marca()
    try:
        pdf_termica = generar_pdf_ticket(datos, "termica", logo)
        pdf_a4 = generar_pdf_ticket(datos, "a4", logo)
    except Exception as err:
        st.error(f"No se pudo generar el PDF: {err}")
        return

    st.success(
        f"Ticket **{datos['ticket']}** emitido el {formatear_ts(str(datos.get('fecha', '')))} "
        f"por {datos.get('barman', '')}."
    )
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "🧾 Ticket térmico (80 mm)",
            data=pdf_termica,
            file_name=f"ticket-{datos['ticket']}-80mm.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            help="Descarga el PDF de 80 mm. Imprímelo con Ctrl+P en la impresora térmica.",
        )
    with d2:
        st.download_button(
            "📄 Factura A4",
            data=pdf_a4,
            file_name=f"factura-{datos['ticket']}-A4.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            help="Descarga el PDF en A4. Imprímelo con Ctrl+P en una impresora normal.",
        )


# ============================================
# APP
# ============================================
init_state()

with st.sidebar:
    logo = ruta_imagen_marca()
    if logo:
        st.image(str(logo), use_container_width=True)
    st.title(nombre_del_bar())
    st.caption("Varios barmans · mesas compartidas · trazabilidad con fecha/hora.")

    with st.expander(
        "Quién soy (barman)",
        expanded=not barman_activo(),
    ):
        st.caption(
            "Cada barman usa la app en su móvil. Identifícate para que "
            "los pedidos queden firmados con tu nombre, fecha y hora."
        )
        barmans = lista_barmans()
        if barmans:
            opciones = ["(elige tu nombre)"] + barmans
            actual = barman_activo()
            idx = opciones.index(actual) if actual in opciones else 0
            elegido = st.selectbox(
                "Barman en este teléfono",
                options=opciones,
                index=idx,
                help="Selecciona quién está usando la app ahora.",
                key="select_barman_activo",
            )
            if elegido != "(elige tu nombre)" and elegido != actual:
                st.session_state.barman_activo = elegido
                st.success(f"Identificado como {elegido}")
                st.rerun()
            if actual:
                st.caption(f"Activo: **{actual}** · {formatear_ts(ahora_iso())}")
            if st.button(
                "Cerrar sesión de barman",
                use_container_width=True,
                help="Quita la identificación de este teléfono.",
                disabled=not actual,
            ):
                st.session_state.barman_activo = None
                st.rerun()
        else:
            st.info("Todavía no hay barmans. Añade el primero abajo.")

        st.markdown("---")
        st.markdown("**Alta de barmans**")
        nuevo_barman = st.text_input(
            "Nombre del barman",
            placeholder="Ej: Ana",
            help="Nombre que aparecerá en la trazabilidad de cada pedido.",
            key="input_nuevo_barman",
        )
        c_ab, c_bb = st.columns(2)
        with c_ab:
            if st.button(
                "Añadir barman",
                use_container_width=True,
                type="primary",
                help="Registra un barman para poder seleccionarlo en los móviles.",
            ):
                nombre_b = " ".join((nuevo_barman or "").strip().split())
                if not nombre_b:
                    st.error("Escribe un nombre.")
                elif any(nombre_b.casefold() == b.casefold() for b in barmans):
                    st.error(f"«{nombre_b}» ya está en la lista.")
                else:
                    set_config({"barmans": barmans + [nombre_b]})
                    registrar_personal("alta", nombre_b)
                    st.session_state.barman_activo = nombre_b
                    st.success(f"Barman añadido e identificado: {nombre_b}")
                    st.rerun()
        with c_bb:
            if barmans:
                a_borrar = st.selectbox(
                    "Eliminar barman",
                    options=barmans,
                    key="select_borrar_barman",
                    label_visibility="collapsed",
                )
                if st.button(
                    "Eliminar",
                    use_container_width=True,
                    help=f"Quita a «{a_borrar}» de la lista de barmans.",
                ):
                    set_config(
                        {"barmans": [b for b in barmans if b != a_borrar]}
                    )
                    registrar_personal("baja", a_borrar)
                    st.success(f"Barman eliminado: {a_borrar}")
                    st.rerun()

    with st.expander("Administrador", expanded=not es_admin()):
        nombre_admin = st.session_state.config.get("administrador_nombre") or "administrador"
        pin_guardado = str(st.session_state.config.get("administrador_pin") or "")
        if es_admin():
            st.caption(f"Sesión de **{nombre_admin}** abierta en este teléfono.")
            if st.button(
                "Salir del panel",
                width="stretch",
                help="Cierra el panel de indicadores en este teléfono.",
            ):
                st.session_state.admin_ok = False
                st.rerun()
        elif not pin_guardado:
            st.caption("Elige un PIN de al menos 4 caracteres para crear el acceso.")
            pin_nuevo = st.text_input(
                "PIN de administrador",
                type="password",
                key="pin_crear_admin",
                help="Solo quien lo sepa verá el panel de indicadores.",
            )
            if st.button(
                "Crear administrador",
                type="primary",
                width="stretch",
                help="Guarda el usuario administrador y abre el panel.",
            ):
                if len((pin_nuevo or "").strip()) < 4:
                    st.error("El PIN necesita al menos 4 caracteres.")
                else:
                    set_config(
                        {
                            "administrador_nombre": "administrador",
                            "administrador_pin": pin_nuevo.strip(),
                        }
                    )
                    st.session_state.admin_ok = True
                    st.rerun()
        else:
            st.caption(f"Usuario: **{nombre_admin}**")
            pin_admin = st.text_input(
                "PIN",
                type="password",
                key="pin_entrar_admin",
                help="PIN del administrador.",
            )
            if st.button(
                "Entrar",
                type="primary",
                width="stretch",
                help="Abre la pestaña Panel con los indicadores.",
            ):
                if pin_admin == pin_guardado:
                    st.session_state.admin_ok = True
                    st.success(f"Has entrado como {nombre_admin}.")
                    st.rerun()
                else:
                    st.error("PIN incorrecto.")

    with st.expander("Marca del bar", expanded=False):
        st.caption("Nombre e imagen que se muestran en la app y en el mensaje de WhatsApp.")
        nombre_input = st.text_input(
            "Nombre del bar",
            value=nombre_del_bar(),
            placeholder="Ej: Bar El Rincón",
            help="Nombre comercial visible en la cabecera y en la cuenta de WhatsApp.",
            key="input_nombre_bar",
        )
        if st.button(
            "Guardar nombre",
            use_container_width=True,
            type="primary",
            help="Guarda el nombre del bar.",
            key="btn_guardar_nombre_bar",
        ):
            nombre_ok = nombre_input.strip()
            if not nombre_ok:
                st.error("El nombre del bar no puede estar vacío.")
            else:
                set_config({"nombre_bar": nombre_ok})
                st.success(f"Nombre guardado: {nombre_ok}")
                st.rerun()

        st.markdown("---")
        st.markdown("**Imagen de marca**")
        if logo:
            st.image(str(logo), caption="Imagen actual", use_container_width=True)
        archivo = st.file_uploader(
            "Subir logo o imagen",
            type=["png", "jpg", "jpeg", "webp", "gif"],
            help="PNG, JPG, WEBP o GIF. Sustituye la imagen anterior si ya había una.",
            key="uploader_marca",
        )
        c_img1, c_img2 = st.columns(2)
        with c_img1:
            if st.button(
                "Guardar imagen",
                use_container_width=True,
                type="primary",
                help="Guarda la imagen seleccionada como marca del bar.",
                disabled=archivo is None,
            ):
                try:
                    nombre_archivo = guardar_imagen_marca(archivo)
                    set_config({"imagen_marca": nombre_archivo})
                    st.success("Imagen de marca guardada.")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))
        with c_img2:
            if st.button(
                "Quitar imagen",
                use_container_width=True,
                help="Elimina la imagen de marca guardada.",
                disabled=logo is None,
            ):
                eliminar_imagen_marca()
                set_config({"imagen_marca": ""})
                st.success("Imagen de marca eliminada.")
                st.rerun()

    with st.expander("Ayuda de accesibilidad", expanded=False):
        st.markdown(
            """
- Usa **Tab** / **Mayús+Tab** para moverte entre controles.
- Al enfocar o pasar el ratón por un botón verás **qué hace**.
- Los botones tienen **texto** (no solo iconos).
- Los avisos de éxito o error aparecen **por escrito** en pantalla.
- Las pestañas son: Mesas, Pedido, Ticket y Menú.
- En Ticket puedes descargar el PDF fiscal (térmica 80 mm o A4) con QR.
            """
        )

    with st.expander("WhatsApp del bar", expanded=False):
        st.caption(
            "Número con prefijo de país, sin + ni espacios. "
            "España: 34 + móvil (ej. 34612345678)."
        )
        telefono_actual = st.session_state.config.get("whatsapp_telefono", "")
        telefono_input = st.text_input(
            "Teléfono WhatsApp",
            value=telefono_actual,
            placeholder="34612345678",
            help=(
                "Chat al que se enviará la cuenta. "
                "Déjalo vacío para elegir el contacto manualmente cada vez."
            ),
            key="input_whatsapp_telefono",
        )
        c_guardar, c_borrar = st.columns(2)
        with c_guardar:
            if st.button(
                "Guardar número",
                use_container_width=True,
                type="primary",
                help="Guarda el número de WhatsApp del bar.",
            ):
                telefono_ok = normalizar_telefono(telefono_input)
                if telefono_input.strip() and len(telefono_ok) < 8:
                    st.error("El número parece demasiado corto. Incluye el prefijo del país.")
                else:
                    set_config({"whatsapp_telefono": telefono_ok})
                    if telefono_ok:
                        st.success(f"WhatsApp del bar guardado: +{telefono_ok}")
                    else:
                        st.success("Número borrado. Se elegirá el contacto al enviar.")
                    st.rerun()
        with c_borrar:
            if st.button(
                "Quitar número",
                use_container_width=True,
                help="Elimina el número guardado.",
                disabled=not telefono_actual,
            ):
                set_config({"whatsapp_telefono": ""})
                st.success("Número de WhatsApp eliminado.")
                st.rerun()
        if telefono_actual:
            st.caption(f"Activo: **+{telefono_actual}**")

    with st.expander("Datos fiscales", expanded=False):
        st.caption(
            "Salen en el ticket PDF. Los precios del menú se tratan como IVA incluido. "
            "Con IVA 0 % el ticket indica «IVA incluido en los precios»."
        )
        cfg_fiscal = st.session_state.config
        razon_input = st.text_input(
            "Razón social",
            value=cfg_fiscal.get("razon_social", ""),
            placeholder="Ej: Bar El Rincón S.L.",
            help="Nombre fiscal del emisor, tal como debe aparecer en el ticket.",
            key="input_razon_social",
        )
        nif_input = st.text_input(
            "NIF/CIF",
            value=cfg_fiscal.get("nif", ""),
            placeholder="B12345678",
            help="NIF o CIF. Se guardan solo letras y números, en mayúsculas.",
            key="input_nif",
        )
        direccion_input = st.text_area(
            "Dirección fiscal",
            value=cfg_fiscal.get("direccion_fiscal", ""),
            placeholder="Calle Mayor 1, 28001 Madrid",
            help="Dirección que se imprime bajo el NIF.",
            key="input_direccion_fiscal",
            height=80,
        )
        opciones_iva = list(IVA_OPCIONES)
        iva_actual = int(cfg_fiscal.get("iva_porcentaje", 10))
        if iva_actual not in opciones_iva:
            iva_actual = 10
        iva_input = st.selectbox(
            "Tipo de IVA",
            options=opciones_iva,
            index=opciones_iva.index(iva_actual),
            format_func=lambda valor: f"{valor} %",
            help="Un solo tipo para todo el ticket. 10 % es el de hostelería; 21 % el general.",
            key="select_iva",
        )
        c_serie, c_num = st.columns(2)
        with c_serie:
            serie_input = st.text_input(
                "Serie del ticket",
                value=cfg_fiscal.get("serie_ticket", "A"),
                help="Prefijo del número. Ejemplo: A-00001.",
                key="input_serie_ticket",
            )
        with c_num:
            # Si se emite un ticket, el correlativo cambia fuera de este campo.
            proximo_real = int(cfg_fiscal.get("proximo_numero_ticket", 1))
            if (
                "input_proximo_ticket" not in st.session_state
                or st.session_state.get("_fiscal_numero_sync") != proximo_real
            ):
                st.session_state.input_proximo_ticket = proximo_real
            st.session_state._fiscal_numero_sync = proximo_real
            numero_input = st.number_input(
                "Próximo número de ticket",
                min_value=1,
                step=1,
                help="El siguiente ticket usará este número y luego sumará uno.",
                key="input_proximo_ticket",
            )
        if st.button(
            "Guardar datos fiscales",
            use_container_width=True,
            type="primary",
            help="Guarda razón social, NIF, dirección, IVA, serie y próximo número.",
        ):
            set_config(
                {
                    "razon_social": razon_input,
                    "nif": nif_input,
                    "direccion_fiscal": direccion_input,
                    "iva_porcentaje": int(iva_input),
                    "serie_ticket": serie_input,
                    "proximo_numero_ticket": int(numero_input),
                }
            )
            guardado = st.session_state.config
            st.success(
                "Datos fiscales guardados. Próximo ticket: "
                f"{guardado['serie_ticket']}-{int(guardado['proximo_numero_ticket']):05d}"
            )
            st.rerun()
        st.caption(
            "Próximo ticket: "
            f"**{cfg_fiscal['serie_ticket']}-{int(cfg_fiscal['proximo_numero_ticket']):05d}**"
        )

    st.markdown("---")

    mesa_act = asegurar_mesa_activa()
    st.markdown("**Mesas**")
    if not st.session_state.mesas:
        st.caption("Sin mesas. Créalas en la pestaña Mesas.")
    else:
        for nombre_mesa, datos in st.session_state.mesas.items():
            n = len(datos["comensales"])
            marca = "→ " if nombre_mesa == mesa_act else ""
            st.markdown(f"- {marca}**{nombre_mesa}**: {n} comensal(es)")
        if mesa_act:
            st.caption(f"Activa: **{mesa_act}**")

    menu = st.session_state.menu
    if menu:
        st.markdown("**Menú rápido**")
        for producto, precio in menu.items():
            st.markdown(f"- {producto}: **{precio:.2f} €**")
    else:
        st.warning("Menú vacío. Ve a la pestaña Menú para añadir productos.")

    st.markdown("---")
    if st.button(
        "Vaciar mesa activa",
        use_container_width=True,
        help="Quita comensales y consumiciones de la mesa seleccionada. La mesa sigue existiendo.",
        disabled=not mesa_act,
    ):
        vaciar_mesa(mesa_act)
        st.success(f"Mesa «{mesa_act}» vaciada.")
        st.rerun()
    if st.button(
        "Cerrar todas las mesas",
        use_container_width=True,
        help="Elimina todas las mesas y sus cuentas. El menú no se modifica.",
    ):
        for nombre_cierre in list(st.session_state.mesas):
            archivar_mesa(nombre_cierre)
        st.session_state.mesas = {}
        st.session_state.mesa_activa = None
        st.session_state.persona_activa = None
        guardar_mesas()
        st.success("Todas las mesas han sido cerradas.")
        st.rerun()

# Cabecera principal con marca
logo_principal = ruta_imagen_marca()
if logo_principal:
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        st.image(str(logo_principal), use_container_width=True)
    with col_titulo:
        st.markdown(f"## {nombre_del_bar()}")
        st.caption(
            "Navegación: identifícate como barman → Mesas → Pedido → Ticket. "
            "Menú y marca en la barra lateral. Varios móviles comparten las mesas."
        )
else:
    st.markdown(f"## {nombre_del_bar()}")
    st.caption(
        "Identifícate en Quién soy, crea mesas y apunta pedidos. "
        "Todo queda con fecha, hora y barman para reclamaciones."
    )

nombres_pestanas = ["Mesas", "Pedido", "Ticket", "Menú (crear, editar, borrar)"]
if es_admin():
    nombres_pestanas.append("Panel")
pestanas = st.tabs(nombres_pestanas)

with pestanas[0]:
    ui_gestion_mesas()

with pestanas[1]:
    persona = ui_personas()
    if persona:
        st.markdown("---")
        ui_anadir_consumiciones(persona)

with pestanas[2]:
    total = ui_ticket()
    ui_resumen_y_whatsapp(total)

with pestanas[3]:
    ui_crud_menu()

if es_admin():
    with pestanas[4]:
        from dashboard import ui_dashboard

        ui_dashboard()

st.caption(
    "Python + Streamlit · Precios con Decimal · Menú persistente en JSON · "
    "Mesas con comensales · Ticket fiscal PDF con QR · "
    "Interfaz pensada para teclado, tooltips y lectores de pantalla."
)
