import sqlite3
conn = sqlite3.connect('bot_ia.db')
cursor = conn.cursor()

cursor.execute("SELECT Folio_factura, Total_factura, Fecha_documento FROM CxC_Local WHERE Empresa LIKE '%ERSA%' AND Fecha_documento LIKE '2026%' ORDER BY Total_factura DESC LIMIT 1")
print("\n--- Factura mas alta ERSA 2026 ---")
print(cursor.fetchone())

conn.close()
