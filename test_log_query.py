import sqlite3

conn = sqlite3.connect('bot_ia.db')
cur = conn.cursor()

sql = "SELECT COUNT(Folio_factura) AS total FROM CxC_Local WHERE COALESCE(Nombre_cliente, Nombre_extranjero, '') LIKE ? AND CAST(Saldo_vencido AS REAL) < 0"
params = ['%MUNICIPIO DE QUERETARO%']

cur.execute(sql, params)
print(cur.fetchone())
conn.close()
