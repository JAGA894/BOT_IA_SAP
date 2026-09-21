import sqlite3
conn = sqlite3.connect('bot_ia.db')
cur = conn.cursor()
cur.execute("SELECT Folio_factura FROM CxC_Local WHERE Nombre_extranjero LIKE '%QUERETARO%'")
print(cur.fetchall())
conn.close()
