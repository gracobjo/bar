# Manual de usuario

Cuenta del Bar sirve para apuntar pedidos de varias mesas a la vez, saber quién los registró, sacar la cuenta por WhatsApp o en un ticket PDF, y ver los indicadores del local si entras como administrador.

Varios móviles pueden usar la misma aplicación. Las mesas y el menú se comparten. Cada teléfono elige su barman. El panel de indicadores solo aparece en el teléfono donde se ha escrito el PIN.

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

### 2.5 Administrador

El administrador no es un barman. El PIN solo abre la pestaña **Panel** en ese teléfono. Pedidos, mesas y tickets siguen igual sin entrar.

Si todavía no hay PIN, el bloque **Administrador** de la barra lateral pide uno de al menos 4 caracteres. Pulsa **Crear administrador**. El usuario queda como `administrador`.

Si el PIN ya existe:

1. Abre **Administrador** en la barra lateral.
2. Comprueba el usuario que se muestra.
3. Escribe el PIN y pulsa **Entrar**.
4. Aparece la pestaña **Panel**.
5. **Salir del panel** cierra el panel en ese teléfono. No borra el PIN.

El PIN se cambia dentro del panel, en **Acceso de administrador**. No está en el código ni en el repositorio: solo en `config_bar.json` de ese ordenador. Quien abre la dirección de la app puede seguir trabajando como barman; no ve los indicadores hasta entrar.

### 2.6 Menú

Pestaña **Menú (crear, editar, borrar)**.

- Alta: icono, nombre, precio de venta y coste en euros. **Guardar producto**.
- El coste es lo que te cuesta producir esa unidad. **0 €** significa que aún no lo sabes: el panel no lo usa para el coste de producto ni para el margen.
- Cambio: edita la ficha del producto y pulsa **Guardar cambios**.
- Baja: **Eliminar producto**. También desaparece de las mesas abiertas.
- **Restaurar menú por defecto** vuelve a caña, cerveza, agua y pincho de tortilla.

## 3. Uso diario

Orden habitual: identificarse, mesas, pedido, ticket.

### 3.1 Mesas

Pestaña **Mesas**.

- **Crear mesa**: nombre, zona y asientos. La zona es **Barra**, **Mesas** o **Terraza**. Los asientos empiezan en 4. Sirven para el ticket medio por zona y para el RevPASH del panel.
- Si una mesa antigua no tiene zona, el nombre decide: si contiene «barra» es barra, si contiene «terraza» es terraza, y el resto queda en mesas.
- **Seleccionar**: esa pasa a ser la mesa activa.
- **Renombrar**: cambia el nombre y conserva comensales e historial. En el mismo formulario se guardan la zona y los asientos.
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
- **Registrar queja o error de comanda**: anota una incidencia de esa mesa. La nota es opcional. Hace falta estar identificado como barman. El panel cuenta esas incidencias; no las deduce de quitar una consumición.

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

## 5. Panel de indicadores

Solo se ve después de entrar como administrador. La pestaña se llama **Panel**.

Arriba se elige el periodo: **Hoy** (las últimas 24 horas), **7 días**, **30 días** o **Todo**. Las cuentas abiertas con importe entran con lo consumido hasta ahora. Si la mesa sigue abierta, esa foto sustituye a la copia ya guardada de la misma apertura, para no contar dos veces.

### 5.1 Financieros

- **Ticket medio**: venta del periodo partida por comensales. También por zona (barra, mesas y terraza).
- **Coste de producto**: coste de lo vendido partido por su precio, solo en productos con coste informado. La referencia que muestra la pantalla es del 25 % al 30 %. No es un tope: la app no bloquea nada si te sales.
- **RevPASH**: ingresos por asiento y hora. Usa los asientos de la mesa y el tiempo que lleva abierta. Sin asientos, esa mesa no entra.
- **Margen por producto**: precio de venta menos coste, en euros, de los productos con coste. El gráfico enseña los que más dejan.

### 5.2 Operaciones

- **Rotación de mesa**: minutos desde que se abre la mesa hasta el ticket, o hasta ahora si sigue abierta.
- **Ocupación de la terraza**: mesas de terraza con gente, ahora mismo, sobre las mesas de terraza que existen. No mira el clima ni el histórico.
- **Tiempo de la cuenta**: minutos desde la primera consumición hasta el ticket. No separa la cocina de la barra.
- **Cuentas de terraza por hora**: cuántas cuentas de terraza caen en cada hora del periodo.

### 5.3 Personal

- **Coste de personal**: euros de salario estimado partidos por las ventas. La referencia de la pantalla es del 30 % al 35 %.
- El salario se calcula con los **€/hora** que escribes en el panel y con las horas que la mesa estuvo abierta. La venta de la cuenta se asigna a quien emitió el ticket (o al barman de ese teléfono, si la mesa sigue abierta). **0 €** no entra en el cálculo.
- **Ventas por empleado y hora**: la misma atribución, en euros por hora.
- **Rotación de personal**: bajas del periodo partidas por la plantilla media. Solo cuenta altas y bajas hechas en **Quién soy**. Los barmans que ya estaban al crear el fichero no cuentan como contratados ese día.

### 5.4 Satisfacción

- **Clientes que repiten**: nombres de comensal que salen en más de una cuenta, sobre los nombres distintos. No hay ficha de cliente: se compara el texto escrito en la mesa, sin distinguir mayúsculas.
- **Quejas o errores**: incidencias registradas en Ticket, partidas por el número de cuentas.
- **Notas de Google y TripAdvisor**: las escribes a mano, de 0 a 5. **0** significa que aún no las has anotado. La app no entra en esas webs.

## 6. Copias de seguridad

Copia de vez en cuando estos archivos, que están en la carpeta del proyecto y no van al repositorio:

- `config_bar.json`: bar, barmans, WhatsApp, datos fiscales, próximo número de ticket, usuario y PIN del administrador, €/hora y notas de reseñas.
- `mesas_bar.json`: mesas abiertas, pedidos, historial y tickets ya emitidos.
- `menu_bar.json`: productos y precios.
- `costes_bar.json`: coste de cada producto.
- `ventas_bar.json`: cuentas archivadas para el panel.
- `personal_bar.json`: altas y bajas de barmans.
- `incidencias_bar.json`: quejas y errores de comanda.
- `assets/`: el logo.

Si se pierde `config_bar.json`, el próximo ticket puede repetir un número ya usado y hay que volver a crear el PIN. Si se pierde `ventas_bar.json`, el panel solo ve las mesas que sigan abiertas.

## 7. Atajos de uso

- Tab y Mayús+Tab mueven el foco. El control enfocado se marca con un borde.
- Los botones tienen texto, no solo un icono.
- Los avisos de éxito o error salen escritos en la página.
