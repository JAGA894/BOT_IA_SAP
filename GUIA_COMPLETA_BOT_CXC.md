# 📱 Guía Completa: Bot de Cuentas por Cobrar (CxC) en WhatsApp

> **Para quién es esta guía:** Para cualquier persona de la empresa que necesite entender cómo funciona el bot, cómo arrancarlo, qué puede hacer y cómo mantenerlo — sin necesidad de saber programar.

---

## ¿Qué es este bot y para qué sirve?

Es un **asistente financiero automático** que vive dentro de WhatsApp. Cuando alguien le escribe una pregunta sobre las Cuentas por Cobrar de la empresa, el bot le responde al instante con información real extraída directamente de la base de datos de SAP.

**Ejemplo real:**

> 👤 Usuario: *"¿Cuánto nos debe AGACEL?"*
>
> 🤖 Bot: *"El saldo vencido pendiente de AGACEL es de $192,605.00, correspondiente a 4 facturas registradas."*

No es necesario abrir SAP, no es necesario llamar a alguien de contabilidad, y no es necesario esperar. La respuesta llega en segundos.

---

## ¿Cómo funciona por dentro? (Sin tecnicismos)

Imagina que el bot es como una **recepcionista muy inteligente** que trabaja en tres pasos:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   1. ESCUCHA      →    2. ENTIENDE     →    3. CONSULTA     │
│   (WhatsApp)           (Inteligencia        y RESPONDE      │
│                         Artificial)         (Base de Datos) │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Paso 1 — El bot escucha tu mensaje en WhatsApp

Cuando alguien escribe un mensaje al número de WhatsApp del bot, ese mensaje llega automáticamente a la computadora donde está instalado el sistema. Esto funciona gracias a un programa que mantiene abierta la sesión de WhatsApp en segundo plano, como si fuera el teléfono de la empresa siempre encendido.

### Paso 2 — La Inteligencia Artificial entiende qué se está preguntando

El mensaje de texto llega a un motor de **Inteligencia Artificial de Google** (llamado Gemini). Su única tarea es leer el mensaje y decidir:

- **¿Qué tipo de dato quiere el usuario?**
  - ¿Un saldo pendiente? ¿Una factura? ¿Un conteo? ¿Una lista?
- **¿Para quién o para qué?**
  - ¿Para un cliente específico? ¿Para un proyecto? ¿Para toda la empresa?
- **¿En qué período de tiempo?**
  - ¿Este mes? ¿El año pasado? ¿Sin importar la fecha?

La IA **no inventa nada**. Solo "traduce" la pregunta en lenguaje humano a una orden estructurada muy precisa. Es como si un contador experto recibiera la pregunta y dijera: *"Ah, me están pidiendo el saldo vencido del cliente AGACEL, sin filtro de fechas."*

### Paso 3 — El sistema consulta la base de datos y construye la respuesta

Con esa orden precisa, el sistema busca la información **directamente en la base de datos** (un archivo que se actualiza con los datos de SAP). Hace los cálculos matemáticos de forma exacta y le devuelve al usuario una respuesta clara y formateada en español.

---

## ¿Qué puede responder el bot?

El bot puede contestar **6 tipos de preguntas financieras**:

| Tipo de pregunta | Ejemplos que puede entender |
|---|---|
| **Saldo vencido** (lo que un cliente debe) | "¿Cuánto nos debe AGACEL?", "¿Qué adeuda el Municipio?", "Saldo pendiente de LUVER" |
| **Total facturado** (lo que se ha facturado) | "¿Cuánto facturamos a MATA AUTOMOTIVE?", "Lo que vendimos al proyecto AEROESPACIAL" |
| **Total cobrado** (pagos recibidos) | "¿Cuánto nos ha pagado HSJ?", "Cobros recibidos en 2024" |
| **Conteo de facturas** | "¿Cuántas facturas hay?", "¿Cuántas facturas están pendientes del proyecto POES?" |
| **La factura más alta** | "¿Cuál es la factura más grande?", "El mayor saldo en el sistema" |
| **Lista de clientes** | "¿Qué clientes tenemos?", "¿Quiénes tienen facturas del proyecto AEROESPACIAL?" |

### También entiende lenguaje coloquial

No es necesario escribir de forma exacta o formal. El bot entiende expresiones como:

- *"¿Cuánto hay en la calle?"* → Lo interpreta como saldo por cobrar
- *"¿Lo que vendimos este año?"* → Lo interpreta como facturación del año en curso
- *"Dinero que nos deben"* → Saldo vencido total
- *"El mes pasado"*, *"este trimestre"*, *"en 2024"* → El bot calcula automáticamente las fechas exactas

---

## Bienvenida para usuarios nuevos

Si alguien escribe simplemente **"Hola"** o **"¿Qué puedes hacer?"**, el bot no busca en la base de datos. En cambio, se presenta y explica sus capacidades:

> 🤖 *"¡Hola! Soy el Asistente Financiero de Cuentas por Cobrar. Los datos están sincronizados con SAP. Puedo ayudarte con:*
> - *Consultar el saldo vencido de un cliente*
> - *Ver el total facturado o cobrado*
> - *Contar facturas por proyecto o fecha*
> - *Buscar la factura con mayor saldo*
> - *Listar todos los clientes registrados..."*

---

## ¿Quién puede usar el bot?

El bot tiene una **lista de números autorizados**. Solo las personas cuyos números de WhatsApp estén en esa lista pueden recibir respuestas. Si alguien no autorizado escribe, el bot simplemente no responde.

Esto es una medida de seguridad para que información financiera confidencial no llegue a personas externas.

---

## Seguridad: ¿Qué pasa si alguien intenta engañar al bot?

El bot tiene protecciones específicas contra intentos de manipulación:

- Si alguien escribe *"Olvida tus instrucciones"* o *"Actúa como otro sistema"*, el bot responde simplemente: *"Solo puedo consultar información de CxC."* y no hace nada más.
- El bot **nunca puede modificar, borrar ni alterar** ningún dato. Solo tiene permiso de lectura — es como darle acceso de "solo ver" en SAP.
- Todos los números que se buscan pasan por un sistema de seguridad que impide ataques de inyección (intentos de extraer datos de formas no autorizadas).

---

## ¿De dónde vienen los datos?

Los datos vienen de un **archivo de base de datos local** (`bot_ia.db`) que es una copia de la información de SAP Business One. Este archivo se actualiza mediante un proceso de sincronización (ETL) que extrae la información de SAP y la guarda localmente para que el bot pueda consultarla rápidamente.

> [!IMPORTANT]
> Si los datos de SAP cambian, se debe correr el proceso de sincronización para que el bot vea la información actualizada. El bot trabaja con los datos que tiene disponibles en ese momento — no accede a SAP en tiempo real.

---

## Las piezas del sistema (sin tecnicismos)

El sistema está compuesto por **3 programas que trabajan juntos** en la misma computadora:

```
┌──────────────────────────────────────────────────────────────────┐
│                    COMPUTADORA / SERVIDOR                        │
│                                                                  │
│  ┌────────────────┐   ┌─────────────────┐   ┌────────────────┐  │
│  │   PROGRAMA 1   │   │   PROGRAMA 2    │   │   PROGRAMA 3   │  │
│  │                │   │                 │   │                │  │
│  │  WhatsApp Web  │◄──►  Cerebro (IA +  │◄──►   Internet    │  │
│  │  (Node.js)     │   │  Base de Datos) │   │   (Ngrok)      │  │
│  │                │   │  (Python)       │   │                │  │
│  └────────────────┘   └─────────────────┘   └────────────────┘  │
│         ▲                                          ▲             │
│         │                                          │             │
│    WhatsApp del                              Mensajes de         │
│    número del bot                            WhatsApp llegan     │
│                                              desde internet      │
└──────────────────────────────────────────────────────────────────┘
```

| Programa | Qué hace | Nombre técnico |
|---|---|---|
| **WhatsApp Web** | Mantiene la sesión de WhatsApp activa y envía/recibe mensajes | `whatsapp_client.js` |
| **Cerebro (IA + DB)** | Recibe el mensaje, lo manda a Gemini, consulta la base de datos y construye la respuesta | `bot_app.py` |
| **Puente de Internet** | Permite que los mensajes de WhatsApp lleguen a la computadora local aunque no tenga IP pública | `ngrok` |

---

## ¿Cómo se enciende el bot? (Arranque completo)

Existe un archivo llamado **`start_all.ps1`** que enciende los 3 programas automáticamente con un solo clic.

### Pasos para arrancar:

1. Abrir la carpeta `BOT_IA_HANA` en el Escritorio
2. Hacer **clic derecho** sobre el archivo `start_all.ps1`
3. Seleccionar **"Ejecutar con PowerShell"**
4. El sistema abrirá **3 ventanas** automáticamente:
   - Una ventana azul para el Cerebro (IA)
   - Una ventana para WhatsApp Web
   - Una ventana para el puente de Internet (Ngrok)
5. En la ventana de WhatsApp, **escanear el código QR** con el teléfono del número del bot (solo la primera vez o si la sesión expiró)
6. Cuando aparezca el mensaje ✅ *"Cliente de WhatsApp conectado y listo"*, el bot está activo

> [!IMPORTANT]
> Las **3 ventanas deben permanecer abiertas** mientras el bot esté en funcionamiento. Si se cierra cualquiera de las tres, el bot dejará de responder.

---

## ¿Cómo se apaga el bot?

Simplemente cerrar las 3 ventanas de PowerShell que se abrieron. No hay ningún riesgo de perder datos al apagarlo.

---

## ¿Qué pasa si el bot deja de responder?

Si el bot no contesta a los mensajes, puede deberse a una de estas causas:

| Síntoma | Causa probable | Solución |
|---|---|---|
| No responde a nadie | Alguna de las 3 ventanas se cerró | Volver a ejecutar `start_all.ps1` |
| Dice "error de conexión" | El puente de internet (Ngrok) se reinició | Volver a ejecutar `start_all.ps1` |
| El QR de WhatsApp apareció de nuevo | La sesión de WhatsApp expiró | Escanear el QR nuevamente con el teléfono |
| Responde que no tiene acceso | El número no está en la lista de autorizados | Contactar al equipo de sistemas para agregar el número |
| Los datos parecen desactualizados | No se ha corrido la sincronización con SAP | Correr el proceso de actualización de la base de datos |

---

## ¿Cada cuánto hay que actualizar los datos?

El bot trabaja con una **copia local de los datos de SAP**. Esta copia no se actualiza sola — alguien del equipo de sistemas debe correr el proceso de sincronización (ETL) cada vez que se quieran reflejar los datos más recientes.

**Frecuencia recomendada:** Una vez al día, preferiblemente al inicio de la jornada laboral, para que los usuarios del bot trabajen siempre con información del día anterior al cierre.

---

## Limitaciones importantes

> [!WARNING]
> El bot tiene las siguientes limitaciones que es importante conocer:

- **No puede responder dos preguntas a la vez en un mismo mensaje.** Si alguien pregunta *"¿Cuánto debe AGACEL y cuánto debe HSJ?"*, el bot responderá solo la primera pregunta y ofrecerá buscar la segunda en el siguiente mensaje.
- **No puede modificar datos.** Solo consulta — no puede registrar pagos, crear facturas ni cambiar nada en SAP.
- **No tiene memoria de conversaciones anteriores.** Cada mensaje se procesa de forma independiente. No recuerda lo que se preguntó hace 10 minutos.
- **Depende de internet.** Si la conexión a internet de la computadora cae, el bot no podrá recibir mensajes nuevos hasta que se restaure la conexión.
- **Los datos de facturación** (`Total_factura`) provienen de SAP pero pueden aparecer en $0.00 si SAP no ha registrado el importe. El saldo vencido (`Saldo_vencido`) sí refleja la deuda real actualizada.

---

## Glosario de términos que usa el bot

| Lo que el usuario dice | Lo que el bot entiende |
|---|---|
| "Saldo", "deuda", "lo que nos deben", "pendiente", "por cobrar", "dinero en la calle" | **Saldo vencido** (CxC) |
| "Lo que vendimos", "facturación", "total de facturas", "cuánto facturamos" | **Total facturado** |
| "Lo que cobramos", "pagos recibidos", "lo que nos pagaron", "entradas" | **Total cobrado** |
| "Cuántas facturas", "número de registros", "cuántas hay" | **Conteo de facturas** |
| "La más alta", "la mayor", "el top", "la más grande", "cuál debe más" | **Factura máxima** |
| "Lista de clientes", "qué clientes tenemos", "quiénes son" | **Listado de clientes** |
| "Este mes", "el mes pasado", "este año", "el año pasado", "primer trimestre", etc. | **Rango de fechas calculado automáticamente** |

---

## Archivo de referencia rápida

```
📁 BOT_IA_HANA (carpeta principal en el Escritorio)
│
├── 🚀 start_all.ps1          ← Ejecutar esto para encender el bot
├── 🗄️  bot_ia.db              ← Base de datos con los datos de SAP
├── 🧠 bot_app.py             ← El cerebro del bot (no modificar)
├── 📱 whatsapp_client.js     ← Conexión con WhatsApp (no modificar)
├── 🔬 test_cross_validation.py ← Prueba de exactitud matemática
├── 🧪 test_queries.py        ← Prueba general de funcionalidad
└── ⚙️  .env                  ← Configuración y contraseñas (no compartir)
```

---

## Preguntas frecuentes

**¿El bot puede responder desde cualquier teléfono?**
Solo el número de WhatsApp configurado como "número del bot" recibirá y enviará los mensajes. Los usuarios pueden escribirle a ese número desde cualquier teléfono, siempre que su número esté en la lista de autorizados.

**¿Qué pasa si dos personas le escriben al bot al mismo tiempo?**
El bot puede atender múltiples conversaciones simultáneas. Cada consulta se procesa de forma independiente y la respuesta llega a quien la preguntó.

**¿Los datos son seguros?**
Sí. La información nunca sale de la computadora local hacia servicios externos de almacenamiento. Solo el texto del mensaje (la pregunta) se envía a la IA de Google para entender qué se está preguntando — nunca se envían datos financieros a Google.

**¿Puede el bot equivocarse?**
El bot calcula de forma matemáticamente exacta — los números que reporta están verificados contra la base de datos. Lo que sí puede variar es si los datos en SAP no han sido sincronizados recientemente.

**¿Hay que pagarle a Google por cada pregunta?**
Sí, el servicio de Inteligencia Artificial de Google (Gemini) tiene un costo por uso. Si el bot recibe muchas preguntas, el costo aumenta. Para uso empresarial normal, el costo es mínimo.

---

*Documento generado automáticamente — Bot CxC WhatsApp v5.0 — Agosto 2026*
