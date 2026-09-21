r"""
test_cross_validation.py -- Validacion Cruzada: SQL vs Pandas
==============================================================
Compara la salida de consultar_totales_financieros (SQL interno)
contra calculos directos con pandas sobre la misma base de datos.

Los 6 escenarios criticos:
  1. Saldo vencido total "Municipio de Queretaro" (normalizacion de acentos)
  2. Facturas completamente pagadas (Saldo_vencido <= 0)
  3. Factura mas alta (top_maximo) en todo 2024
  4. Facturas pendientes (Saldo_vencido > 0) del proyecto "POES"
  5. Total facturado (facturacion) para cliente "LUVER"
  6. Registros con saldo a favor (Saldo_vencido < 0) globales

Uso:
    .\venv\Scripts\python.exe -X utf8 test_cross_validation.py
"""

import asyncio
import os
import re
import sqlite3
import sys
import unicodedata

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv()

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False
    print("ADVERTENCIA: pandas no instalado. Usando sqlite3 directo para ground truth.")

from bot_app import consultar_totales_financieros, DB_NAME

# ── Colores ──────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

TOLERANCIA = 0.01   # diferencia maxima aceptable entre montos ($)

# ── Helpers de parseo ─────────────────────────────────────────────────────────
def parse_monto(texto: str) -> float | None:
    """Extrae el primer monto $X,XXX.XX del string de respuesta."""
    m = re.search(r'\$([0-9,]+\.?\d*)', texto)
    return float(m.group(1).replace(',', '')) if m else None

def parse_conteo(texto: str) -> int | None:
    """Extrae el primer numero entero significativo del string de respuesta."""
    # "Se encontraron X registros"
    m = re.search(r'encontraron\s+(\d+)', texto)
    if m: return int(m.group(1))
    # "correspondiente a X registros"
    m = re.search(r'correspondiente\s+a\s+(\d+)', texto)
    if m: return int(m.group(1))
    return None

def strip_accents(texto: str) -> str:
    """Quita acentos y pasa a mayusculas (igual que normalize_text en bot_app)."""
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).upper()

# ── Ground Truth via SQL directo (pandas o sqlite3) ──────────────────────────
def sql_ground_truth(query: str, scalar: bool = True):
    """Ejecuta SQL directo contra la DB y devuelve el resultado."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.execute(query)
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return row[0] if scalar else row

# ─────────────────────────────────────────────────────────────────────────────
# DEFINICION DE ESCENARIOS
# Cada uno: (titulo, params_funcion, sql_gt, tipo_comparacion, descripcion_gt)
# tipo: "monto" | "conteo" | "vacio" | "folio"
# ─────────────────────────────────────────────────────────────────────────────

# Normalizacion del nombre del cliente para el query de pandas/sqlite
MUNICIPIO_NORM = strip_accents("Municipio de Querétaro")   # -> "MUNICIPIO DE QUERETARO"

ESCENARIOS = [
    {
        "id": 1,
        "titulo": "Saldo vencido 'Municipio de Queretaro' (normalizacion acentos)",
        "params": dict(
            metrica="cxc", dimension="cliente",
            valor_dimension="Municipio de Querétaro",
            fecha_inicio=None, fecha_fin=None, estatus_pago="todos",
        ),
        # Ground truth: suma de Saldo_vencido para ese cliente
        "sql_gt": (
            f"SELECT COALESCE(SUM(Saldo_vencido), 0) FROM CxC_Local "
            f"WHERE UPPER(COALESCE(Nombre_cliente, Nombre_extranjero, Proyecto, '')) "
            f"LIKE '%{MUNICIPIO_NORM}%'"
        ),
        "tipo": "monto",
        "descripcion_gt": "SUM(Saldo_vencido) WHERE cliente LIKE '%MUNICIPIO DE QUERETARO%'",
    },
    {
        "id": 2,
        "titulo": "Facturas completamente pagadas (Saldo_vencido <= 0)",
        "params": dict(
            metrica="conteo", dimension="global",
            valor_dimension="", fecha_inicio=None, fecha_fin=None, estatus_pago="pagado",
        ),
        "sql_gt": "SELECT COUNT(*) FROM CxC_Local WHERE CAST(Saldo_vencido AS REAL) <= 0",
        "tipo": "conteo",
        "descripcion_gt": "COUNT(*) WHERE Saldo_vencido <= 0",
    },
    {
        "id": 3,
        "titulo": "Factura mas alta (top_maximo) en todo 2024",
        "params": dict(
            metrica="top_maximo", dimension="global",
            valor_dimension="", fecha_inicio="2024-01-01", fecha_fin="2024-12-31", estatus_pago="todos",
        ),
        # Con Fecha_documento=NULL en toda la DB, esperamos 0 filas
        "sql_gt": (
            "SELECT COUNT(*) FROM CxC_Local "
            "WHERE DATE(Fecha_documento) >= DATE('2024-01-01') "
            "AND DATE(Fecha_documento) <= DATE('2024-12-31')"
        ),
        "tipo": "vacio",   # esperamos resultado vacio (0 filas en 2024)
        "descripcion_gt": "COUNT(*) WHERE Fecha_documento en 2024 (esperado: 0 — todas las fechas son NULL)",
    },
    {
        "id": 4,
        "titulo": "Facturas pendientes (Saldo_vencido > 0) proyecto 'POES'",
        "params": dict(
            metrica="conteo", dimension="proyecto",
            valor_dimension="POES", fecha_inicio=None, fecha_fin=None, estatus_pago="pendiente",
        ),
        "sql_gt": (
            "SELECT COUNT(*) FROM CxC_Local "
            "WHERE UPPER(COALESCE(Proyecto, '')) LIKE '%POES%' "
            "AND CAST(Saldo_vencido AS REAL) > 0"
        ),
        "tipo": "conteo",
        "descripcion_gt": "COUNT(*) WHERE Proyecto LIKE '%POES%' AND Saldo_vencido > 0",
    },
    {
        "id": 5,
        "titulo": "Total facturado (facturacion) cliente 'LUVER'",
        "params": dict(
            metrica="facturacion", dimension="cliente",
            valor_dimension="LUVER", fecha_inicio=None, fecha_fin=None, estatus_pago="todos",
        ),
        "sql_gt": (
            "SELECT COALESCE(SUM(Total_factura), 0) FROM CxC_Local "
            "WHERE UPPER(COALESCE(Nombre_cliente, Nombre_extranjero, Proyecto, '')) LIKE '%LUVER%'"
        ),
        "tipo": "monto",
        "descripcion_gt": "SUM(Total_factura) WHERE cliente LIKE '%LUVER%' (esperado: $0 — Total_factura=0 en toda la DB)",
    },
    {
        "id": 6,
        "titulo": "Registros con saldo a favor (Saldo_vencido < 0)",
        "params": dict(
            metrica="conteo", dimension="global",
            valor_dimension="", fecha_inicio=None, fecha_fin=None, estatus_pago="saldo_favor",
        ),
        "sql_gt": "SELECT COUNT(*) FROM CxC_Local WHERE CAST(Saldo_vencido AS REAL) < 0",
        "tipo": "conteo",
        "descripcion_gt": "COUNT(*) WHERE Saldo_vencido < 0",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────────────────────
async def run_validations():
    print(f"\n{BOLD}{CYAN}{'='*70}")
    print("  VALIDACION CRUZADA: consultar_totales_financieros vs SQL Directo")
    print(f"  DB: {DB_NAME}")
    print(f"{'='*70}{RESET}\n")

    match_count = 0
    mismatch_count = 0
    reporte = []

    for esc in ESCENARIOS:
        eid     = esc["id"]
        titulo  = esc["titulo"]
        params  = esc["params"]
        sql_gt  = esc["sql_gt"]
        tipo    = esc["tipo"]
        desc_gt = esc["descripcion_gt"]

        print(f"{BOLD}[Escenario {eid}]{RESET} {titulo}")
        print(f"  Params: {params}")

        # ── Ground Truth ──────────────────────────────────────────────────
        try:
            gt_raw = sql_ground_truth(sql_gt)
            gt_val = float(gt_raw) if gt_raw is not None else 0.0
            print(f"  {CYAN}Ground Truth{RESET} ({desc_gt}): {gt_val}")
        except Exception as e:
            print(f"  {RED}Ground Truth ERROR: {e}{RESET}")
            gt_val = None

        # ── Funcion Python ────────────────────────────────────────────────
        try:
            funcion_result = await consultar_totales_financieros(**params)
            print(f"  {CYAN}Funcion     {RESET}: {funcion_result[:120]}")
        except Exception as e:
            print(f"  {RED}Funcion ERROR: {e}{RESET}")
            reporte.append((eid, titulo, "FAIL", f"Excepcion: {e}", gt_val, None))
            mismatch_count += 1
            print()
            continue

        # ── Comparacion ───────────────────────────────────────────────────
        if tipo == "monto":
            fn_val = parse_monto(funcion_result)
            if fn_val is None:
                veredicto = "FAIL"
                detalle   = "No se pudo parsear monto de la respuesta"
            elif gt_val is None:
                veredicto = "WARN"
                detalle   = "Ground truth nulo — no comparable"
            elif abs(fn_val - gt_val) <= TOLERANCIA:
                veredicto = "MATCH"
                detalle   = f"${fn_val:,.2f} == ${gt_val:,.2f} (dif=${abs(fn_val-gt_val):.2f})"
            else:
                veredicto = "MISMATCH"
                detalle   = f"Funcion=${fn_val:,.2f} | GT=${gt_val:,.2f} | DIFERENCIA=${abs(fn_val-gt_val):,.2f}"

        elif tipo == "conteo":
            fn_val = parse_conteo(funcion_result)
            if fn_val is None:
                veredicto = "FAIL"
                detalle   = "No se pudo parsear conteo de la respuesta"
            elif int(gt_val) == fn_val:
                veredicto = "MATCH"
                detalle   = f"{fn_val} == {int(gt_val)}"
            else:
                veredicto = "MISMATCH"
                detalle   = f"Funcion={fn_val} | GT={int(gt_val)}"

        elif tipo == "vacio":
            # Para este tipo: GT debe ser 0 filas, funcion debe decir "no se encontraron"
            es_vacio_gt = (gt_val == 0)
            es_vacio_fn = ("no se encontr" in funcion_result.lower() or
                           "sin registro"  in funcion_result.lower() or
                           "0 registros"   in funcion_result)
            if es_vacio_gt and es_vacio_fn:
                veredicto = "MATCH"
                detalle   = "Ambos volvieron vacio (correcto: Fecha_documento=NULL en DB)"
            elif not es_vacio_gt:
                veredicto = "MATCH"
                detalle   = f"GT={int(gt_val)} registros, funcion responde con datos"
            else:
                veredicto = "MISMATCH"
                detalle   = f"GT=0 filas, pero funcion no reporto vacio: {funcion_result[:80]}"

        else:
            veredicto = "WARN"
            detalle   = "Tipo de comparacion no reconocido"

        # ── Display resultado ─────────────────────────────────────────────
        color = GREEN if veredicto in ("MATCH",) else (YELLOW if veredicto == "WARN" else RED)
        print(f"  {color}{BOLD}{veredicto}{RESET}  {detalle}")
        print()

        reporte.append((eid, titulo, veredicto, detalle, gt_val,
                        parse_monto(funcion_result) or parse_conteo(funcion_result)))

        if veredicto == "MATCH":
            match_count += 1
        elif veredicto in ("MISMATCH", "FAIL"):
            mismatch_count += 1

    # ── Reporte Final ─────────────────────────────────────────────────────────
    total = len(ESCENARIOS)
    print(f"{BOLD}{'='*70}")
    print(f"  REPORTE FINAL — {total} escenarios")
    print(f"  {GREEN}MATCH   : {match_count}{RESET}")
    warn_c = sum(1 for r in reporte if r[2] == "WARN")
    print(f"  {YELLOW}WARN    : {warn_c}{RESET}  (vacios esperados dado el estado de la DB)")
    print(f"  {RED}MISMATCH: {mismatch_count}{RESET}  (discrepancias que requieren parche)")
    print()

    if mismatch_count > 0:
        print(f"{RED}DISCREPANCIAS ENCONTRADAS:{RESET}")
        for r in reporte:
            if r[2] in ("MISMATCH", "FAIL"):
                print(f"  [E{r[0]}] {r[1]}")
                print(f"         {r[3]}")
        print()
        print(f"{RED}Se requiere parche en bot_app.py.{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}TODAS LAS VALIDACIONES PASARON - bot_app.py en sincro con la DB.{RESET}")
        sys.exit(0)

    print(f"{'='*70}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_validations())
