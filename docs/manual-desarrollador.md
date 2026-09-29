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
bar.py              Interfaz, mesas, pedidos, WhatsApp, emisión del número
ticket_fiscal.py    IVA, huella, texto del QR, PDF
requirements.txt
docs/               Esta documentación
config_bar.json     Configuración (no se versiona)
mesas_bar.json      Mesas abiertas (no se versiona)
menu_bar.json       Carta (no se versiona)
assets/marca_bar.*  Logo (no se versiona)
```

`bar.py` no define clases de dominio. Los datos son diccionarios y los precios son `Decimal`. `ticket_fiscal.py` no importa Streamlit: se puede llamar desde un script.

Cada rerun de Streamlit vuelve a leer configuración y mesas del disco (`init_state`). Así, dos móviles que apuntan al mismo proceso ven los cambios del otro en la siguiente interacción. El barman activo no se comparte: es de la sesión del navegador.

## 3. Configuración

`CONFIG_DEFAULT` en `bar.py` es el contrato de `config_bar.json`. `normalizar_config` rellena claves que falten y descarta valores ilegales. Cualquier campo nuevo tiene que entrar en `CONFIG_DEFAULT` o se perderá al guardar.

Normalizaciones:

- Teléfono: solo dígitos. Se quita un `00` inicial.
- NIF: alfanumérico en mayúsculas.
- Serie: alfanumérico en mayúsculas, máximo 10, por defecto `A`.
- Próximo número: entero mayor o igual que 1.
- IVA: solo `0`, `4`, `10` o `21`. Si no vale, queda `10`.
- Barmans: lista única, ordenada sin distinguir mayúsculas.

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
  "ticket_fiscal": {
    "huella": "<sha256>",
    "datos": {}
  }
}
```

`ticket_fiscal` solo existe después de emitir. `vaciar_mesa` lo borra. `normalizar_estructura_mesa` lo conserva si tiene `huella` y `datos.ticket`.

La clave del producto en `comensales` incluye el icono (`🍺 Caña`). En el ticket y en WhatsApp se usa `nombre_limpio`, que quita ese icono.

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

## 9. Interfaz

Pestañas, en este orden: Mesas, Pedido, Ticket, Menú. La barra lateral no es una pestaña: identidad, marca, accesibilidad, WhatsApp, datos fiscales y acciones rápidas de mesas.

`exigir_barman` devuelve falso y muestra un aviso si no hay barman. Lo usan las consumiciones y la emisión del ticket.

Al añadir un control, ponle etiqueta visible y `help`. El foco de teclado ya tiene un borde en el CSS de cabecera.

## 10. Qué no hay que hacer

- No guardes precios como `float`.
- No incrementes `proximo_numero_ticket` al generar el PDF. Solo al emitir una huella nueva.
- No vuelvas a meter JSON con `ñ` u `ó` en el QR si el lector del bar las muestra mal.
- No des por hecho un usuario y una contraseña. Identificarse es elegir un nombre de la lista.
- No hay verificación del QR en un servidor. El código solo lleva el texto del ticket.

## 11. Pruebas

No hay suite automática. Para un cambio de ticket:

1. Arranca Streamlit y entra con un barman.
2. Abre una mesa con consumiciones.
3. Emite el térmico y el A4 y comprueba que el número coincide.
4. Descarga otra vez y comprueba que `proximo_numero_ticket` no ha subido.
5. Cambia una cantidad, emite y comprueba que el número sí sube.
6. Escanea el QR del PDF nuevo, en el móvil y, si puedes, en un papel de 80 mm.

`ticket_fiscal.py` se puede ejercitar sin Streamlit importando `desglose_iva`, `texto_qr` y `generar_pdf_ticket`.
