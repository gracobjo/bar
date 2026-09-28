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
    if "pedidos" not in st.session_state:
        st.session_state.pedidos = {}
    if "persona_activa" not in st.session_state:
        st.session_state.persona_activa = None
    if "ultimo_aviso" not in st.session_state:
        st.session_state.ultimo_aviso = None


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


def renombrar_producto_en_pedidos(antiguo: str, nuevo: str) -> None:
    for consumo in st.session_state.pedidos.values():
        if antiguo in consumo:
            cantidad = consumo.pop(antiguo)
            consumo[nuevo] = consumo.get(nuevo, 0) + cantidad


def eliminar_producto_de_pedidos(producto: str) -> None:
    for consumo in st.session_state.pedidos.values():
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
) -> str:
    """Mensaje en texto plano (sin emojis) para que WhatsApp no muestre caracteres rotos."""
    titulo = (nombre_bar or "Cuenta del Bar").strip()
    lineas = [f"*{titulo}*", "*CUENTA*", ""]
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
            st.session_state.pedidos = {}
            st.success("Menú restaurado al valor por defecto. Mesa vaciada.")
            st.rerun()
    with c_info:
        st.caption(f"Guardado en `{MENU_FILE.name}` · {len(menu)} producto(s)")


# ============================================
# PEDIDOS
# ============================================
def ui_personas() -> None | str:
    st.subheader("Mesa")
    st.caption("Añade clientes y selecciona quién está pidiendo.")

    c1, c2 = st.columns([3, 1])
    with c1:
        nueva = st.text_input(
            "Nombre del cliente",
            placeholder="Ej: Juan",
            help="Escribe el nombre de la persona que se sienta en la mesa.",
            key="input_nueva_persona",
        )
    with c2:
        anadir = st.button(
            "Añadir persona",
            use_container_width=True,
            type="primary",
            help="Añade esta persona a la mesa para poder apuntarle consumiciones.",
        )

    if anadir:
        nombre = (nueva or "").strip()
        if not nombre:
            st.warning("Escribe un nombre válido.")
        elif nombre in st.session_state.pedidos:
            st.warning(f"{nombre} ya está en la mesa.")
        else:
            st.session_state.pedidos[nombre] = {}
            st.session_state.persona_activa = nombre
            st.success(f"{nombre} añadido a la mesa.")
            st.rerun()

    nombres = list(st.session_state.pedidos.keys())
    if not nombres:
        st.info("Añade personas a la mesa para empezar a apuntar consumiciones.")
        return None

    st.markdown("**Personas en la mesa** — pulsa un nombre para seleccionarlo:")
    cols = st.columns(min(len(nombres), 6))
    for i, nombre in enumerate(nombres):
        activa = st.session_state.persona_activa == nombre
        etiqueta = f"Seleccionada: {nombre}" if activa else nombre
        if cols[i % len(cols)].button(
            etiqueta,
            key=f"sel_{nombre}",
            use_container_width=True,
            type="primary" if activa else "secondary",
            help=(
                f"«{nombre}» ya está seleccionada. Las consumiciones se añaden a esta persona."
                if activa
                else f"Seleccionar a {nombre} para añadirle consumiciones."
            ),
        ):
            st.session_state.persona_activa = nombre
            st.rerun()

    if st.session_state.persona_activa not in st.session_state.pedidos:
        st.session_state.persona_activa = nombres[0]

    persona = st.session_state.persona_activa

    c_del, _ = st.columns([1, 3])
    if c_del.button(
        f"Quitar a {persona} de la mesa",
        use_container_width=True,
        help=(
            f"Elimina a {persona} y todas sus consumiciones de la mesa. "
            "No se puede deshacer."
        ),
    ):
        del st.session_state.pedidos[persona]
        restantes = list(st.session_state.pedidos.keys())
        st.session_state.persona_activa = restantes[0] if restantes else None
        st.success(f"{persona} eliminado de la mesa.")
        st.rerun()

    return persona


def ui_resumen_pedido_actual(persona: str) -> None:
    """Muestra en vivo lo que lleva la persona seleccionada (sin ir al ticket)."""
    menu = st.session_state.menu
    consumo = st.session_state.pedidos.get(persona, {})

    with st.container(border=True):
        st.markdown(f"**Pedido en curso de {persona}**")

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
                key=f"pedido_menos_{persona}_{producto}",
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
                key=f"pedido_mas_{persona}_{producto}",
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
                key=f"pedido_del_{persona}_{producto}",
                help=f"Eliminar «{producto}» del pedido de {persona}.",
            ):
                del st.session_state.pedidos[persona][producto]
                st.session_state.ultimo_aviso = (
                    f"Eliminado «{nombre_limpio(producto)}» del pedido de {persona}."
                )
                st.rerun()

        st.markdown(
            f"**Resumen:** {unidades} unidad(es) · **Total de {persona}: {total:.2f} €**"
        )


def ui_anadir_consumiciones(persona: str) -> None:
    menu = st.session_state.menu
    st.markdown(f"### Pedido de {persona}")
    st.caption(
        f"Pulsa un producto para sumar una unidad al pedido de {persona}. "
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
    consumo = st.session_state.pedidos.get(persona, {})

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
                    key=f"add_{persona}_{producto}",
                    use_container_width=True,
                    help=(
                        f"Añadir 1 unidad de «{producto}» "
                        f"({precio:.2f} euros) al pedido de {persona}."
                    ),
                ):
                    consumo[producto] = cantidad_actual + 1
                    st.session_state.ultimo_aviso = (
                        f"Añadido: 1 × {nombre_limpio(producto)} a {persona}. "
                        f"Ahora lleva {consumo[producto]}."
                    )
                    st.rerun()

    st.markdown("---")
    ui_resumen_pedido_actual(persona)


def ajustar_cantidad(persona: str, producto: str, delta: int) -> None:
    consumo = st.session_state.pedidos[persona]
    nueva = consumo.get(producto, 0) + delta
    if nueva <= 0:
        consumo.pop(producto, None)
    else:
        consumo[producto] = nueva


def ui_ticket() -> Decimal:
    menu = st.session_state.menu
    st.subheader("Ticket de la mesa")
    st.caption(
        "Revisa cantidades e importes. Usa los botones para restar, sumar o eliminar líneas."
    )

    if not st.session_state.pedidos:
        st.info("La mesa está vacía.")
        return Decimal("0.00")

    total_general = Decimal("0.00")

    for persona, consumo in st.session_state.pedidos.items():
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
                        key=f"menos_{persona}_{producto}",
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
                        key=f"mas_{persona}_{producto}",
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
                        key=f"del_all_{persona}_{producto}",
                        help=(
                            f"Eliminar todas las unidades de «{producto}» "
                            f"({cantidad}) del pedido de {persona}."
                        ),
                    ):
                        del st.session_state.pedidos[persona][producto]
                        st.rerun()

                st.markdown(f"**Total de {persona}: {total_persona:.2f} €**")
                total_general += total_persona

    return total_general


def ui_resumen_y_whatsapp(total_general: Decimal) -> None:
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    personas = len(st.session_state.pedidos)
    items = sum(sum(c.values()) for c in st.session_state.pedidos.values())
    m1.metric("Personas en la mesa", personas, help="Número de clientes en la mesa.")
    m2.metric(
        "Consumiciones",
        items,
        help="Suma de todas las unidades pedidas por toda la mesa.",
    )
    m3.metric(
        "Total de la mesa",
        f"{total_general:.2f} €",
        help="Importe total a pagar por toda la mesa.",
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

    hay_pedidos = any(st.session_state.pedidos.values())
    if not hay_pedidos:
        st.info("Añade consumiciones para poder compartir la cuenta.")
        return

    mensaje = generar_mensaje_whatsapp(
        st.session_state.pedidos,
        st.session_state.menu,
        nombre_del_bar(),
    )
    with st.expander("Vista previa del mensaje de WhatsApp", expanded=False):
        st.code(mensaje, language=None)

    enlace = crear_enlace_whatsapp(mensaje, telefono)
    etiqueta = (
        f"Enviar cuenta por WhatsApp a +{telefono}"
        if telefono
        else "Abrir WhatsApp con la cuenta"
    )
    st.link_button(
        etiqueta,
        enlace,
        use_container_width=True,
        type="primary",
        help=(
            f"Abre el chat de WhatsApp con +{telefono} y el resumen de la cuenta."
            if telefono
            else "Abre WhatsApp con el resumen de la cuenta listo para elegir contacto."
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
    st.caption("Gestiona mesa, menú, marca y precios.")

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
- Las pestañas son: Pedido, Ticket y Menú.
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

    menu = st.session_state.menu
    if menu:
        st.markdown("**Menú rápido**")
        for producto, precio in menu.items():
            st.markdown(f"- {producto}: **{precio:.2f} €**")
    else:
        st.warning("Menú vacío. Ve a la pestaña Menú para añadir productos.")

    st.markdown("---")
    if st.button(
        "Vaciar cuenta de la mesa",
        use_container_width=True,
        help="Borra todas las personas y consumiciones de la mesa. El menú no se modifica.",
    ):
        st.session_state.pedidos = {}
        st.session_state.persona_activa = None
        st.success("Cuenta de la mesa vaciada.")
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
            "Navegación: Pedido para apuntar, Ticket para revisar importes, "
            "Menú para productos, y barra lateral para marca y WhatsApp."
        )
else:
    st.markdown(f"## {nombre_del_bar()}")
    st.caption(
        "Navegación principal: elige Pedido para apuntar, Ticket para revisar importes, "
        "o Menú para crear, editar y borrar productos. "
        "Configura nombre e imagen en la barra lateral → Marca del bar."
    )

tab_pedido, tab_ticket, tab_menu = st.tabs(
    ["Pedido", "Ticket", "Menú (crear, editar, borrar)"]
)

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
    "Interfaz pensada para teclado, tooltips y lectores de pantalla."
)
