# Manual de desarrollador

La aplicación es un proceso Streamlit. No hay base de datos ni API. El estado compartido vive en JSON junto a `bar.py`. El estado de cada navegador (barman elegido, mesa y comensal activos) vive en `st.session_state`.

## 1. Entorno

Python 3. El entorno del proyecto es `.venv` (está en `.gitignore`).

```powershell
.\.venv\Scripts\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run bar.py
```

Dependencias de `requirements.txt`:

| Paquete | Uso |
| --- | --- |
| `streamlit` | Interfaz |
| `fpdf2` | PDF térmico y A4 |
| `segno` | Código QR |
| `pillow` | Logo a PNG para incrustarlo en el PDF |

En Windows el PDF usa Arial (`%WINDIR%\Fonts\arial.ttf` y `arialbd.ttf`) para tildes y el símbolo del euro. Si esas fuentes no están, se usa Helvetica y el euro se escribe `EUR`.

## 2. Mapa del código

```text
bar.py              Interfaz, mesas, pedidos, WhatsApp, emisión del número, archivo de cuentas
dashboard.py        Pestaña Panel. No importa bar.py: lo toma del proceso ya cargado
kpis.py             Cálculo de indicadores, sin Streamlit
ticket_fiscal.py    IVA, huella, texto del QR, PDF
requirements.txt
docs/               Esta documentación
config_bar.json     Configuración, PIN y tarifas (no se versiona)
mesas_bar.json      Mesas abiertas (no se versiona)
menu_bar.json       Carta (no se versiona)
costes_bar.json     Coste por producto (no se versiona)
ventas_bar.json     Cuentas archivadas (no se versiona)
personal_bar.json   Altas y bajas (no se versiona)
incidencias_bar.json Quejas (no se versiona)
assets/marca_bar.*  Logo (no se versiona)
```

`bar.py` no define clases de dominio. Los datos son diccionarios y los precios son `Decimal`. `ticket_fiscal.py` y `kpis.py` no importan Streamlit. `dashboard.py` no debe hacer `import bar`: `streamlit run bar.py` carga el archivo como `__main__`, y un import volvería a ejecutar la app. Busca el módulo con `sys.modules.get("bar") or sys.modules["__main__"]`.

`pandas` llega con Streamlit y solo lo usa el panel para los gráficos. No está en `requirements.txt` por separado.

Cada rerun de Streamlit vuelve a leer configuración, costes y mesas del disco (`init_state`). Así, dos móviles que apuntan al mismo proceso ven los cambios del otro en la siguiente interacción. El barman activo y la sesión de administrador no se comparten: son de la sesión del navegador.

## 3. Configuración

`CONFIG_DEFAULT` en `bar.py` es el contrato de `config_bar.json`. `normalizar_config` rellena claves que falten y descarta valores ilegales. Cualquier campo nuevo tiene que entrar en `CONFIG_DEFAULT` o se perderá al guardar.

Normalizaciones:

- Teléfono: solo dígitos. Se quita un `00` inicial.
- NIF: alfanumérico en mayúsculas.
- Serie: alfanumérico en mayúsculas, máximo 10, por defecto `A`.
- Próximo número: entero mayor o igual que 1.
- IVA: solo `0`, `4`, `10` o `21`. Si no vale, queda `10`.
- Barmans: lista única, ordenada sin distinguir mayúsculas.
- Administrador: nombre (por defecto `administrador`) y PIN en texto. El PIN vacío significa que aún no se ha creado. No se versiona el fichero.
- `coste_hora`: mapa barman → importe. Cadena vacía o ausencia significa tarifa desconocida.
- `nota_google` y `nota_tripadvisor`: número o `null`. Cero o vacío se guardan como no anotadas al pulsar **Guardar notas**.

`set_config` fusiona, normaliza y escribe el archivo. También cierra la sesión si el barman activo ya no está en la lista.

## 4. Mesas

Cada mesa en `mesas_bar.json`:

```json
{
  "abierta_en": "2026-09-29 09:29:43",
  "comensales": {
    "pepe": { "🍺 Caña": 1 }
  },
  "historial": [],
  "zona": "barra",
  "asientos": 4,
  "incidencias": 0,
  "ticket_fiscal": {
    "huella": "<sha256>",
    "datos": {}
  }
}
```

`ticket_fiscal` solo existe después de emitir. `vaciar_mesa` lo borra, pone `incidencias` a 0 y renueva `abierta_en`, para que la siguiente sentada sea otro periodo. `normalizar_estructura_mesa` conserva el ticket si tiene `huella` y `datos.ticket`.

`zona` es `barra`, `mesas` o `terraza`. Si falta, `inferir_zona` mira el nombre: «barra», si no «terraza», si no `mesas`. `asientos` mínimo 1; si falta, 4.

La clave del producto en `comensales` incluye el icono (`🍺 Caña`). En el ticket y en WhatsApp se usa `nombre_limpio`, que quita ese icono. El coste de esa unidad no vive en la mesa: está en `costes_bar.json` y solo se guarda si es mayor que 0.

Un comensal solo está en una mesa. `asignar_comensal_a_mesa` lo mueve si ya existía y conserva sus cantidades.

### Historial

`registrar_evento` añade un objeto y, por defecto, guarda el JSON. Acciones usadas:

| Acción | Cuándo |
| --- | --- |
| `abrir` | Se crea la mesa |
| `renombrar` | Cambia el nombre |
| `asignar` | Entra un comensal nuevo |
| `mover` | Un comensal cambia de mesa |
| `quitar_comensal` | Se saca a una persona |
| `añadir` | Sube la cantidad |
| `quitar` | Baja la cantidad y aún queda alguna |
| `eliminar` | La línea desaparece |
| `vaciar` | Se vacía la mesa |
| `ticket_fiscal` | Se asigna un número de ticket |

Campos: `ts` (`YYYY-MM-DD HH:MM:SS`), `barman`, `comensal`, `accion`, `producto`, `cantidad_delta`, `cantidad_resultante`, `detalle`.

La pestaña Ticket muestra los últimos 50. WhatsApp incluye los últimos 12.

## 5. Dinero

Todos los importes de negocio son `Decimal` cuantizados a céntimos. No uses `float` para precios.

Los precios del menú son IVA incluido. `desglose_iva` saca la base como `total / (1 + tipo)` y la cuota como `total - base`, ambas a dos decimales. Con tipo 0 la cuota es `0.00` y el PDF no imprime el desglose.

`lineas_agrupadas` suma el mismo producto de todos los comensales. El orden sigue el del menú y, al final, los productos que ya no están en la carta pero siguen en la mesa.

## 6. Número de ticket

`huella_cuenta` hace SHA-256 de un JSON ordenado con mesa, líneas, total, NIF, IVA, serie, razón social y dirección. No entran el barman ni el historial: si no, cada emisión o cada móvil cambiaría la huella y gastaría otro número.

`emitir_ticket_fiscal`:

1. Calcula la huella.
2. Si la mesa ya tiene un `ticket_fiscal` con esa huella, lo reutiliza.
3. Si no, `siguiente_numero_ticket` lee `proximo_numero_ticket`, guarda el siguiente y forma `SERIE-00001`.
4. Guarda `datos` en la mesa y registra el evento `ticket_fiscal`.

La primera pulsación de **Ticket térmico** o **Factura A4** emite y hace `st.rerun()`. En la siguiente ejecución ya existen los bytes del PDF y Streamlit puede pintar `download_button`. Los dos formatos se generan a partir de los mismos `datos`.

Cambiar la cuenta o los datos fiscales que entran en la huella invalida el ticket guardado. La siguiente emisión consume otro número. Vaciar la mesa también invalida el ticket guardado.

El widget del próximo número usa la clave `input_proximo_ticket` y se sincroniza con `_fiscal_numero_sync`, para que un número ya emitido no vuelva a escribirse al pulsar **Guardar datos fiscales**.

## 7. PDF y QR

`generar_pdf_ticket(datos, formato, logo_png=None)`.

| | `termica` | `a4` |
| --- | --- | --- |
| Papel | 80 mm de ancho, alto mínimo 200 mm | 210 × 297 mm |
| Márgenes | 3 mm | 15 mm |
| QR impreso | 68 mm | 42 mm |

El alto térmico lo estima `_alto_termica` para que el QR quepa en la misma página. Justo antes de colocarlo se desactiva el salto de página.

`texto_qr` arma líneas de texto. `_ascii` pasa a NFD, quita marcas combinantes y descarta lo que no sea ASCII. Así `ñ` queda en `n` y `ó` en `o`. El motivo: varios lectores interpretan los bytes altos del QR como chino o japonés, y la marca ECI de UTF-8 no basta en esos lectores. El PDF, con Arial, sí imprime las tildes.

`generar_qr_ticket` usa `segno` con corrección `m`, `scale=12` y `border=4` (zona muda de 4 módulos). No pongas un borde más estrecho en la térmica: la impresora recorta el borde y el móvil no enfoca.

El logo pasa por `png_logo_marca`: fondo blanco si hay transparencia, como máximo 480×240 px.

Impresora de 58 mm: hoy el ancho está fijado en `ANCHO_TERMICA_MM = 80` y el QR en 68 mm. Habría que bajar los dos; 68 mm no cabe en un rollo de 58 mm.

## 8. WhatsApp

`generar_mensaje_whatsapp` construye texto plano, sin emoticonos. `crear_enlace_whatsapp` usa `https://api.whatsapp.com/send`. Con teléfono, añade `phone`. El mensaje va en UTF-8 dentro de la query.

## 9. Cuentas archivadas e indicadores

`archivar_mesa` escribe en `ventas_bar.json` una foto de la mesa si tiene importe. La clave de esa sentada es mesa más `abierta_en`. Se archiva al emitir el ticket, al vaciar, al cerrar una mesa, al cerrar todas y al restaurar el menú. Mientras la mesa sigue abierta, `fusionar_cuentas` sustituye esa fila por la foto en vivo, para no dejar una copia vieja ni contar dos veces.

`cuenta_desde_mesa` devuelve `None` si no hay importe. El coste de línea es `None` cuando el producto no está en `costes_bar.json`. `minutos_mesa` va de `abierta_en` al `fecha` del ticket, o a ahora. `minutos_servicio` va del primer evento `añadir` a ese mismo fin.

`kpis.calcular` no inventa cifras:

| Indicador | Cálculo | Si falta el dato |
| --- | --- | --- |
| Ticket medio | Ventas / comensales, también por zona | `None` si no hay comensales |
| Coste de producto | Coste conocido / venta de esas líneas | Fuera las líneas con coste `None`. Referencia en pantalla: 25–30 % |
| RevPASH | Ventas / (asientos × horas). La hora es `max(minutos, 1) / 60` | La mesa sin asientos no entra |
| Margen | Subtotal − coste, por producto | Igual: sin coste no entra |
| Rotación | Media de `minutos_mesa` | — |
| Tiempo de la cuenta | Media de `minutos_servicio` | No es el tiempo de cocina |
| Ocupación terraza | Mesas de terraza con comensales / mesas de terraza, ahora | `None` si no hay mesas de terraza. No hay clima |
| Coste de personal | (€/hora × horas de la mesa) / ventas. La cuenta entera se atribuye al barman del ticket | Tarifa vacía no suma euros. Referencia: 30–35 % |
| Ventas por hora | Venta atribuida / horas de mesa abierta | — |
| Rotación de personal | Bajas del periodo / plantilla media | Las altas iniciales, si el fichero no existía, van fechadas el 2020-01-01 para no contar como contrataciones de hoy |
| Retención | Nombres en 2 o más cuentas / nombres distintos, sin distinguir mayúsculas | No hay id de cliente |
| Quejas | Incidencias del periodo / cuentas | Solo el botón de Ticket, no un `eliminar` |

El periodo **Hoy** es un `timedelta` de 1 día, no el día natural. **Todo** pasa `dias=None`.

`registrar_personal("alta"|"baja")` se llama al añadir o quitar un barman. `registrar_incidencia` suma el contador de la mesa y añade una fila en `incidencias_bar.json`. Exige barman.

La sesión de administrador es `st.session_state.admin_ok`. La pestaña Panel solo se añade si `es_admin()`. El PIN se compara en claro con `administrador_pin`; no hay hash.

## 10. Interfaz

Pestañas, en este orden: Mesas, Pedido, Ticket, Menú. **Panel** se añade al final solo con la sesión de administrador abierta. La barra lateral no es una pestaña: identidad, administrador, marca, accesibilidad, WhatsApp, datos fiscales y acciones rápidas de mesas.

`exigir_barman` devuelve falso y muestra un aviso si no hay barman. Lo usan las consumiciones, la emisión del ticket y el registro de quejas.

Al añadir un control, ponle etiqueta visible y `help`. En controles nuevos usa `width="stretch"`; `use_container_width` está en desuso. El foco de teclado ya tiene un borde en el CSS de cabecera.

## 11. Qué no hay que hacer

- No guardes precios como `float`.
- No incrementes `proximo_numero_ticket` al generar el PDF. Solo al emitir una huella nueva.
- No vuelvas a meter JSON con `ñ` u `ó` en el QR si el lector del bar las muestra mal.
- El barman sigue eligiéndose por nombre, sin PIN. El PIN solo abre el panel y no debe quedar escrito en el código ni en un commit.
- No hay verificación del QR en un servidor. El código solo lleva el texto del ticket.
- No rellenes un indicador con una cifra de ejemplo si falta el coste, la tarifa, la zona o la reseña.
- No hagas `import bar` desde `dashboard.py`.

## 12. Pruebas

No hay suite automática. Para un cambio de ticket:

1. Arranca Streamlit y entra con un barman.
2. Abre una mesa con consumiciones.
3. Emite el térmico y el A4 y comprueba que el número coincide.
4. Descarga otra vez y comprueba que `proximo_numero_ticket` no ha subido.
5. Cambia una cantidad, emite y comprueba que el número sí sube.
6. Escanea el QR del PDF nuevo, en el móvil y, si puedes, en un papel de 80 mm.

Para el panel: entra con el PIN, abre **Panel** y comprueba que ticket medio, RevPASH y rotación salen de la mesa abierta, y que coste de producto y reseñas quedan en blanco hasta que se informen.

`ticket_fiscal.py` se puede ejercitar sin Streamlit importando `desglose_iva`, `texto_qr` y `generar_pdf_ticket`. `kpis.calcular` también, pasándole listas de cuentas.
