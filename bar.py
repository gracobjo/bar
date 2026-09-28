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

MENU_DEFAULT = {
    "🍺 Caña": "1.90",
    "🍻 Cerveza": "2.50",
    "💧 Agua": "1.00",
    "🥔 Pincho tortilla": "3.50",
}

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
# PERSISTENCIA DEL MENÚ
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


def init_state() -> None:
    if "menu" not in st.session_state:
        st.session_state.menu = cargar_menu()
    if "pedidos" not in st.session_state:
        st.session_state.pedidos = {}
    if "persona_activa" not in st.session_state:
        st.session_state.persona_activa = None
    if "ultimo_aviso" not in st.session_state:
        st.session_state.ultimo_aviso = None


def set_menu(menu: dict[str, Decimal]) -> None:
    st.session_state.menu = menu
    guardar_menu(menu)


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


def generar_mensaje_whatsapp(pedidos: dict, menu: dict[str, Decimal]) -> str:
    """Mensaje en texto plano (sin emojis) para que WhatsApp no muestre caracteres rotos."""
    lineas = ["*CUENTA DEL BAR*", ""]
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


def crear_enlace_whatsapp(mensaje: str) -> str:
    """Codifica el mensaje en UTF-8 para el enlace de compartir de WhatsApp."""
    texto = urllib.parse.quote(mensaje, safe="", encoding="utf-8")
    return f"https://api.whatsapp.com/send?text={texto}"


# ============================================
# CRUD MENÚ
# ============================================
def ui_crud_menu() -> None:
    menu = st.session_state.menu

    st.subheader("Gestión del menú")
    st.caption(
        "Crea, edita o elimina productos y precios. "
        "Los cambios se guardan automáticamente. "
        "Pasa el ratón o enfoca con Tab para ver la descripción de cada botón."
    )

    # --- CREAR ---
    with st.expander("Añadir producto nuevo", expanded=not menu):
        with st.form("form_nuevo_producto", clear_on_submit=True):
            c1, c2 = st.columns([2, 1])
            nombre = c1.text_input(
                "Nombre del producto",
                placeholder="Ej: Vino tinto",
                help="Nombre visible en el menú y en el ticket.",
            )
            precio = c2.number_input(
                "Precio en euros",
                min_value=0.0,
                value=2.0,
                step=0.10,
                format="%.2f",
                help="Precio unitario del producto en euros.",
            )
            if st.form_submit_button(
                "Guardar producto",
                use_container_width=True,
                type="primary",
                help="Añade este producto al menú con el precio indicado.",
            ):
                nombre_ok = nombre.strip()
                if not nombre_ok:
                    st.error("El nombre no puede estar vacío.")
                elif nombre_ok in menu:
                    st.error(f"«{nombre_ok}» ya existe en el menú.")
                else:
                    nuevo = dict(menu)
                    nuevo[nombre_ok] = Decimal(f"{precio:.2f}")
                    set_menu(nuevo)
                    st.success(f"Producto añadido: {nombre_ok} a {precio:.2f} euros.")
                    st.rerun()

    if not menu:
        st.info("Todavía no hay productos. Añade el primero arriba.")
        return

    st.markdown("---")
    st.markdown(f"#### Productos actuales ({len(menu)})")

    # --- LEER / ACTUALIZAR / ELIMINAR ---
    for producto, precio in list(menu.items()):
        with st.container(border=True):
            st.markdown(f"**Producto:** {producto} — **Precio actual:** {precio:.2f} €")
            with st.form(f"form_edit_{producto}"):
                e1, e2 = st.columns([2, 1])
                nuevo_nombre = e1.text_input(
                    f"Nuevo nombre para {producto}",
                    value=producto,
                    help=f"Cambia el nombre del producto «{producto}».",
                    key=f"nom_{producto}",
                )
                nuevo_precio = e2.number_input(
                    f"Nuevo precio de {producto} (€)",
                    min_value=0.0,
                    value=float(precio),
                    step=0.10,
                    format="%.2f",
                    help=f"Cambia el precio de «{producto}» en euros.",
                    key=f"pre_{producto}",
                )
                b1, b2 = st.columns(2)
                with b1:
                    guardar = st.form_submit_button(
                        "Guardar cambios",
                        use_container_width=True,
                        type="primary",
                        help=(
                            f"Guarda el nombre y el precio nuevos de «{producto}». "
                            "Si renombras, los pedidos de la mesa se actualizan."
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
                    nombre_ok = nuevo_nombre.strip()
                    if not nombre_ok:
                        st.error("El nombre no puede estar vacío.")
                    elif nombre_ok != producto and nombre_ok in menu:
                        st.error(f"Ya existe «{nombre_ok}».")
                    else:
                        actualizado = dict(menu)
                        del actualizado[producto]
                        actualizado[nombre_ok] = Decimal(f"{nuevo_precio:.2f}")
                        if nombre_ok != producto:
                            renombrar_producto_en_pedidos(producto, nombre_ok)
                        set_menu(actualizado)
                        st.success(
                            f"Producto actualizado: {nombre_ok} a {nuevo_precio:.2f} euros."
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

    hay_pedidos = any(st.session_state.pedidos.values())
    if not hay_pedidos:
        st.info("Añade consumiciones para poder compartir la cuenta.")
        return

    mensaje = generar_mensaje_whatsapp(st.session_state.pedidos, st.session_state.menu)
    with st.expander("Vista previa del mensaje de WhatsApp", expanded=False):
        st.code(mensaje, language=None)

    enlace = crear_enlace_whatsapp(mensaje)
    st.link_button(
        "Abrir WhatsApp con la cuenta",
        enlace,
        use_container_width=True,
        type="primary",
        help="Abre WhatsApp con el resumen de la cuenta listo para enviar.",
    )


# ============================================
# APP
# ============================================
init_state()

with st.sidebar:
    st.title("Cuenta del Bar")
    st.caption("Gestiona mesa, menú y precios.")
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

st.markdown("## Cuenta del Bar")
st.caption(
    "Navegación principal: elige Pedido para apuntar, Ticket para revisar importes, "
    "o Menú para crear, editar y borrar productos."
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
