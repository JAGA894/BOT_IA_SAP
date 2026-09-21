import sqlite3
conn = sqlite3.connect('bot_ia.db')
cursor = conn.cursor()

cursor.execute("SELECT MIN(Fecha_documento), MAX(Fecha_documento) FROM CxC_Local")
print("Fechas max/min:", cursor.fetchone())

cursor.execute("SELECT DISTINCT Empresa FROM CxC_Local")
print("Empresas:", [r[0] for r in cursor.fetchall()])

cursor.execute("SELECT Nombre_cliente, COUNT(*) as c FROM CxC_Local GROUP BY Nombre_cliente ORDER BY c DESC LIMIT 5")
print("Top clientes:", cursor.fetchall())

cursor.execute("SELECT strftime('%Y-%m', Fecha_documento) as Mes, SUM(Total_factura) FROM CxC_Local WHERE Empresa LIKE '%ERSA%' GROUP BY Mes ORDER BY Mes DESC LIMIT 5")
print("\n--- Facturacion ERSA Ultimos Meses ---")
for r in cursor.fetchall(): print(r)

cursor.execute("SELECT SUM(Saldo_vencido) FROM CxC_Local WHERE Nombre_cliente LIKE '%Costco%'")
print("\n--- Deuda Costco ---")
print(cursor.fetchone()[0])

cursor.execute("SELECT Folio_factura, Total_factura FROM CxC_Local WHERE Empresa LIKE '%ERSA%' ORDER BY Total_factura DESC LIMIT 1")
print("\n--- Factura mas alta ERSA ---")
print(cursor.fetchone())

cursor.execute("SELECT SUM(Saldo_vencido) FROM CxC_Local")
print("\n--- Cartera Vencida Global ---")
print(cursor.fetchone()[0])

conn.close()
