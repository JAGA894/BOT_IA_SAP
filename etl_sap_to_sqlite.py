import os
import re
import time
import sqlite3
import logging
import requests
import schedule
from collections import defaultdict
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

SL_URL = os.getenv("SL_URL").rstrip('/') if os.getenv("SL_URL") else None
SAP_COMPANIES = os.getenv("SAP_COMPANIES", "")
SL_USERNAME = os.getenv("SL_USERNAME")
SL_PASSWORD = os.getenv("SL_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "bot_ia.db")
# Hora de corte al final del día laboral para enviar el resumen acumulado (por defecto 18 = 6:00 PM)
HORA_RESUMEN_DIARIO = int(os.getenv("HORA_RESUMEN_DIARIO", "18"))

NOMBRES_DISPLAY = {
    "SBA_PROD":          "SBA",
    "ERSA_PRODUCTIVA":   "ERSA",
    "ERSAGRO_PROD":      "ERSAGRO",
    "SA_PRODUCTIVA":     "SA",
    "SB_PROD":           "SB",
    "JEUMA_PRODUCTIVA":  "JEUMA",
    "ERSA_TESTPB1":      "ERSA Test",
}

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    try:
        with sqlite3.connect(DB_NAME, timeout=15.0) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
        
            # Crear tabla CxC_Local basada en la vista V_CXC_BOT_IA
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS CxC_Local (
                    Empresa TEXT,
                    Folio_factura INTEGER,
                    Nombre_cliente TEXT,
                    Nombre_extranjero TEXT,
                    Fecha_documento DATE,
                    Proyecto TEXT,
                    Impuestos REAL,
                    Retenciones REAL,
                    Total_factura REAL,
                    Importe_aplicado REAL,
                    Saldo_vencido REAL
                )
            ''')
        
            # Tabla de control de arranque y estados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS etl_control (
                    id INTEGER PRIMARY KEY,
                    primer_arranque_completado INTEGER DEFAULT 0,
                    ultimo_etl_exitoso TEXT,
                    ultimo_resumen_fecha TEXT
                )
            ''')
        
            # Inicializar fila de control si no existe
            cursor.execute("INSERT OR IGNORE INTO etl_control (id, primer_arranque_completado) VALUES (1, 0)")

            # Asegurar columna ultimo_resumen_fecha en etl_control si la tabla ya existía
            cursor.execute("PRAGMA table_info(etl_control)")
            etl_cols = [c[1] for c in cursor.fetchall()]
            if "ultimo_resumen_fecha" not in etl_cols:
                cursor.execute("ALTER TABLE etl_control ADD COLUMN ultimo_resumen_fecha TEXT")
        
            # Tabla para guardar la foto anterior de los folios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS CxC_Snapshot_folios (
                    empresa TEXT,
                    folio INTEGER,
                    PRIMARY KEY (empresa, folio)
                )
            ''')
        
            # Tabla de destinatarios del broadcast
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notificacion_destinatarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    destino TEXT NOT NULL UNIQUE,
                    activo INTEGER DEFAULT 1,
                    descripcion TEXT
                )
            ''')
        
            # Tabla de cola para notificaciones fallidas o fuera de horario
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notificaciones_pendientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mensaje TEXT NOT NULL,
                    timestamp_intento TEXT,
                    enviar_desde TEXT,
                    enviado INTEGER DEFAULT 0
                )
            ''')

            # NUEVA TABLA: Acumulador diario de nuevas facturas (se limpia cada día tras enviar el resumen)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cxc_movimientos_dia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    empresa TEXT NOT NULL,
                    folio INTEGER NOT NULL,
                    proyecto TEXT,
                    cliente TEXT,
                    monto REAL DEFAULT 0.0,
                    saldo REAL DEFAULT 0.0,
                    fecha_deteccion TEXT,
                    UNIQUE(empresa, folio)
                )
            ''')
        
            # Verificar si las columnas necesarias existen en caso de que la tabla ya estuviera creada
            cursor.execute("PRAGMA table_info(CxC_Local)")
            columns = [column[1] for column in cursor.fetchall()]
        
            needed_columns = {
                'Empresa': 'TEXT',
                'Folio_factura': 'INTEGER',
                'Nombre_cliente': 'TEXT',
                'Nombre_extranjero': 'TEXT',
                'Fecha_documento': 'DATE',
                'Proyecto': 'TEXT',
                'Impuestos': 'REAL',
                'Retenciones': 'REAL',
                'Total_factura': 'REAL',
                'Importe_aplicado': 'REAL',
                'Saldo_vencido': 'REAL',
                'ultima_actualizacion': 'TEXT'
            }
        
            for col, col_type in needed_columns.items():
                if col not in columns:
                    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', col) or not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', col_type):
                        raise ValueError(f"Nombre de columna o tipo inválido detectado: {col} {col_type}")
                    cursor.execute(f"ALTER TABLE CxC_Local ADD COLUMN {col} {col_type}")
                    logger.info(f"Columna '{col}' añadida a la tabla existente.")

            # TAREA 2: Limpiar duplicados antes de crear UNIQUE INDEX
            cursor.execute('''
                DELETE FROM CxC_Local 
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) 
                    FROM CxC_Local 
                    GROUP BY Empresa, Folio_factura
                )
            ''')

            # TAREA 2: UNIQUE INDEX para UPSERT
            cursor.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_cxc_empresa_folio ON CxC_Local(Empresa, Folio_factura)''')

            # TAREA 2: Tabla etl_historial
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS etl_historial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    empresa TEXT,
                    registros_sap INTEGER,
                    registros_nuevos INTEGER,
                    registros_actualizados INTEGER,
                    duracion_segundos REAL,
                    exito INTEGER DEFAULT 1,
                    error_msg TEXT
                )
            ''')
            logger.info("Base de datos y tablas inicializadas correctamente.")

        conn.commit()
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")

def sl_login(company_db):
    """Autentica con SAP B1 Service Layer y devuelve la sesión para la empresa dada."""
    if not all([SL_URL, company_db, SL_USERNAME, SL_PASSWORD]):
        logger.error(f"Faltan credenciales o URL para la empresa {company_db}")
        return None

    url = f"{SL_URL}/b1s/v1/Login"
    payload = {
        "CompanyDB": company_db.strip(),
        "UserName": SL_USERNAME,
        "Password": SL_PASSWORD
    }
    
    session = requests.Session()
    try:
        # verify=False es común en SAP B1 por certificados autofirmados
        response = session.post(url, json=payload, verify=False, timeout=30)
        response.raise_for_status()
        
        logger.info(f"Login en Service Layer exitoso para la empresa {company_db}.")
        return session
    except requests.exceptions.Timeout:
        logger.error(f"Timeout en Login de Service Layer para {company_db}.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de conexión o autenticación en Service Layer para {company_db}: {e}")
        return None

def sl_logout(session):
    """Cierra la sesión en SAP B1 Service Layer."""
    if not session:
        return
        
    url = f"{SL_URL}/b1s/v1/Logout"
    try:
        session.post(url, verify=False, timeout=10)
        logger.info("Logout de Service Layer exitoso.")
    except Exception as e:
        logger.warning(f"Error durante el logout de Service Layer: {e}")

def consolidar_por_folio(rows):
    """
    Si una misma factura (Empresa, Folio_factura) viene dividida en varias líneas de proyecto
    desde la vista de SAP HANA, suma sus importes y concatena los proyectos para no perder saldo
    en el UPSERT por (Empresa, Folio_factura).
    """
    agrupado = {}
    for row in rows:
        emp = row.get('Empresa')
        fol = row.get('Folio_factura') or row.get('Folio_de_la_factura')
        if not emp or fol is None:
            continue
        key = (emp, fol)
        proy = (row.get('Proyecto') or 'Sin Proyecto').strip()
        imp = float(row.get('Impuestos') or 0.0)
        ret = float(row.get('Retenciones') or 0.0)
        tot = float(row.get('Total_factura') if row.get('Total_factura') is not None else (row.get('Total_de_la_factura') or 0.0))
        apl = float(row.get('Importe_aplicado') or 0.0)
        sal = float(row.get('Saldo_vencido') or 0.0)

        if key not in agrupado:
            copia = dict(row)
            copia['Folio_factura'] = fol
            copia['Proyecto'] = proy
            copia['Impuestos'] = imp
            copia['Retenciones'] = ret
            copia['Total_factura'] = tot
            copia['Importe_aplicado'] = apl
            copia['Saldo_vencido'] = sal
            copia['_proyectos_set'] = [proy]
            agrupado[key] = copia
        else:
            item = agrupado[key]
            item['Impuestos'] = round(item['Impuestos'] + imp, 2)
            item['Retenciones'] = round(item['Retenciones'] + ret, 2)
            item['Total_factura'] = round(item['Total_factura'] + tot, 2)
            item['Importe_aplicado'] = round(item['Importe_aplicado'] + apl, 2)
            item['Saldo_vencido'] = round(item['Saldo_vencido'] + sal, 2)
            if proy and proy not in item['_proyectos_set']:
                item['_proyectos_set'].append(proy)
                item['Proyecto'] = " / ".join(item['_proyectos_set'])

    resultado = []
    for item in agrupado.values():
        item.pop('_proyectos_set', None)
        resultado.append(item)
    return resultado

def fetch_cxc_data(session, company_name):
    """Obtiene los datos de la vista V_CXC_BOT_IA y les añade el nombre de la empresa."""
    url = f"{SL_URL}/b1s/v1/sml.svc/V_CXC_BOT_IA"
    all_data = []
    
    try:
        while url:
            try:
                response = session.get(url, verify=False, timeout=30)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                logger.error(f"Timeout al obtener datos (paginación) para {company_name}. url={url}")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Error HTTP al obtener datos para {company_name}: {e}")
                return None
                
            data = response.json()
            
            if 'value' in data:
                # Inyectar el nombre de la empresa en cada registro
                for row in data['value']:
                    row['Empresa'] = company_name.strip()
                all_data.extend(data['value'])
            
            # Manejar paginación de OData
            next_link = data.get('@odata.nextLink') or data.get('odata.nextLink')
            if next_link:
                if next_link.startswith('http'):
                    url = next_link
                else:
                    if next_link.startswith('/b1s/v1/'):
                        next_link = next_link.replace('/b1s/v1/', '')
                    if not next_link.startswith('sml.svc/'):
                        next_link = f"sml.svc/{next_link}"
                    url = f"{SL_URL}/b1s/v1/{next_link}"
            else:
                url = None
                
        consolidados = consolidar_por_folio(all_data)
        logger.info(f"Se obtuvieron {len(all_data)} líneas ({len(consolidados)} facturas únicas) de SAP HANA para {company_name}.")
        return consolidados
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener datos de Service Layer para {company_name}: {e}")
        return None

def load_to_sqlite(data):
    """Inserta o actualiza los registros en la base de datos local usando UPSERT."""
    if not data:
        logger.warning("No hay datos para procesar o la vista está vacía.")
        return False
        
    try:
        from datetime import datetime
        now_iso = datetime.now().isoformat()
        
        insert_query = '''
            INSERT INTO CxC_Local (
                Empresa, Folio_factura, Nombre_cliente, Nombre_extranjero, Fecha_documento,
                Proyecto, Impuestos, Retenciones, Total_factura, Importe_aplicado, Saldo_vencido, ultima_actualizacion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(Empresa, Folio_factura) DO UPDATE SET
                Nombre_cliente = excluded.Nombre_cliente,
                Nombre_extranjero = excluded.Nombre_extranjero,
                Fecha_documento = excluded.Fecha_documento,
                Proyecto = excluded.Proyecto,
                Impuestos = excluded.Impuestos,
                Retenciones = excluded.Retenciones,
                Total_factura = excluded.Total_factura,
                Importe_aplicado = excluded.Importe_aplicado,
                Saldo_vencido = excluded.Saldo_vencido,
                ultima_actualizacion = excluded.ultima_actualizacion
        '''
        
        records_to_insert = []
        for row in data:
            records_to_insert.append((
                row.get('Empresa'),
                row.get('Folio_factura') or row.get('Folio_de_la_factura'),
                row.get('Nombre_cliente') or row.get('Nombre_del_cliente'),
                row.get('Nombre_extranjero'),
                row.get('Fecha_documento') or row.get('Fecha_del_documento'),
                row.get('Proyecto'),
                row.get('Impuestos', 0.0),
                row.get('Retenciones', 0.0),
                row.get('Total_factura') if row.get('Total_factura') is not None else row.get('Total_de_la_factura', 0.0),
                row.get('Importe_aplicado', 0.0),
                row.get('Saldo_vencido', 0.0),
                now_iso
            ))
            
        with sqlite3.connect(DB_NAME, timeout=15.0) as conn:
            cursor = conn.cursor()
            cursor.executemany(insert_query, records_to_insert)
            conn.commit()
            
        logger.info(f"Se procesaron {len(records_to_insert)} registros correctamente mediante UPSERT en CxC_Local.")
        return True
    except Exception as e:
        logger.error(f"Error al cargar datos en SQLite: {e}")
        return False

def acumular_novedades(data_nueva):
    """
    Detecta facturas nuevas respecto a CxC_Snapshot_folios y las guarda en la tabla
    acumuladora cxc_movimientos_dia para enviarlas en un único resumen diario.
    """
    from datetime import datetime
    with sqlite3.connect(DB_NAME, timeout=15.0) as conn_snap:
        cursor = conn_snap.cursor()
        cursor.execute("SELECT empresa, folio FROM CxC_Snapshot_folios")
        old_set = set((str(r[0]), str(r[1])) for r in cursor.fetchall())
        logger.info(f"[NOTIF DEBUG] Snapshot anterior cargado: {len(old_set)} folios conocidos.")
    
    nuevos = []
    vistos = set()
    for row in data_nueva:
        emp = row.get('Empresa')
        fol = row.get('Folio_factura') or row.get('Folio_de_la_factura')
        if emp and fol:
            key = (str(emp), str(fol))
            if key not in old_set and key not in vistos:
                nuevos.append(row)
                vistos.add(key)
            
    if not nuevos:
        return 0
        
    ahora_iso = datetime.now().isoformat()
    registros_dia = []
    for r in nuevos:
        emp = str(r.get('Empresa'))
        fol = int(r.get('Folio_factura') or r.get('Folio_de_la_factura'))
        proy = (r.get('Proyecto') or 'Sin Proyecto').strip()
        cli = (r.get('Nombre_cliente') or r.get('Nombre_del_cliente') or 'Sin nombre').strip()
        tot = float(r.get('Total_factura') if r.get('Total_factura') is not None else (r.get('Total_de_la_factura') or 0.0))
        sal = float(r.get('Saldo_vencido') or 0.0)
        registros_dia.append((emp, fol, proy, cli, tot, sal, ahora_iso))

    with sqlite3.connect(DB_NAME, timeout=15.0) as conn:
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT OR IGNORE INTO cxc_movimientos_dia
            (empresa, folio, proyecto, cliente, monto, saldo, fecha_deteccion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', registros_dia)
        conn.commit()

    emp_str = ", ".join(sorted(set(r[0] for r in registros_dia)))
    logger.info(f"[NOTIF] Se acumularon {len(registros_dia)} nueva(s) factura(s) de [{emp_str}] en cxc_movimientos_dia.")
    return len(registros_dia)

def construir_mensaje_resumen(rows):
    """
    Construye un resumen diario compacto agrupado por Empresa y Obra (Proyecto),
    mostrando únicamente la obra y el monto (sin nombre de cliente ni detalles extensos).
    """
    from datetime import datetime
    if not rows:
        return None

    # rows: [(id, empresa, folio, proyecto, monto), ...]
    por_empresa = defaultdict(lambda: defaultdict(lambda: {"monto": 0.0, "cantidad": 0}))
    conteo_empresa = defaultdict(int)
    total_empresa = defaultdict(float)
    total_general = 0.0
    total_facturas = 0

    for _id, emp, _fol, proy, monto in rows:
        obra = (proy or "Sin Proyecto").strip()
        m = float(monto or 0.0)
        por_empresa[emp][obra]["monto"] += m
        por_empresa[emp][obra]["cantidad"] += 1
        conteo_empresa[emp] += 1
        total_empresa[emp] += m
        total_general += m
        total_facturas += 1

    fecha_str = datetime.now().strftime("%d/%b/%Y")
    msg = f"📊 *Resumen Diario de Nuevas Facturas*\n"
    msg += f"📅 {fecha_str}\n"
    msg += f"{'─' * 28}\n"

    for emp in sorted(por_empresa.keys()):
        emp_display = NOMBRES_DISPLAY.get(emp, emp)
        n_emp = conteo_empresa[emp]
        tot_emp = total_empresa[emp]
        etiqueta_fact = "factura" if n_emp == 1 else "facturas"
        msg += f"🏢 *{emp_display}* ({n_emp} {etiqueta_fact} | ${tot_emp:,.2f})\n"
        obras_dict = por_empresa[emp]
        for obra, info in obras_dict.items():
            cant = info["cantidad"]
            monto_obra = info["monto"]
            sufijo_cant = f" ({cant})" if cant > 1 else ""
            msg += f"• 🏗️ *Obra:* {obra}{sufijo_cant}\n"
            msg += f"  💰 *Monto:* ${monto_obra:,.2f}\n"
        msg += "\n"

    msg += f"{'─' * 28}\n"
    msg += f"*💵 Total del día ({total_facturas}): ${total_general:,.2f}*\n"
    msg += f"_Si necesitas consultar clientes, folios o más detalles, pregúntale al bot._\n"
    return msg

def actualizar_snapshot(data_nueva):
    if not data_nueva: return
    with sqlite3.connect(DB_NAME, timeout=15.0) as conn_snap:
        cursor = conn_snap.cursor()
        empresas_in_data = list(set(str(r.get('Empresa')) for r in data_nueva if r.get('Empresa')))
        if empresas_in_data:
            placeholders = ",".join(["?"] * len(empresas_in_data))
            cursor.execute(f"DELETE FROM CxC_Snapshot_folios WHERE empresa IN ({placeholders})", empresas_in_data)
        records = set()
        for row in data_nueva:
            emp = row.get('Empresa')
            fol = row.get('Folio_factura') or row.get('Folio_de_la_factura')
            if emp and fol:
                records.add((str(emp), str(fol)))
        cursor.executemany("INSERT INTO CxC_Snapshot_folios (empresa, folio) VALUES (?, ?)", list(records))

def enviar_broadcast(mensaje, conn):
    # NOTA: Para agregar un director hacer INSERT INTO notificacion_destinatarios
    # (tipo, destino, descripcion) VALUES ('whatsapp', '5214421234567@c.us', 'Director Finanzas')
    # IMPORTANTE: El destinatario debe haber chateado al menos una vez con este número de WA.
    cursor = conn.cursor()
    cursor.execute("SELECT destino, descripcion FROM notificacion_destinatarios WHERE activo = 1")
    targets = [{"destino": r[0], "descripcion": r[1] or ""} for r in cursor.fetchall()]
    if not targets:
        logger.warning("[NOTIF] No hay destinatarios activos en notificacion_destinatarios.")
        return

    import requests
    try:
        health_resp = requests.get("http://localhost:3001/health", timeout=3)
        if not health_resp.json().get('whatsapp_ready'):
            logger.error("[NOTIF] ❌ Node.js responde pero WhatsApp no está autenticado. Broadcast abortado.")
            raise requests.exceptions.ConnectionError("WhatsApp no listo")
        logger.info("[NOTIF] ✅ Node.js disponible y WhatsApp listo. Procediendo con broadcast.")
    except requests.exceptions.ConnectionError:
        logger.error("[NOTIF] ❌ Node.js no disponible en localhost:3001. Broadcast abortado.")
        raise requests.exceptions.ConnectionError("Node.js caído")

    logger.info(f"[NOTIF DEBUG] Enviando broadcast a {len(targets)} destinatario(s): {[t['destino'][:6] + '***' for t in targets]}")

    url = "http://localhost:3001/broadcast"
    payload = {"targets": targets, "message": mensaje}
    timeout_dinamico = 15 * len(targets) + 10
    resp = requests.post(url, json=payload, timeout=timeout_dinamico)

    if resp.status_code >= 400:
        raise requests.exceptions.HTTPError(f"Node.js respondió HTTP {resp.status_code}")

    # Inspeccionar resultados individuales — Node.js devuelve HTTP 200 incluso si WhatsApp
    # rechaza el mensaje (ej. "No LID for user" cuando el número nunca inició conversación)
    try:
        data = resp.json()
        results = data.get("results", [])
        enviados = [r for r in results if r.get("status") == "sent"]
        fallidos = [r for r in results if r.get("status") == "failed"]
        omitidos = [r for r in results if r.get("status") == "skipped"]

        for r in enviados:
            logger.info(f"[NOTIF] ✅ Mensaje entregado a {r['target'][:6]}***")
        for r in fallidos:
            logger.warning(f"[NOTIF] ⚠️  Fallo al entregar a {r['target'][:6]}*** | Error: {r.get('error','?')[:80]}")
            logger.warning("[NOTIF]    >> Si el error es 'No LID for user': ese número nunca ha escrito a esta cuenta WA. El destinatario debe enviar un mensaje primero para que puedas notificarle.")
        for r in omitidos:
            logger.info(f"[NOTIF] ⏭  Duplicado omitido para {r['target'][:6]}***")

        logger.info(f"[NOTIF] Resultado broadcast: {len(enviados)} enviados, {len(fallidos)} fallidos, {len(omitidos)} omitidos de {len(results)} total.")

        if results and len(enviados) == 0 and len(omitidos) == 0:
            raise requests.exceptions.HTTPError(
                f"Broadcast completamente fallido: {len(fallidos)} destinatario(s) con error. "
                f"Revisa el log para detalles. Los destinatarios deben haber chateado con este número al menos una vez."
            )
    except (ValueError, KeyError):
        # Si no viene JSON válido, simplemente loggear la respuesta cruda
        logger.warning(f"[NOTIF] Respuesta inesperada de Node.js: {resp.text[:200]}")

def procesar_resumen_diario():
    """
    Verifica si hay movimientos acumulados en cxc_movimientos_dia y si corresponde enviar
    el resumen diario:
    1) Al final del día laboral (hora >= HORA_RESUMEN_DIARIO y < 21) si aún no se envió hoy, O
    2) Al inicio del día siguiente (hora >= 8 y < 21) si quedaron movimientos rezagados de días anteriores.
    Tras enviar exitosamente el resumen por WhatsApp, limpia la tabla cxc_movimientos_dia.
    """
    from datetime import datetime
    ahora = datetime.now()
    hoy_str = ahora.strftime("%Y-%m-%d")
    hora_actual = ahora.hour

    if not (8 <= hora_actual < 21):
        logger.info("[NOTIF] Fuera de horario de envío (8 AM - 9 PM). Los movimientos siguen acumulándose.")
        return

    with sqlite3.connect(DB_NAME, timeout=15.0) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, empresa, folio, proyecto, monto, fecha_deteccion FROM cxc_movimientos_dia ORDER BY id ASC")
        movimientos = cursor.fetchall()

        if not movimientos:
            return

        cursor.execute("SELECT ultimo_resumen_fecha FROM etl_control WHERE id = 1")
        row_ctrl = cursor.fetchone()
        ultimo_resumen = row_ctrl[0] if row_ctrl and row_ctrl[0] else ""

        # Verificar si existen movimientos detectados en días anteriores a hoy
        hay_rezagados_dia_anterior = any(
            (m[5] or "")[:10] < hoy_str for m in movimientos if m[5]
        )
        es_hora_corte_diario = (hora_actual >= HORA_RESUMEN_DIARIO and ultimo_resumen != hoy_str)

        if not (hay_rezagados_dia_anterior or es_hora_corte_diario):
            logger.info(
                f"[NOTIF] {len(movimientos)} factura(s) acumulada(s) para el resumen de hoy "
                f"(se enviará a partir de las {HORA_RESUMEN_DIARIO:02d}:00 hrs)."
            )
            return

        rows_para_mensaje = [(m[0], m[1], m[2], m[3], m[4]) for m in movimientos]
        max_id = max(m[0] for m in movimientos)
        mensaje = construir_mensaje_resumen(rows_para_mensaje)

        if not mensaje:
            return

        try:
            logger.info(f"[NOTIF] Enviando resumen diario con {len(movimientos)} movimiento(s)...")
            enviar_broadcast(mensaje, conn)
            # Limpiar la tabla de movimientos acumulados para el día siguiente
            cursor.execute("DELETE FROM cxc_movimientos_dia WHERE id <= ?", (max_id,))
            if es_hora_corte_diario:
                cursor.execute("UPDATE etl_control SET ultimo_resumen_fecha = ? WHERE id = 1", (hoy_str,))
            conn.commit()
            logger.info(f"[NOTIF] ✅ Resumen diario enviado y tabla cxc_movimientos_dia limpiada ({len(movimientos)} registros depurados).")
        except Exception as e:
            logger.warning(f"[NOTIF] ⚠️ No se pudo enviar el resumen diario todavía (se conservarán los datos para reintentar): {e}")

def etl_job():
    try:
        """Función que orquesta el flujo ETL para múltiples empresas."""
        logger.info("--- Iniciando ejecución del proceso ETL Multibase ---")

        if not SAP_COMPANIES:
            logger.error("No hay empresas configuradas en la variable SAP_COMPANIES.")
            return

        with sqlite3.connect(DB_NAME, timeout=15.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT primer_arranque_completado FROM etl_control WHERE id = 1")
            row = cursor.fetchone()
            primer_arranque = row[0] if row else 0

        logger.info(f"[NOTIF] Estado primer_arranque={primer_arranque}. {'Detección activa (acumulación diaria).' if primer_arranque else 'Detección DESACTIVADA — primer arranque pendiente.'}")

        empresas = [e.strip() for e in SAP_COMPANIES.split(',')]
        empresas_exitosas = 0

        for empresa in empresas:
            logger.info(f"Procesando empresa: {empresa}")

            from datetime import datetime
            import time
            start_time = time.time()

            session = sl_login(empresa)
            if not session:
                logger.error(f"Omitiendo empresa {empresa} por fallo de login.")
                try:
                    with sqlite3.connect(DB_NAME, timeout=15.0) as conn_hist:
                        conn_hist.execute("INSERT INTO etl_historial (timestamp, empresa, exito, error_msg) VALUES (?, ?, 0, ?)", 
                                          (datetime.now().isoformat(), empresa, "Fallo de login"))
                except Exception: pass
                continue

            try:
                cxc_data = fetch_cxc_data(session, empresa)
                if not cxc_data:
                    logger.warning(f"Sin datos en SAP para {empresa}.")
                    continue

                # PASO 1: Detectar novedades y acumularlas en cxc_movimientos_dia
                registros_nuevos = 0
                if primer_arranque == 1:
                    try:
                        registros_nuevos = acumular_novedades(cxc_data)
                    except Exception as e:
                        logger.warning(f"Error al acumular novedades para {empresa}: {e}")
                else:
                    logger.info(f"[NOTIF] {empresa}: Primer arranque pendiente — detección de novedades DESACTIVADA")

                registros_sap = len(cxc_data)
                registros_actualizados = registros_sap - registros_nuevos

                # PASO 2: UPSERT a base de datos
                exito = load_to_sqlite(cxc_data)

                # PASO 3: Guardar el nuevo snapshot
                if exito:
                    empresas_exitosas += 1
                    actualizar_snapshot(cxc_data)

                    # Insertar en etl_historial
                    duracion = time.time() - start_time
                    with sqlite3.connect(DB_NAME, timeout=15.0) as conn_hist:
                        conn_hist.execute('''INSERT INTO etl_historial 
                            (timestamp, empresa, registros_sap, registros_nuevos, registros_actualizados, duracion_segundos, exito) 
                            VALUES (?, ?, ?, ?, ?, ?, 1)''', 
                            (datetime.now().isoformat(), empresa, registros_sap, registros_nuevos, registros_actualizados, duracion))

            except Exception as emp_err:
                logger.error(f"Error general en ETL para {empresa}: {emp_err}")
                try:
                    with sqlite3.connect(DB_NAME, timeout=15.0) as conn_hist:
                        conn_hist.execute("INSERT INTO etl_historial (timestamp, empresa, exito, error_msg) VALUES (?, ?, 0, ?)", 
                                          (datetime.now().isoformat(), empresa, str(emp_err)))
                except Exception: pass
            finally:
                sl_logout(session)

        if primer_arranque == 0 and empresas_exitosas > 0:
            with sqlite3.connect(DB_NAME, timeout=15.0) as conn:
                conn.execute("UPDATE etl_control SET primer_arranque_completado = 1 WHERE id = 1")
                conn.commit()
            logger.info("Primer arranque completado. Snapshot base guardado para futuras comparaciones.")

        # PASO 4: Evaluar si corresponde enviar el Resumen Diario y limpiar cxc_movimientos_dia
        try:
            procesar_resumen_diario()
        except Exception as e:
            logger.warning(f"Error procesando resumen diario: {e}")

        logger.info("--- Proceso ETL Multibase finalizado ---")

    except Exception as e:
        logger.exception(f"Error crítico en el orquestador ETL: {e}")

if __name__ == "__main__":
    # Suprimir warnings de InsecureRequestWarning si se usa HTTPS sin certificado verificado
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    logger.info("Arrancando el servicio ETL CxC Bot IA Multibase...")
    
    init_db()
    
    # Ejecutar la primera vez inmediatamente al arrancar
    etl_job()
    
    # Programar la ejecución del ETL cada 30 minutos
    schedule.every(30).minutes.do(etl_job)
    # Programar chequeos puntuales del resumen diario al inicio y final del día
    schedule.every().day.at("08:00").do(procesar_resumen_diario)
    schedule.every().day.at(f"{HORA_RESUMEN_DIARIO:02d}:00").do(procesar_resumen_diario)
    logger.info(f"Proceso ETL programado cada 30 min. Resumen diario programado a las {HORA_RESUMEN_DIARIO:02d}:00 hrs (y 08:00 hrs para rezagados).")
    
    # Bucle infinito
    while True:
        schedule.run_pending()
        time.sleep(1)
