import sqlite3
import pandas as pd

conn = sqlite3.connect('bot_ia.db')
df = pd.read_sql_query('SELECT * FROM CxC_Local', conn)

print("Total registros:", len(df))
print("Fechas max/min:", df['Fecha_documento'].min(), "-", df['Fecha_documento'].max())
print("Empresas:", df['Empresa'].unique())
print("Top clientes:", df['Nombre_cliente'].value_counts().head(5).to_dict())

df['Mes'] = pd.to_datetime(df['Fecha_documento']).dt.to_period('M')
meses_ersa = df[df['Empresa'].str.contains('ERSA', case=False, na=False)].groupby('Mes')['Total_factura'].sum()
print("\n--- Facturacion ERSA Ultimos Meses ---")
print(meses_ersa.tail())

print("\n--- Deuda Costco ---")
costco = df[df['Nombre_cliente'].str.contains('Costco', case=False, na=False)]
print("Costco Deuda total:", costco['Saldo_vencido'].sum())

print("\n--- Factura mas alta ERSA ---")
ersa = df[df['Empresa'].str.contains('ERSA', case=False, na=False)]
if not ersa.empty:
    top = ersa.loc[ersa['Total_factura'].idxmax()]
    print("Top ERSA: Folio", top['Folio_factura'], "Total:", top['Total_factura'])

print("\n--- Cartera Vencida Global ---")
print("Total Cartera (Saldo_vencido):", df['Saldo_vencido'].sum())

conn.close()
