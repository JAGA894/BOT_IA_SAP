import sqlite3
import unicodedata

def normalize_text(texto: str) -> str:
    if not texto:
        return texto
    t = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return t.upper()

def test_query(term):
    conn = sqlite3.connect('bot_ia.db')
    cur = conn.cursor()
    limpio = normalize_text(term)
    print(f"\n--- Probando: {term} (Normalizado: {limpio}) ---")
    
    cur.execute("SELECT COUNT(*) FROM CxC_Local WHERE COALESCE(Nombre_cliente, Nombre_extranjero, '') LIKE ?", (f"%{limpio}%",))
    print("Matches cliente/ext:", cur.fetchone()[0])
    
    cur.execute("SELECT COUNT(*) FROM CxC_Local WHERE COALESCE(Proyecto, '') LIKE ?", (f"%{limpio}%",))
    print("Matches proyecto:", cur.fetchone()[0])
    
    # Pruebas con métricas numéricas
    cur.execute("SELECT COALESCE(SUM(COALESCE(Saldo_vencido, 0)), 0) FROM CxC_Local WHERE COALESCE(Nombre_cliente, Nombre_extranjero, '') LIKE ?", (f"%{limpio}%",))
    print("Total cxc cliente/ext:", cur.fetchone()[0])

    conn.close()

if __name__ == '__main__':
    test_query("Querétaro")
