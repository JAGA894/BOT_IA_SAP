import sqlite3
conn = sqlite3.connect('bot_ia.db')
cursor = conn.cursor()

# 1. Cobro Q1 2026 ERSA
cursor.execute("SELECT SUM(Importe_aplicado) FROM CxC_Local WHERE Empresa LIKE '%ERSA%' AND Fecha_documento BETWEEN '2026-01-01' AND '2026-03-31'")
print("Cobro Q1 ERSA:", cursor.fetchone()[0])

# 2. Factura 1217 ERSA
cursor.execute("SELECT Total_factura, Saldo_vencido, Nombre_cliente FROM CxC_Local WHERE Empresa LIKE '%ERSA%' AND Folio_factura = 1217")
print("Factura 1217 ERSA:", cursor.fetchone())

# 3. Saldo a favor ERSA
cursor.execute("SELECT SUM(Saldo_vencido) FROM CxC_Local WHERE Empresa LIKE '%ERSA%' AND Saldo_vencido < 0")
print("Saldo a favor ERSA:", cursor.fetchone()[0])

# 4. Conteo 2025 ERSA
cursor.execute("SELECT COUNT(*) FROM CxC_Local WHERE Empresa LIKE '%ERSA%' AND Fecha_documento LIKE '2025%'")
print("Conteo 2025 ERSA:", cursor.fetchone()[0])

# 5. Proyecto Aero ERSA
cursor.execute("SELECT SUM(Total_factura) FROM CxC_Local WHERE Empresa LIKE '%ERSA%' AND Proyecto LIKE '%AEROESPACIAL%'")
print("Facturacion Proyecto Aero:", cursor.fetchone()[0])

conn.close()
