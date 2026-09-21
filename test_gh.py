import sqlite3
conn = sqlite3.connect('bot_ia.db')
cur = conn.cursor()
cur.execute("SELECT DISTINCT Nombre_extranjero FROM CxC_Local WHERE Nombre_extranjero LIKE '%EDIFICACIONES%' OR Nombre_extranjero LIKE '%GH%'")
print(cur.fetchall())
