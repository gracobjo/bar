# Manual de usuario

Cuenta del Bar sirve para apuntar pedidos de varias mesas a la vez, saber quién los registró y sacar la cuenta por WhatsApp o en un ticket PDF.

Varios móviles pueden usar la misma aplicación. Las mesas y el menú se comparten. Cada teléfono elige su barman.

## 1. Arrancar la aplicación

En la carpeta del proyecto, con el entorno virtual ya creado:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run bar.py
```

Se abre en el navegador, normalmente en `http://localhost:8501`. En otros móviles de la misma red hay que usar la dirección del ordenador donde corre Streamlit.

## 2. Configuración inicial

Se hace una vez, en la barra lateral. Después solo se cambia si cambian los datos del bar.

### 2.1 Quién soy

1. En **Alta de barmans**, escribe el nombre y pulsa **Añadir barman**.
2. En **Barman en este teléfono**, elige tu nombre.
3. La pantalla muestra «Activo» con la fecha y la hora.
4. **Cerrar sesión de barman** quita la identificación de ese teléfono. No borra al barman de la lista.
5. **Eliminar** quita un barman de la lista. No borra el historial ya guardado.

Sin barman identificado no se pueden apuntar consumiciones ni emitir el ticket fiscal.

### 2.2 Marca del bar

- **Nombre del bar**: el nombre que se ve en la cabecera, en WhatsApp y, si no hay razón social, en el ticket.
- **Imagen**: PNG, JPG, WEBP o GIF. Sale en la barra lateral y en el encabezado del PDF.
- **Quitar imagen** borra el logo.

### 2.3 WhatsApp del bar

Teléfono con prefijo de país, sin el signo `+`. Ejemplo para España: `34612345678`.

La aplicación quita espacios, guiones y el `+`. Si el número empieza por `00`, también lo quita.

Si hay número, el botón de WhatsApp abre el chat con ese teléfono. Si no hay número, WhatsApp pide a quién enviar el mensaje.

### 2.4 Datos fiscales

Hacen falta para el ticket PDF.

| Campo | Qué poner |
| --- | --- |
| Razón social | Nombre fiscal del bar |
| NIF/CIF | Letras y números, sin espacios. Se guarda en mayúsculas |
| Dirección fiscal | Calle, código postal y localidad |
| Tipo de IVA | 0 %, 4 %, 10 % o 21 %. El valor inicial es 10 % |
| Serie del ticket | Letras o números, hasta 10 caracteres. El valor inicial es `A` |
| Próximo número de ticket | El siguiente correlativo. El valor inicial es 1, que se imprime como `A-00001` |

Pulsa **Guardar datos fiscales**.

Los precios del menú ya llevan el IVA incluido. Con IVA 0 % el ticket imprime «IVA incluido en los precios» y no desglosa cuota.

### 2.5 Menú

Pestaña **Menú (crear, editar, borrar)**.

- Alta: icono, nombre y precio en euros. **Guardar producto**.
- Cambio: edita la ficha del producto y pulsa **Guardar cambios**.
- Baja: **Eliminar producto**. También desaparece de las mesas abiertas.
- **Restaurar menú por defecto** vuelve a caña, cerveza, agua y pincho de tortilla.

## 3. Uso diario

Orden habitual: identificarse, mesas, pedido, ticket.

### 3.1 Mesas

Pestaña **Mesas**.

- **Crear mesa**: por ejemplo `Mesa 1`, `Terraza A` o `Barra`.
- **Seleccionar**: esa pasa a ser la mesa activa.
- **Renombrar**: cambia el nombre y conserva comensales e historial.
- **Vaciar mesa**: quita comensales y consumiciones. La mesa sigue abierta. Si había un ticket fiscal de esa cuenta, se olvida para poder emitir otro cuando haya un pedido nuevo.
- **Cerrar mesa**: elimina la mesa por completo.

En la barra lateral también están **Vaciar mesa activa** y **Cerrar todas las mesas**.

### 3.2 Pedido

Pestaña **Pedido**.

1. Escribe el nombre del comensal, elige la mesa y pulsa **Asignar a mesa**.
2. Una persona solo puede estar en una mesa. Si ya estaba en otra, se mueve y se lleva lo que hubiera consumido.
3. Elige la mesa y pulsa el nombre del comensal.
4. Pulsa un producto para sumar una unidad. El botón indica cuántas lleva ya.
5. En el resumen, **+** suma, **−** resta y **Quitar** borra la línea.

Cada pulsación guarda fecha, hora, barman, comensal, producto, lo que cambió y la cantidad que queda.

### 3.3 Ticket de la mesa

Pestaña **Ticket**.

- Un bloque por comensal, con producto, cantidad, subtotal y botones para corregir.
- Total de cada comensal y total de la mesa.
- Aviso de cuadre si los importes coinciden.
- **Trazabilidad**: los últimos 50 movimientos de esa mesa. Sirve para una reclamación.
- Métricas: mesa, número de comensales, consumiciones y total.

### 3.4 WhatsApp

En la misma pestaña, abre la vista previa y pulsa **Abrir WhatsApp**.

El mensaje incluye el nombre del bar, la mesa, la hora, el barman, el desglose por comensal, el total y los últimos 12 movimientos. No usa emoticonos, para que WhatsApp no los muestre mal.

## 4. Ticket fiscal PDF

En **Ticket**, debajo de WhatsApp.

1. Completa razón social y NIF. Si faltan, la pantalla avisa, pero puedes emitir igual: el nombre del bar se usa como razón social si el campo está vacío.
2. Tiene que haber consumiciones con importe.
3. Identifícate como barman.
4. La primera vez, pulsa **Ticket térmico (80 mm)** o **Factura A4**. Eso reserva el número (`A-00001`, `A-00002`, …).
5. Después aparecen los botones de descarga. Vuelve a pulsar el formato que quieras. Los dos formatos comparten el mismo número.
6. Abre el PDF e imprime con Ctrl+P. Para la térmica, elige la impresora de 80 mm. Para el otro, una impresora normal en A4.

Si descargas otra vez la misma cuenta, no se gasta otro número. Si cambias productos, cantidades, total o datos fiscales de esa mesa, la siguiente emisión pide un número nuevo.

**Vaciar** la mesa borra también el ticket asociado. **Cerrar** la mesa borra la mesa y su ticket.

### Qué lleva el PDF

- Logo, si existe.
- Razón social, nombre comercial si es distinto, NIF y dirección.
- Número, fecha, mesa y barman.
- Productos agrupados, sin separar por comensal: cantidad, precio y subtotal.
- Base, cuota de IVA y total. Los precios van con IVA incluido.
- Código QR.
- El texto «Gracias por su visita».

El papel térmico mide 80 mm de ancho y al menos 200 mm de alto. Crece si hay muchas líneas. El A4 es una hoja normal, con márgenes de 15 mm.

### Cómo se lee el QR

El QR no abre una web. Al escanearlo se ve el texto del ticket: número, bar, NIF, dirección, fecha, mesa, barman, líneas, IVA y total.

La ñ y las tildes se escriben sin acento (`Rincon`, `Cana`). Muchos lectores convierten esas letras en caracteres de otro idioma. En el PDF impreso, el nombre y los productos sí salen con sus tildes.

En la térmica el QR ocupa casi todo el ancho del papel (68 mm) para que se pueda enfocar. Hay que imprimir el archivo nuevo, no uno descargado antes.

## 5. Copias de seguridad

Copia de vez en cuando estos archivos, que están en la carpeta del proyecto y no van al repositorio:

- `config_bar.json`: bar, barmans, WhatsApp, datos fiscales y el próximo número de ticket.
- `mesas_bar.json`: mesas abiertas, pedidos, historial y tickets ya emitidos.
- `menu_bar.json`: productos y precios.
- `assets/`: el logo.

Si se pierde `config_bar.json`, el próximo ticket puede repetir un número ya usado.

## 6. Atajos de uso

- Tab y Mayús+Tab mueven el foco. El control enfocado se marca con un borde.
- Los botones tienen texto, no solo un icono.
- Los avisos de éxito o error salen escritos en la página.
