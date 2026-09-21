import sqlite3
conn = sqlite3.connect('bot_ia.db')
conn.cursor().execute("INSERT INTO notificaciones_pendientes (mensaje, enviar_desde) VALUES ('Prueba con isRegisteredUser!', NULL)")
conn.commit()
