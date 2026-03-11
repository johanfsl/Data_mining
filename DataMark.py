import datawerehouse as dw
import sqlite3
import pandas as pd
from pathlib import Path


# CARPETAS DEL PROYECTO
CSV_DIR = Path("csv")
SQLITE_DIR = Path("sqlite")

# Crear carpetas si no existen
CSV_DIR.mkdir(exist_ok=True)
SQLITE_DIR.mkdir(exist_ok=True)

# RUTAS
DW_PATH = SQLITE_DIR / "dw.sqlite" # Base del Data Warehouse
CSV_DIR = Path(r"C:\Users\Usuario\Actividad 3. Data Warehouse, Data Mart, OLAP\ACT.3")
CSV_PATH = CSV_DIR / "garantias.csv" # CSV original (dentro de carpeta csv)
DM_PATH = SQLITE_DIR / "data_mart_ventas.sqlite"

# VALIDACIONES
if not DW_PATH.exists():
   raise FileNotFoundError(
      "No existe dw.sqlite. Ejecuta primero el notebook del Data Warehouse y vuelta"
    )

if not CSV_PATH.exists():
   raise FileNotFoundError(
       "No existe garantias.csv en la carpeta csv/. Colócalo en csv/garantias.csv"  
    )
print("OK -> Encontré:", DW_PATH, "y", CSV_PATH) 

# Conectar al Data Warehouse
dw_conn = sqlite3.connect(DW_PATH)

# Leer dimensiones y hechos del DW
dim_tiempo = pd.read_sql_query("SELECT * FROM dim_tiempo;", dw_conn)
dim_producto = pd.read_sql_query("SELECT * FROM dim_producto;", dw_conn)
dim_cliente = pd.read_sql_query("SELECT * FROM dim_cliente;", dw_conn)
fact_ventas = pd.read_sql_query("SELECT * FROM fact_ventas;", dw_conn)

dw_conn.close()

# Vista rápida
dim_tiempo.head(), dim_producto.head(), dim_cliente.head(), fact_ventas.head()

# Leer CSV
df_src = pd.read_csv(CSV_PATH)

# Normalizar nombres (por si hay espacios)
df_src.columns = [c.strip().lower() for c in df_src.columns]

# Asegurar columnas mínimas
cols_necesarias = {"producto", "categoria"}
faltantes = cols_necesarias - set(df_src.columns)
if faltantes:
  raise ValueError(f"Al CSV le faltan columnas necesarias: {faltantes}")

# Mapeo producto -> categoria (sin duplicados)
map_prod_cat = (
    df_src[["producto", "categoria"]]
    .dropna()
    .drop_duplicates()
    .reset_index(drop=True)
)
map_prod_cat.head()

# 1) Dimensión Categoría (Data Mart)
dim_categoria = map_prod_cat[["categoria"]].drop_duplicates().reset_index(drop=True)
dim_categoria["categoria_id"] = dim_categoria.index + 1
dim_categoria = dim_categoria[["categoria_id", "categoria"]]

# 2) Tabla puente Producto -> Categoría usando producto_id del DW
#(unimos por el nombre del producto)
dim_producto_dm = dim_producto.merge(map_prod_cat, on="producto", how="left")
 
# Asignar categoria_id a cada producto
cat_id_map = dict(zip(dim_categoria["categoria"], dim_categoria["categoria_id"]))
dim_producto_dm["categoria_id"] = dim_producto_dm["categoria"].map(cat_id_map)

# Mantener columnas relevantes para el DM
dim_producto_dm = dim_producto_dm[["producto_id", "producto", "categoria_id"]]
dim_categoria.head(), dim_producto_dm.head()

# Unir hechos del DW con producto->categoria y con tiempo
fact_dm = (
    fact_ventas
    .merge(dim_producto_dm[["producto_id", "categoria_id"]], on="producto_id", how="left")
    .merge(dim_tiempo[["date_id", "anio", "mes"]], on="date_id", how="left")
)

# Validación: ¿hay productos sin categoría?
sin_categoria = fact_dm["categoria_id"].isna().sum()
print("Registros sin categoria_id:", sin_categoria)

# Agregar (agregación OLAP-ready)
fact_ventas_dm_ag = (
    fact_dm
    .groupby(["anio", "mes", "categoria_id"], as_index=False)["ventas"]
    .sum()
    .rename(columns={"ventas": "total_ventas"})
)
fact_ventas_dm_ag.head() 

DM_PATH = Path("sqlite") / "data_mart_ventas.sqlite"
DM_PATH.parent.mkdir(parents=True, exist_ok=True)
print("DM_PATH:", DM_PATH.resolve())

# 1) Validación mínima del agregado OLAP-ready
required_cols = {"anio", "mes", "categoria_id", "total_ventas"}
missing = required_cols - set(fact_ventas_dm_ag.columns)
if missing:
  raise ValueError(f"fact_ventas_dm_ag NO tiene columnas requeridas: {missing}")

# 2) Dimensión tiempo del Data Mart
dim_tiempo_dm = (
    fact_ventas_dm_ag[["anio", "mes"]]
    .drop_duplicates()
    .sort_values(["anio", "mes"])
    .reset_index(drop=True)
)
dim_tiempo_dm["tiempo_id"] = dim_tiempo_dm.index + 1
dim_tiempo_dm = dim_tiempo_dm[["tiempo_id", "anio", "mes"]]

# 3) Tabla de hechos del Data Mart
# Vincular tiempo_id (categoria_id ya viene del puente producto->categoría)
fact_ventas_dm = fact_ventas_dm_ag.merge(dim_tiempo_dm, on=["anio", "mes"], how="left")
fact_ventas_dm = fact_ventas_dm[["tiempo_id", "categoria_id", "total_ventas"]]

# 4) Guardar en DB del Data Mart
dm_conn = sqlite3.connect(DM_PATH)
dm_conn.execute("PRAGMA foreign_keys = ON;")
dim_tiempo_dm.to_sql("dim_tiempo_dm", dm_conn, if_exists="replace", index=False)
dim_categoria.to_sql("dim_categoria", dm_conn, if_exists="replace", index=False)
fact_ventas_dm.to_sql("fact_ventas_dm", dm_conn, if_exists="replace", index=False)

dm_conn.commit()

# 5) Validación inmediata
tablas = pd.read_sql_query("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name;
""", dm_conn)

c_tiempo = pd.read_sql_query("SELECT COUNT(*) AS n FROM dim_tiempo_dm;", dm_conn)
c_cat = pd.read_sql_query("SELECT COUNT(*) AS n FROM dim_categoria;", dm_conn)
c_fact = pd.read_sql_query("SELECT COUNT(*) AS n FROM fact_ventas_dm;", dm_conn)

dm_conn.close()

print("OK -> Data Mart creado:", DM_PATH.resolve())
tablas, c_tiempo, c_cat, c_fact

dm_conn.close()
print("Conexión cerrada.")