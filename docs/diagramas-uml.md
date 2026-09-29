# Diagramas UML

Los diagramas describen el dominio y los flujos reales del código. La implementación no usa clases: mesas, eventos y tickets son diccionarios en JSON, y la lógica está en funciones de `bar.py` y `ticket_fiscal.py`. El diagrama de clases es el modelo de información, no un mapa de `class` de Python.

## 1. Casos de uso

```mermaid
flowchart TB
  barman((Barman))
  lector((Quien escanea))
  subgraph sistema [Cuenta del Bar]
    id[Identificarse]
    carta[Mantener la carta]
    cfg[Configurar marca, WhatsApp y datos fiscales]
    mesas[Gestionar mesas]
    gente[Asignar comensales]
    pedido[Apuntar consumiciones]
    cuenta[Revisar cuenta y trazabilidad]
    wa[Compartir por WhatsApp]
    pdf[Emitir ticket PDF]
  end
  barman --- id
  barman --- carta
  barman --- cfg
  barman --- mesas
  barman --- gente
  barman --- pedido
  barman --- cuenta
  barman --- wa
  barman --- pdf
  lector --- pdf
```

El detalle escrito de cada caso está en [casos de uso](casos-de-uso.md).

## 2. Clases del dominio

```mermaid
classDiagram
  class Configuracion {
    nombre_bar
    imagen_marca
    whatsapp_telefono
    barmans
    razon_social
    nif
    direccion_fiscal
    iva_porcentaje
    serie_ticket
    proximo_numero_ticket
  }
  class Producto {
    nombre
    icono
    precio Decimal
  }
  class Mesa {
    nombre
    abierta_en
    comensales
    historial
    ticket_fiscal
  }
  class Comensal {
    nombre
    consumiciones
  }
  class Evento {
    ts
    barman
    comensal
    accion
    producto
    cantidad_delta
    cantidad_resultante
    detalle
  }
  class TicketFiscal {
    huella
    numero
    fecha
    lineas agrupadas
    base
    cuota_iva
    total
  }
  Configuracion "1" --> "*" Producto : carta aparte
  Mesa "1" *-- "*" Comensal
  Mesa "1" *-- "*" Evento
  Mesa "1" o-- "0..1" TicketFiscal
  Comensal "*" --> "*" Producto : cantidad
```

`iva_porcentaje` solo puede ser 0, 4, 10 o 21. `TicketFiscal` aparece cuando se emite y desaparece al vaciar la mesa.

## 3. Secuencia: apuntar una consumición

```mermaid
sequenceDiagram
  actor Barman
  participant UI as Pedido
  participant App as bar.py
  participant Disco as mesas_bar.json
  Barman->>UI: Pulsa un producto
  UI->>App: exigir_barman()
  alt sin barman
    App-->>UI: aviso y no guarda
  else con barman
    App->>App: suma 1 a comensal y producto
    App->>App: registrar_evento añadir
    App->>Disco: guardar_mesas()
    App-->>UI: resumen con la nueva cantidad
  end
```

## 4. Secuencia: emitir y descargar el ticket

```mermaid
sequenceDiagram
  actor Barman
  participant UI as Ticket
  participant App as bar.py
  participant Fiscal as ticket_fiscal.py
  participant Disco as JSON
  Barman->>UI: Ticket termico o Factura A4
  UI->>App: exigir_barman()
  App->>Fiscal: huella_cuenta(...)
  alt misma huella ya guardada
    App-->>UI: reutiliza el numero
  else cuenta nueva
    App->>Disco: proximo_numero_ticket + 1
    App->>Fiscal: desglose_iva(...)
    App->>Disco: ticket_fiscal y evento
  end
  UI->>Fiscal: generar_pdf_ticket termica y A4
  Fiscal->>Fiscal: texto_qr en ASCII y PNG
  Fiscal-->>UI: dos PDF
  Barman->>UI: descarga el formato elegido
```

La primera pulsación solo emite. La descarga aparece en la recarga siguiente, porque Streamlit necesita los bytes antes de pintar el botón.

## 5. Estados de una mesa

```mermaid
stateDiagram-v2
  [*] --> Abierta: crear
  Abierta --> ConConsumo: asignar comensal y pedir
  ConConsumo --> ConConsumo: cambiar cantidades
  ConConsumo --> TicketEmitido: emitir PDF
  TicketEmitido --> TicketEmitido: volver a descargar
  TicketEmitido --> ConConsumo: cambia la cuenta
  ConConsumo --> Abierta: vaciar
  TicketEmitido --> Abierta: vaciar
  Abierta --> [*]: cerrar
  ConConsumo --> [*]: cerrar
  TicketEmitido --> [*]: cerrar
```

«Cambia la cuenta» significa que cambia alguna línea, el total o un dato fiscal que entra en la huella. La mesa sigue abierta. El ticket anterior deja de valer para esa huella y la próxima emisión pide otro número.

## 6. Actividad de una jornada

```mermaid
flowchart TD
  inicio([Empieza el turno]) --> quien[Elegir barman en el movil]
  quien --> mesa{Hay mesa?}
  mesa -->|No| crear[Crear mesa]
  mesa -->|Si| elegir[Seleccionar mesa]
  crear --> sentar[Asignar comensales]
  elegir --> sentar
  sentar --> pedir[Apuntar consumiciones]
  pedir --> mas{Siguen pidiendo?}
  mas -->|Si| pedir
  mas -->|No| revisar[Revisar ticket y trazabilidad]
  revisar --> canal{Como se entrega?}
  canal -->|WhatsApp| wa[Abrir chat con el mensaje]
  canal -->|Papel| pdf[Emitir numero y descargar PDF]
  pdf --> imprimir[Imprimir 80 mm o A4]
  wa --> fin([Cuenta entregada])
  imprimir --> fin
```

## 7. Componentes

```mermaid
flowchart LR
  subgraph navegador [Navegador del barman]
    ui[Paginas Streamlit]
  end
  subgraph proceso [Proceso Python]
    bar[bar.py]
    fiscal[ticket_fiscal.py]
  end
  subgraph disco [Carpeta del proyecto]
    cfg[config_bar.json]
    menu[menu_bar.json]
    mesas[mesas_bar.json]
    logo[assets]
  end
  ui --> bar
  bar --> fiscal
  bar --> cfg
  bar --> menu
  bar --> mesas
  bar --> logo
  bar --> wa[WhatsApp en el movil]
  fiscal --> papel[Impresora 80 mm o A4]
```

WhatsApp no recibe una llamada del servidor. `bar.py` solo construye una URL `api.whatsapp.com` y el navegador la abre. La impresora tampoco está conectada al proceso: el barman descarga el PDF y lo imprime con el sistema.

## 8. Despliegue

```mermaid
flowchart TB
  subgraph local [Un ordenador del bar]
    venv[Python y .venv]
    st[streamlit run bar.py]
    json[JSON y assets]
    venv --> st
    st --> json
  end
  movil1[Movil del barman 1]
  movil2[Movil del barman 2]
  termica[Impresora termica 80 mm]
  a4[Impresora A4]
  movil1 -->|misma red| st
  movil2 -->|misma red| st
  movil1 -->|PDF| termica
  movil1 -->|PDF| a4
```

No hay servidor de base de datos ni de verificación de QR. Si se arranca la aplicación en dos ordenadores distintos, cada uno tiene sus propios JSON y sus propios números de ticket.
