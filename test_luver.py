import sqlite3
conn = sqlite3.connect('bot_ia.db')
cur = conn.cursor()
cur.execute("SELECT Total_factura, Saldo_vencido, Fecha_documento FROM CxC_Local WHERE Nombre_extranjero LIKE '%LUVER%'")
print(cur.fetchall())
conn.close()
