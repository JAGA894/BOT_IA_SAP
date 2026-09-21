import os
import re
import time
import sqlite3
import logging
import requests
import schedule
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

def init_db():
    """Inicializa la base de datos y crea la tabla si no existe."""
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
                ultimo_etl_exitoso TEXT
            )
        ''')
        
        # Inicializar fila de control si no existe
        cursor.execute("INSERT OR IGNORE INTO etl_control (id, primer_arranque_completado) VALUES (1, 0)")
        
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
        logger.info("Base de datos y tabla inicializadas correctamente.")
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
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"Error HTTP al obtener datos para {company_name}: {e}")
                break
                
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
                
        logger.info(f"Se obtuvieron {len(all_data)} registros de SAP HANA para {company_name}.")
        return all_data
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

def detectar_novedades(data_nueva):
    from datetime import datetime, timedelta
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
        return None, 0
        
    total_monto = sum(float(r.get('Total_factura') or r.get('Total_de_la_factura') or 0.0) for r in nuevos)
    empresa_nombres = ", ".join(list(set(r.get('Empresa') for r in nuevos)))
    inicio_hora = (datetime.now() - timedelta(minutes=15)).strftime("%H:%M")
    fin_hora = datetime.now().strftime("%H:%M")
    
    fecha_hoy = datetime.now().strftime("%d/%b/%Y")
    msg = f"🔔 *Nueva(s) Factura(s) Detectada(s)*\n"
    msg += f"📅 {fecha_hoy} | Ciclo {inicio_hora}→{fin_hora}\n"
    msg += f"🏢 Empresa(s): {empresa_nombres}\n"
    msg += f"{'─' * 28}\n"
    for r in nuevos[:10]:
        fol = r.get('Folio_factura') or r.get('Folio_de_la_factura')
        cli = (r.get('Nombre_cliente') or r.get('Nombre_del_cliente') or r.get('Proyecto') or 'Sin nombre')[:20]
        tot = float(r.get('Total_factura') or r.get('Total_de_la_factura') or 0.0)
        saldo = float(r.get('Saldo_vencido') or 0.0)
        estado = "✅ Pagada" if saldo <= 0 else "🔴 Pendiente"
        msg += f"• *Folio {fol}* — {cli}\n"
        msg += f"  💰 ${tot:,.2f} | {estado}\n"
    if len(nuevos) > 10:
        msg += f"\n_...y {len(nuevos) - 10} más. Consulta el bot para el listado completo._\n"
    msg += f"{'─' * 28}\n"
    msg += f"*💵 Total emitido: ${total_monto:,.2f}*\n"
    msg += f"_Responde al bot con tu empresa para consultar detalles_"
    return msg, len(nuevos)

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

def procesar_notificaciones(mensaje_nuevo=None):
    from datetime import datetime
    with sqlite3.connect(DB_NAME, timeout=15.0) as conn:
        cursor = conn.cursor()
        
        if mensaje_nuevo:
            hora_actual = datetime.now().hour
            enviar_desde = None if 7 <= hora_actual < 21 else "fuera_horario"
            cursor.execute("INSERT INTO notificaciones_pendientes (mensaje, enviar_desde) VALUES (?, ?)", (mensaje_nuevo, enviar_desde))
            conn.commit()
            
        hora_actual = datetime.now().hour
        if 7 <= hora_actual < 21:
            cursor.execute("SELECT id, mensaje FROM notificaciones_pendientes WHERE enviado = 0")
            pendientes = cursor.fetchall()
            for pid, msg in pendientes:
                try:
                    enviar_broadcast(msg, conn)
                    try:
                        cursor.execute("UPDATE notificaciones_pendientes SET enviado = 1 WHERE id = ?", (pid,))
                        conn.commit()
                    except Exception as upd_err:
                        logger.error(f"Error crítico: Broadcast enviado pero no se pudo marcar como enviado (pid={pid}): {upd_err}")
                except Exception as e:
                    logger.warning(f"Fallo al enviar notificación {pid}, se reintentará luego: {e}")
        else:
            logger.info("Fuera de ventana horaria (7AM - 9PM), notificaciones en pausa.")

def etl_job():
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
    
    logger.info(f"[NOTIF] Estado primer_arranque={primer_arranque}. {'Detección activa.' if primer_arranque else 'Detección DESACTIVADA — primer arranque pendiente.'}")
        
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
                
            # PASO 1: Detectar novedades (diferencial vs snapshot)
            mensaje_novedades = None
            registros_nuevos = 0
            if primer_arranque == 1:
                mensaje_novedades, registros_nuevos = detectar_novedades(cxc_data)
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
                
            # PASO 4: Enviar notificaciones si las hay
            if mensaje_novedades:
                try:
                    procesar_notificaciones(mensaje_novedades)
                except Exception as e:
                    logger.warning(f"Error aislado en el sistema de notificaciones para {empresa}: {e}")
                    
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
    
    # PASO 5: Forzar purga de notificaciones pendientes de horarios nocturnos
    try:
        procesar_notificaciones()
    except Exception as e:
        logger.warning(f"Error purgando notificaciones atrasadas: {e}")
        
    logger.info("--- Proceso ETL Multibase finalizado ---")

if __name__ == "__main__":
    # Suprimir warnings de InsecureRequestWarning si se usa HTTPS sin certificado verificado
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    logger.info("Arrancando el servicio ETL CxC Bot IA Multibase...")
    
    init_db()
    
    # Ejecutar la primera vez inmediatamente al arrancar
    etl_job()
    
    # Programar la ejecución cada 30 minutos
    schedule.every(30).minutes.do(etl_job)
    logger.info("Proceso programado para ejecutarse cada 30 minutos ininterrumpidamente.")
    
    # Bucle infinito
    while True:
        schedule.run_pending()
        time.sleep(1)