import sqlite3
import pandas as pd
from pathlib import Path

# Ruta correcta a la base de datos del Data Mart
DM_PATH = Path("sqlite") / "data_mart_ventas.sqlite"

if not DM_PATH.exists():
    raise FileNotFoundError(
        "No existe data_mart_ventas.sqlite. Ejecuta primero el Ejercicio 2 (Data Mark)"
    )

dm_conn = sqlite3.connect(DM_PATH)
print("OK -> Conectado a:", DM_PATH)

pd.read_sql_query("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name;
""", dm_conn)

cur = dm_conn.cursor()

cur.execute("DROP TABLE IF EXISTS olap_cubo_ventas;")

cur.execute("""
CREATE TABLE olap_cubo_ventas AS
SELECT
    t.anio,
    t.mes,
    c.categoria,
    SUM(f.total_ventas) AS ventas_totales,
    COUNT(*) AS num_registros
FROM fact_ventas_dm f
JOIN dim_tiempo_dm t ON t.tiempo_id = f.tiempo_id
JOIN dim_categoria c ON c.categoria_id = f.categoria_id
GROUP BY
    t.anio, t.mes, c.categoria;
""")
dm_conn.commit()
print("OK -> Cubo OLAP creado: olap_cubo_ventas")

cur.execute("CREATE INDEX IF NOT EXISTS idx_cubo_anio_mes ON olap_cubo_ventas(anio, mes)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_cubo_categoria ON olap_cubo_ventas(categoria)")
dm_conn.commit()
print("Índices creados.")

pd.read_sql_query("""
SELECT COUNT(*) AS filas_cubo
FROM olap_cubo_ventas;
""", dm_conn)

pd.read_sql_query("""
SELECT
    anio,
    SUM(ventas_totales) AS ventas_anuales
FROM olap_cubo_ventas
GROUP BY anio
ORDER BY anio;
""", dm_conn)

pd.read_sql_query("""
SELECT
    anio,
    mes,
    SUM(ventas_totales) AS ventas_mensuales
FROM olap_cubo_ventas
GROUP BY anio, mes
ORDER BY anio, mes;
""", dm_conn)

pd.read_sql_query("""
SELECT *
FROM olap_cubo_ventas
WHERE anio = 2024
ORDER BY mes, categoria;
""", dm_conn)

pd.read_sql_query("""
SELECT *
FROM olap_cubo_ventas
WHERE anio = 2024
  AND mes BETWEEN 1 AND 6
  AND categoria IN ('electronica', 'papeleria')
ORDER BY mes, categoria;
""", dm_conn)

df_cubo = pd.read_sql_query("""
SELECT anio, mes, categoria, ventas_totales
FROM olap_cubo_ventas
WHERE anio = 2024;
""", dm_conn)

pivot = df_cubo.pivot_table(
    index="mes",
    columns="categoria",
    values="ventas_totales",
    aggfunc="sum",
    fill_value=0
).sort_index()
print(pivot)

dm_conn.close()
print("Conexión cerrada.")