# Especificación de requisitos

**Sistema:** Cuenta del Bar  
**Tipo:** aplicación web local (Python, Streamlit)  
**Usuarios:** barmans del mismo local, cada uno con su móvil, contra un único proceso y unos únicos ficheros JSON

## 1. Objetivo

Llevar la cuenta de varias mesas a la vez, con el nombre de quien apunta cada cambio, poder entregar esa cuenta por WhatsApp o en un PDF imprimible con código QR, y mostrar al administrador los indicadores del local calculados con esos datos.

## 2. Alcance

Entra en el sistema:

- Identidad del barman, marca, teléfono de WhatsApp y datos fiscales.
- Carta de productos con icono, precio y coste opcional.
- Mesas con zona y asientos, comensales y consumiciones.
- Historial de acciones, archivo de cuentas, altas y bajas, e incidencias.
- Mensaje de WhatsApp.
- Ticket PDF en 80 mm y en A4, con IVA incluido y QR.
- Acceso de administrador con PIN y panel de indicadores.

No entra:

- Un PIN para trabajar de barman. El PIN solo abre el panel.
- Cobro con tarjeta, caja o arqueo.
- Cocina, stock, proveedores o el clima de la terraza.
- Lectura automática de reseñas en Google o TripAdvisor.
- Un servidor que valide el QR y responda «ticket válido».
- Factura electrónica Verifactu o TicketBAI.
- Impresora de 58 mm sin cambiar medidas en el código.

## 3. Actores

| Actor | Descripción |
| --- | --- |
| Barman | Persona del local. Se identifica por nombre en su móvil. Registra pedidos y emite tickets. |
| Administrador | Quien conoce el PIN. En ese navegador ve el panel. No sustituye al barman. |
| Comensal | No usa la aplicación. Es un nombre asociado a una mesa y a unas consumiciones. |
| Lector de QR | Cámara del móvil o aplicación de códigos. Solo lee el texto que lleva el QR. |

## 4. Requisitos funcionales

### Configuración

| ID | Requisito |
| --- | --- |
| RF-01 | El sistema guarda una lista de barmans y permite alta y baja. |
| RF-02 | Cada navegador elige un barman de esa lista. La elección no cambia la de otro móvil. |
| RF-03 | Sin barman identificado no se registra una consumición ni se emite un ticket fiscal. |
| RF-04 | El sistema guarda el nombre comercial y un logo PNG, JPG, WEBP o GIF, y los muestra en la interfaz. |
| RF-05 | El sistema guarda un teléfono de WhatsApp con prefijo de país y lo normaliza a solo dígitos. |
| RF-06 | El sistema guarda razón social, NIF/CIF, dirección fiscal, tipo de IVA (0, 4, 10 o 21 %), serie y próximo número de ticket. |
| RF-07 | Esos datos sobreviven al cerrar el navegador, en `config_bar.json`. |

### Carta

| ID | Requisito |
| --- | --- |
| RF-08 | Se puede crear, modificar y eliminar un producto con icono, nombre, precio y coste. |
| RF-09 | El precio se guarda con céntimos exactos (`Decimal`), no con coma flotante binaria. |
| RF-10 | El precio del menú se trata como IVA incluido. |
| RF-11 | Eliminar o renombrar un producto actualiza las mesas abiertas. |
| RF-12 | La carta se puede restaurar a cuatro productos de ejemplo. Antes se archivan las cuentas abiertas con importe. |
| RF-13 | La carta persiste en `menu_bar.json`. El coste mayor que 0 persiste en `costes_bar.json`. Un coste 0 se trata como desconocido y no se guarda. |

### Mesas y pedidos

| ID | Requisito |
| --- | --- |
| RF-14 | Se puede crear una mesa con nombre, zona (barra, mesas o terraza) y asientos, renombrarla, vaciarla o cerrarla. |
| RF-15 | Vaciar quita comensales y consumiciones, archiva la cuenta si tenía importe, renueva la hora de apertura y mantiene la mesa. Cerrar archiva y elimina la mesa. |
| RF-16 | Hay una mesa activa por navegador. |
| RF-17 | Cada mesa guarda el instante en que se abrió, la zona, los asientos, sus comensales y un historial. |
| RF-18 | Un comensal solo puede estar en una mesa. Si se asigna a otra, se mueve con sus consumiciones. |
| RF-19 | Se puede sumar, restar o quitar una línea de producto del comensal seleccionado. |
| RF-20 | Cada cambio de cantidad guarda instante, barman, acción, comensal, producto, delta y cantidad resultante. |
| RF-21 | Las mesas persisten en `mesas_bar.json` y se releen del disco en cada interacción, para que varios móviles compartan la sala. Si una mesa no tiene zona, se infiere del nombre. |

### Cuenta y WhatsApp

| ID | Requisito |
| --- | --- |
| RF-22 | La pestaña Ticket muestra las líneas por comensal, subtotales, total de mesa y un aviso de cuadre. |
| RF-23 | La trazabilidad en pantalla muestra los últimos 50 eventos de la mesa. |
| RF-24 | Se muestra el número de comensales, de consumiciones y el total. |
| RF-25 | Hay una vista previa del mensaje de WhatsApp y un enlace que lo abre. |
| RF-26 | El mensaje incluye nombre del bar, mesa, hora, barman, desglose por comensal, total y los últimos 12 eventos. |
| RF-27 | Si hay teléfono configurado, el enlace abre ese chat. Si no, WhatsApp pide el destinatario. |

### Ticket fiscal

| ID | Requisito |
| --- | --- |
| RF-28 | Desde Ticket se puede generar un PDF de 80 mm de ancho y otro A4. |
| RF-29 | El PDF incluye emisor, NIF, dirección, número correlativo, fecha, mesa, barman, productos agrupados sin comensal, desglose de IVA, total, QR y un pie. |
| RF-30 | Con IVA 0 % el PDF indica que el IVA va incluido y no desglosa cuota. |
| RF-31 | El número tiene la forma serie y cinco dígitos, por ejemplo `A-00001`. |
| RF-32 | La misma cuenta, con los mismos datos fiscales, no consume otro número si se vuelve a descargar. |
| RF-33 | Un cambio de líneas, total o datos fiscales de esa cuenta hace que la siguiente emisión use el número siguiente. |
| RF-34 | Emitir exige barman identificado y al menos una línea con importe. |
| RF-35 | El logo del bar se imprime en el encabezado si existe. |
| RF-36 | El QR contiene el texto del ticket en ASCII, sin tildes ni eñe, para que los lectores no lo muestren como caracteres de otro idioma. |
| RF-37 | En el PDF de 80 mm el QR se imprime a 68 mm de ancho, con margen blanco alrededor, para poder escanearlo en papel térmico. |

### Administrador e indicadores

| ID | Requisito |
| --- | --- |
| RF-38 | Si no hay PIN, la barra lateral permite crear el usuario `administrador` con un PIN de al menos 4 caracteres. |
| RF-39 | Con PIN, ese navegador entra y sale del panel. Otro móvil no hereda la sesión. |
| RF-40 | La pestaña Panel solo existe con la sesión de administrador abierta. |
| RF-41 | El panel calcula ticket medio general y por zona, coste de producto, RevPASH, margen, rotación de mesa, ocupación actual de la terraza, tiempo de la cuenta, coste de personal, ventas por empleado y hora, rotación de personal, clientes que repiten y tasa de quejas. |
| RF-42 | El periodo es las últimas 24 horas, 7 días, 30 días o todo el histórico. |
| RF-43 | Una mesa abierta con importe cuenta en el panel. Si ya estaba archivada con la misma apertura, la foto en vivo sustituye a la archivada. |
| RF-44 | El coste de producto y el margen ignoran los productos sin coste. El coste de personal ignora al barman sin €/hora. |
| RF-45 | El administrador anota en el panel los €/hora y las notas de Google y TripAdvisor, de 0 a 5. La aplicación no consulta esas webs. |
| RF-46 | Un barman identificado puede registrar una queja o error de comanda, con nota opcional. Quitar una consumición no cuenta como queja. |
| RF-47 | Alta y baja de barman quedan en `personal_bar.json`. El PIN se puede cambiar desde el panel y solo se guarda en `config_bar.json`. |

## 5. Requisitos no funcionales

| ID | Requisito |
| --- | --- |
| RNF-01 | La interfaz es una web usable con el dedo en un móvil y con teclado en un ordenador. |
| RNF-02 | Los controles tienen texto visible. El foco de teclado se ve. Los avisos salen por escrito. |
| RNF-03 | Los importes no acumulan error de céntimos. |
| RNF-04 | Configuración, carta, mesas y logo se guardan en ficheros locales, no en un servicio externo. |
| RNF-05 | Esos ficheros de datos no se suben al repositorio. |
| RNF-06 | El PDF térmico cabe en un rollo de 80 mm. El A4 cabe en una hoja ISO A4. |
| RNF-07 | El texto del PDF conserva tildes y eñe cuando el sistema tiene Arial. |
| RNF-08 | Dos navegadores contra el mismo proceso comparten mesas, carta y archivo de cuentas. Cada uno conserva su barman y, si entra, su sesión de administrador. |
| RNF-09 | El PIN del administrador no se sube al repositorio. |
| RNF-10 | Un indicador sin dato de origen se muestra vacío. No se sustituye por una cifra de ejemplo. |

## 6. Datos persistentes

| Fichero | Contenido |
| --- | --- |
| `config_bar.json` | Nombre, logo, barmans, WhatsApp, datos fiscales, próximo número, usuario y PIN, €/hora, notas de reseñas |
| `menu_bar.json` | Mapa producto → precio con dos decimales |
| `costes_bar.json` | Coste unitario mayor que 0 |
| `mesas_bar.json` | Mesas, zona, asientos, pedidos, historial y ticket emitido |
| `ventas_bar.json` | Cuentas archivadas para el panel |
| `personal_bar.json` | Altas y bajas de barmans |
| `incidencias_bar.json` | Quejas y errores de comanda |
| `assets/marca_bar.*` | Imagen de marca |

El barman activo, la mesa activa, el comensal activo y la sesión de administrador no se guardan en disco.

## 7. Reglas de negocio

- RN-01. Un comensal, una mesa.
- RN-02. El precio de carta incluye el IVA.
- RN-03. El número de ticket es correlativo por serie y solo avanza al emitir una cuenta distinta.
- RN-04. Vaciar una mesa anula el ticket fiscal asociado a esa cuenta.
- RN-05. El QR no sustituye al texto impreso: el papel muestra tildes; el QR, el mismo texto sin ellas.
- RN-06. El panel no estima un coste, una reseña ni el clima. Si no están informados, el indicador queda vacío o fuera del porcentaje.
- RN-07. La misma apertura de mesa cuenta una sola vez: la mesa abierta sustituye a su fila archivada.

## 8. Restricciones

- Un solo proceso Streamlit y una sola carpeta de JSON. No hay sincronización entre dos ordenadores.
- Quien abre la URL puede elegir cualquier barman de la lista. El panel exige el PIN de ese ordenador.
- La impresión física depende de la impresora y del diálogo del sistema. La aplicación solo entrega el PDF con el tamaño de página pedido.
