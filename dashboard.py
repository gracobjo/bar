"""Panel de indicadores. Solo lo abre el administrador."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from kpis import ZONAS, ZONA_ETIQUETA, calcular, fusionar_cuentas


PERIODOS = {"Hoy": 1, "7 días": 7, "30 días": 30, "Todo": None}


def _euros(valor) -> str:
    if valor is None:
        return "—"
    return f"{valor:.2f} €"


def _pct(valor) -> str:
    if valor is None:
        return "—"
    return f"{valor:.1f} %"


def _minutos(valor) -> str:
    if valor is None:
        return "—"
    return f"{valor} min"


def ui_dashboard() -> None:
    import sys

    bar = sys.modules.get("bar") or sys.modules["__main__"]

    st.subheader("Panel de decisiones")
    st.caption(
        "Cifras de las cuentas con ticket y de las mesas que siguen abiertas. "
        "Una mesa abierta cuenta con lo consumido hasta ahora."
    )
    periodo = st.segmented_control(
        "Periodo",
        options=list(PERIODOS),
        default="Hoy",
        key="kpi_periodo",
    )
    dias = PERIODOS.get(periodo or "Hoy", 1)

    cuentas = calcular(
        fusionar_cuentas(bar.cargar_ventas(), bar.cuentas_abiertas()),
        costes_hora=bar.st.session_state.config.get("coste_hora") or {},
        personal=bar.cargar_personal(),
        incidencias=bar.cargar_incidencias(),
        dias=dias,
        plantilla_actual=len(bar.lista_barmans()),
        mesas_ahora=bar.resumen_mesas_ahora(),
    )

    st.markdown("### Financieros y rentabilidad")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Ticket medio", _euros(cuentas["ticket_medio"]), help="Gasto medio por comensal.")
    f2.metric(
        "Coste de producto",
        _pct(cuentas["coste_producto_pct"]),
        help="Coste de lo vendido partido por su precio. Referencia habitual: 25 % a 30 %.",
    )
    f3.metric(
        "RevPASH",
        _euros(cuentas["revpash"]),
        help="Ingresos por asiento y hora. Usa los asientos de cada mesa y el tiempo abierta.",
    )
    f4.metric("Cuentas del periodo", str(cuentas["cuentas"]))
    if not cuentas["hay_costes"]:
        st.caption("El coste de producto aparece cuando indicas el coste de cada producto en Menú. 0 € se toma como coste desconocido.")
    elif cuentas["coste_producto_pct"] is not None:
        st.caption("Referencia de coste de producto en hostelería: entre el 25 % y el 30 %.")

    z1, z2, z3 = st.columns(3)
    for columna, zona in zip((z1, z2, z3), ZONAS):
        columna.metric(
            f"Ticket medio · {ZONA_ETIQUETA[zona]}",
            _euros(cuentas["ticket_medio_zona"][zona]),
        )
    r1, r2, r3 = st.columns(3)
    for columna, zona in zip((r1, r2, r3), ZONAS):
        columna.metric(
            f"RevPASH · {ZONA_ETIQUETA[zona]}",
            _euros(cuentas["revpash_zona"][zona]),
        )

    st.markdown("**Margen de contribución por producto**")
    if cuentas["margen"]:
        tabla = pd.DataFrame(
            {
                "Producto": [nombre for nombre, _ in cuentas["margen"][:12]],
                "Margen €": [float(importe) for _, importe in cuentas["margen"][:12]],
            }
        )
        st.bar_chart(tabla, x="Producto", y="Margen €", horizontal=True)
        st.caption("Precio de venta menos coste, en el periodo. Solo entran productos con coste informado.")
    else:
        st.info("Todavía no hay margen que mostrar. Hace falta venta y el coste en la ficha del producto.")
    if cuentas["sin_coste"]:
        st.caption("Sin coste, fuera del margen: " + ", ".join(cuentas["sin_coste"][:12]))

    st.markdown("### Operaciones y rotación")
    o1, o2, o3 = st.columns(3)
    o1.metric(
        "Rotación de mesa",
        _minutos(cuentas["rotacion_minutos"]),
        help="Minutos desde que se abre la mesa hasta el ticket, o hasta ahora si sigue abierta.",
    )
    o2.metric(
        "Ocupación de la terraza",
        _pct(cuentas["ocupacion_terraza"]),
        help="Mesas de terraza con comensales, ahora mismo, sobre las mesas de terraza creadas.",
    )
    o3.metric(
        "Tiempo de la cuenta",
        _minutos(cuentas["espera_minutos"]),
        help="Minutos desde la primera consumición hasta el ticket. No mide la cocina por separado.",
    )
    st.caption(
        f"Terraza ahora: {cuentas['terraza_ocupadas']} de {cuentas['terraza_total']} mesas con gente. "
        "El clima no se registra."
    )
    horas = pd.DataFrame(
        {
            "Hora": [f"{hora:02d}h" for hora in range(24)],
            "Cuentas en terraza": [cuentas["terraza_por_hora"][hora] for hora in range(24)],
        }
    )
    st.markdown("**Cuentas de terraza por hora**")
    st.bar_chart(horas, x="Hora", y="Cuentas en terraza")

    st.markdown("### Personal")
    p1, p2, p3 = st.columns(3)
    p1.metric(
        "Coste de personal",
        _pct(cuentas["coste_personal_pct"]),
        help="Coste por hora por las horas de cada cuenta, partido por las ventas. Referencia: 30 % a 35 %.",
    )
    p2.metric("Euros de personal", _euros(cuentas["coste_personal"]))
    p3.metric(
        "Rotación de personal",
        _pct(cuentas["rotacion_personal_pct"]),
        help="Bajas del periodo partidas por la plantilla media. Solo cuenta altas y bajas hechas en la app.",
    )
    if cuentas["sin_tarifa"]:
        st.caption(
            "Sin coste por hora, fuera del porcentaje de personal: "
            + ", ".join(cuentas["sin_tarifa"])
        )
    else:
        st.caption("Referencia de coste de personal: entre el 30 % y el 35 % de las ventas.")
    if cuentas["ventas_hora"]:
        productividad = pd.DataFrame(
            {
                "Barman": list(cuentas["ventas_hora"]),
                "€ por hora": [float(v) for v in cuentas["ventas_hora"].values()],
            }
        )
        st.markdown("**Ventas por empleado y hora**")
        st.bar_chart(productividad, x="Barman", y="€ por hora", horizontal=True)
        st.caption("La venta de la cuenta se asigna a quien la cerró. La hora es el tiempo que la mesa estuvo abierta.")
    else:
        st.info("Aún no hay ventas atribuidas a un barman en este periodo.")

    with st.form("form_coste_hora"):
        st.markdown("**Coste por hora de cada barman**")
        tarifas = dict(bar.st.session_state.config.get("coste_hora") or {})
        nuevos = {}
        for nombre in bar.lista_barmans():
            actual = tarifas.get(nombre)
            valor = float(actual) if actual not in (None, "") else 0.0
            nuevos[nombre] = st.number_input(
                f"€/hora de {nombre}",
                min_value=0.0,
                value=valor,
                step=0.5,
                format="%.2f",
                help="0 € significa que todavía no has indicado el coste. No entra en el porcentaje.",
                key=f"coste_hora_{nombre}",
            )
        if st.form_submit_button("Guardar costes por hora", type="primary"):
            bar.set_config(
                {
                    "coste_hora": {
                        nombre: f"{importe:.2f}" if importe > 0 else ""
                        for nombre, importe in nuevos.items()
                    }
                }
            )
            st.success("Costes por hora guardados.")
            st.rerun()

    st.markdown("### Satisfacción")
    s1, s2, s3 = st.columns(3)
    s1.metric(
        "Clientes que repiten",
        _pct(cuentas["retencion_pct"]),
        help="Nombres de comensal que aparecen en más de una cuenta, sobre los nombres distintos.",
    )
    s2.metric(
        "Quejas o errores",
        _pct(cuentas["incidencias_pct"]),
        help="Incidencias registradas partidas por el número de cuentas del periodo.",
    )
    s3.metric("Incidencias", str(cuentas["incidencias"]))
    st.caption(
        f"{cuentas['clientes_repetidos']} nombres repetidos de {cuentas['clientes_distintos']}. "
        "No hay ficha de cliente: se compara el nombre escrito en la mesa. "
        "Las reseñas de Google o TripAdvisor no se leen solas; anótalas aquí."
    )
    cfg = bar.st.session_state.config
    with st.form("form_resenas"):
        c_g, c_t = st.columns(2)
        nota_google = c_g.number_input(
            "Nota en Google",
            min_value=0.0,
            max_value=5.0,
            value=float(cfg.get("nota_google") or 0.0),
            step=0.1,
            format="%.1f",
            help="0 significa que aún no has anotado la nota.",
        )
        nota_trip = c_t.number_input(
            "Nota en TripAdvisor",
            min_value=0.0,
            max_value=5.0,
            value=float(cfg.get("nota_tripadvisor") or 0.0),
            step=0.1,
            format="%.1f",
            help="0 significa que aún no has anotado la nota.",
        )
        if st.form_submit_button("Guardar notas", type="primary"):
            bar.set_config(
                {
                    "nota_google": nota_google if nota_google > 0 else None,
                    "nota_tripadvisor": nota_trip if nota_trip > 0 else None,
                }
            )
            st.success("Notas guardadas.")
            st.rerun()
    g = cfg.get("nota_google")
    t = cfg.get("nota_tripadvisor")
    st.caption(
        "Google: "
        + (f"{float(g):.1f} / 5" if g else "sin anotar")
        + " · TripAdvisor: "
        + (f"{float(t):.1f} / 5" if t else "sin anotar")
    )

    st.markdown("### Acceso de administrador")
    with st.form("form_cambiar_pin"):
        st.caption(f"Usuario: **{cfg.get('administrador_nombre') or 'administrador'}**")
        actual = st.text_input("PIN actual", type="password")
        nuevo = st.text_input("PIN nuevo", type="password", help="Al menos 4 caracteres.")
        if st.form_submit_button("Cambiar PIN"):
            if actual != str(cfg.get("administrador_pin") or ""):
                st.error("El PIN actual no coincide.")
            elif len((nuevo or "").strip()) < 4:
                st.error("El PIN nuevo necesita al menos 4 caracteres.")
            else:
                bar.set_config({"administrador_pin": nuevo.strip()})
                st.success("PIN actualizado.")
                st.rerun()
