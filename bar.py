import json
import re
import urllib.parse
from decimal import Decimal, InvalidOperation
from pathlib import Path

import streamlit as st

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
MARCA_DIR = Path(__file__).with_name("assets")
MARCA_FILE = MARCA_DIR / "marca_bar"

CONFIG_DEFAULT = {
    "whatsapp_telefono": "",  # Prefijo país + número, sin + ni espacios. Ej: 34612345678
    "nombre_bar": "Cuenta del Bar",
    "imagen_marca": "",  # Nombre de archivo dentro de assets/, vacío si no hay
}

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


def cargar_config() -> dict:
    config = dict(CONFIG_DEFAULT)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for clave, valor_def in CONFIG_DEFAULT.items():
                    if clave in raw and raw[clave] is not None:
                        config[clave] = raw[clave]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    config["whatsapp_telefono"] = normalizar_telefono(
        str(config.get("whatsapp_telefono", ""))
    )
    config["nombre_bar"] = str(config.get("nombre_bar") or CONFIG_DEFAULT["nombre_bar"]).strip()
    if not config["nombre_bar"]:
        config["nombre_bar"] = CONFIG_DEFAULT["nombre_bar"]
    config["imagen_marca"] = str(config.get("imagen_marca") or "").strip()
    # Si el archivo ya no existe, limpiar la referencia
    if config["imagen_marca"] and not (MARCA_DIR / config["imagen_marca"]).exists():
        config["imagen_marca"] = ""
    return config


def guardar_config(config: dict) -> None:
    payload = {
        "whatsapp_telefono": normalizar_telefono(
            str(config.get("whatsapp_telefono", ""))
        ),
        "nombre_bar": str(
            config.get("nombre_bar") or CONFIG_DEFAULT["nombre_bar"]
        ).strip()
        or CONFIG_DEFAULT["nombre_bar"],
        "imagen_marca": str(config.get("imagen_marca") or "").strip(),
    }
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


def ruta_imagen_marca(config: dict | None = None) -> Path | None:
    cfg = config if config is not None else st.session_state.get("config", {})
    nombre = str((cfg or {}).get("imagen_marca") or "").strip()
    if not nombre:
        return None
    ruta = MARCA_DIR / nombre
    return ruta if ruta.exists() else None


def guardar_imagen_marca(archivo) -> str:
    """Guarda la imagen subida en assets/ y devuelve el nombre de archivo."""
    MARCA_DIR.mkdir(parents=True, exist_ok=True)
    extension = Path(archivo.name).suffix.lower()
    if extension not in EXTENSIONES_IMAGEN:
        raise ValueError("Formato no válido. Usa PNG, JPG, WEBP o GIF.")
    # Borrar marcas anteriores
    for viejo in MARCA_DIR.glob("marca_bar.*"):
        viejo.unlink(missing_ok=True)
    destino = MARCA_DIR / f"marca_bar{extension}"
    destino.write_bytes(archivo.getvalue())
    return destino.name


def eliminar_imagen_marca() -> None:
    if MARCA_DIR.exists():
        for viejo in MARCA_DIR.glob("marca_bar.*"):
            viejo.unlink(missing_ok=True)


def init_state() -> None:
    if "menu" not in st.session_state:
        st.session_state.menu = cargar_menu()
    if "config" not in st.session_state:
        st.session_state.config = cargar_config()
    if "mesas" not in st.session_state:
        # Migración desde el modelo antiguo (pedidos planos = una sola mesa)
        if "pedidos" in st.session_state and st.session_state.pedidos:
            st.session_state.mesas = {
                "Mesa 1": {"comensales": dict(st.session_state.pedidos)}
            }
            del st.session_state.pedidos
        else:
            st.session_state.mesas = {}
    if "mesa_activa" not in st.session_state:
        mesas = list(st.session_state.mesas.keys())
        st.session_state.mesa_activa = mesas[0] if mesas else None
    if "persona_activa" not in st.session_state:
        st.session_state.persona_activa = None
    if "ultimo_aviso" not in st.session_state:
        st.session_state.ultimo_aviso = None
    # Limpieza residual del modelo antiguo
    if "pedidos" in st.session_state:
        del st.session_state.pedidos


def set_menu(menu: dict[str, Decimal]) -> None:
    st.session_state.menu = menu
    guardar_menu(menu)


def set_config(cambios: dict) -> None:
    """Actualiza la configuración fusionando con la actual y persistiendo."""
    actual = dict(st.session_state.config)
    actual.update(cambios)
    actual["whatsapp_telefono"] = normalizar_telefono(
        str(actual.get("whatsapp_telefono", ""))
    )
    actual["nombre_bar"] = (
        str(actual.get("nombre_bar") or CONFIG_DEFAULT["nombre_bar"]).strip()
        or CONFIG_DEFAULT["nombre_bar"]
    )
    actual["imagen_marca"] = str(actual.get("imagen_marca") or "").strip()
    st.session_state.config = {
        "whatsapp_telefono": actual["whatsapp_telefono"],
        "nombre_bar": actual["nombre_bar"],
        "imagen_marca": actual["imagen_marca"],
    }
    guardar_config(st.session_state.config)


def nombre_del_bar() -> str:
    return str(
        st.session_state.config.get("nombre_bar") or CONFIG_DEFAULT["nombre_bar"]
    )


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
        aviso = (
            f"{nombre_ok} movido de «{origen}» a «{mesa_destino}» "
            "(conserva sus consumiciones)."
        )
    else:
        st.session_state.mesas[mesa_destino]["comensales"][nombre_ok] = {}
        aviso = f"{nombre_ok} asignado a la mesa «{mesa_destino}»."

    st.session_state.mesa_activa = mesa_destino
    st.session_state.persona_activa = nombre_ok
    return None, aviso


def crear_mesa(nombre: str) -> str | None:
    nombre_ok = " ".join(nombre.strip().split())
    if not nombre_ok:
        return "El nombre de la mesa no puede estar vacío."
    if nombre_ok in st.session_state.mesas:
        return f"Ya existe la mesa «{nombre_ok}»."
    st.session_state.mesas[nombre_ok] = {"comensales": {}}
    st.session_state.mesa_activa = nombre_ok
    st.session_state.persona_activa = None
    return None


def eliminar_mesa(nombre: str) -> None:
    st.session_state.mesas.pop(nombre, None)
    if st.session_state.mesa_activa == nombre:
        restantes = list(st.session_state.mesas.keys())
        st.session_state.mesa_activa = restantes[0] if restantes else None
        st.session_state.persona_activa = None


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
    return None


def vaciar_mesa(nombre: str) -> None:
    if nombre in st.session_state.mesas:
        st.session_state.mesas[nombre]["comensales"] = {}
        if st.session_state.mesa_activa == nombre:
            st.session_state.persona_activa = None


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


def eliminar_producto_de_pedidos(producto: str) -> None:
    for mesa in st.session_state.mesas.values():
        for consumo in mesa["comensales"].values():
            consumo.pop(producto, None)


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
) -> str:
    """Mensaje en texto plano (sin emojis) para que WhatsApp no muestre caracteres rotos."""
    titulo = (nombre_bar or "Cuenta del Bar").strip()
    lineas = [f"*{titulo}*", "*CUENTA*"]
    if nombre_mesa:
        lineas.append(f"*Mesa: {nombre_mesa}*")
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
                help="Precio unitario del producto en euros.",
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
                    help=f"Cambia el precio de «{producto}» en euros.",
                    key=f"pre_{producto}",
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
            st.session_state.mesas = {}
            st.session_state.mesa_activa = None
            st.session_state.persona_activa = None
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
        c1, c2 = st.columns([3, 1])
        nombre = c1.text_input(
            "Nombre de la mesa",
            placeholder="Ej: Mesa 1, Terraza A, Barra",
            help="Identificador de la mesa en el local.",
        )
        crear = c2.form_submit_button(
            "Crear mesa",
            use_container_width=True,
            type="primary",
            help="Crea una mesa vacía y la deja seleccionada.",
        )
        if crear:
            error = crear_mesa(nombre)
            if error:
                st.error(error)
            else:
                st.success(f"Mesa creada y seleccionada: {nombre.strip()}")
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
                        st.success(f"Mesa renombrada a «{nuevo_nombre.strip()}».")
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
            del pedidos[persona]
            restantes = list(pedidos.keys())
            st.session_state.persona_activa = restantes[0] if restantes else None
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
                del comensales_de(mesa)[persona][producto]
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
    st.caption(
        f"Pulsa un producto para sumar una unidad al pedido de {persona} en «{mesa}». "
        "Verás el resumen actualizado al instante debajo."
    )

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
                        f"({precio:.2f} euros) al pedido de {persona} en «{mesa}»."
                    ),
                ):
                    consumo[producto] = cantidad_actual + 1
                    st.session_state.ultimo_aviso = (
                        f"Añadido: 1 × {nombre_limpio(producto)} a {persona} "
                        f"(«{mesa}»). Ahora lleva {consumo[producto]}."
                    )
                    st.rerun()

    st.markdown("---")
    ui_resumen_pedido_actual(persona)


def ajustar_cantidad(persona: str, producto: str, delta: int) -> None:
    mesa = st.session_state.mesa_activa
    consumo = comensales_de(mesa)[persona]
    nueva = consumo.get(producto, 0) + delta
    if nueva <= 0:
        consumo.pop(producto, None)
    else:
        consumo[producto] = nueva


def ui_ticket() -> Decimal:
    menu = st.session_state.menu
    mesa = asegurar_mesa_activa()
    st.subheader("Ticket de la mesa")

    if not mesa:
        st.info("No hay ninguna mesa seleccionada. Crea una en la pestaña Mesas.")
        return Decimal("0.00")

    st.caption(
        f"Ticket de **{mesa}**. Revisa cantidades e importes. "
        "Usa los botones para restar, sumar o eliminar líneas."
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
                        del pedidos[persona][producto]
                        st.rerun()

                st.markdown(f"**Total de {persona}: {total_persona:.2f} €**")
                total_general += total_persona

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


# ============================================
# APP
# ============================================
init_state()

with st.sidebar:
    logo = ruta_imagen_marca()
    if logo:
        st.image(str(logo), use_container_width=True)
    st.title(nombre_del_bar())
    st.caption("Gestiona mesas, comensales, menú, marca y precios.")

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
        st.session_state.mesas = {}
        st.session_state.mesa_activa = None
        st.session_state.persona_activa = None
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
            "Navegación: Mesas → Pedido → Ticket. "
            "Menú para productos; barra lateral para marca y WhatsApp."
        )
else:
    st.markdown(f"## {nombre_del_bar()}")
    st.caption(
        "Empieza por la pestaña Mesas, luego Pedido y Ticket. "
        "Configura nombre e imagen en la barra lateral → Marca del bar."
    )

tab_mesas, tab_pedido, tab_ticket, tab_menu = st.tabs(
    ["Mesas", "Pedido", "Ticket", "Menú (crear, editar, borrar)"]
)

with tab_mesas:
    ui_gestion_mesas()

with tab_pedido:
    persona = ui_personas()
    if persona:
        st.markdown("---")
        ui_anadir_consumiciones(persona)

with tab_ticket:
    total = ui_ticket()
    ui_resumen_y_whatsapp(total)

with tab_menu:
    ui_crud_menu()

st.caption(
    "Python + Streamlit · Precios con Decimal · Menú persistente en JSON · "
    "Mesas con comensales · Interfaz pensada para teclado, tooltips y lectores de pantalla."
)
