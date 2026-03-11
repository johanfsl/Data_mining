import pandas as pd
import sqlite3
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Usuario\Actividad 3. Data Warehouse, Data Mart, OLAP\ACT.3")

archivo = BASE_DIR / "garantias.csv"
df = pd.read_csv(archivo)
df.head()

# Eliminar filas con valores nulos
df_limpio = df.dropna()

# Eliminar espacios en columnas de texto
df_limpio = df_limpio.apply(
lambda x: x.str.strip() if x.dtype == "object" else x
)
# Verificar cambios
df_limpio.info()

# Crear un nuevo DataFrame llamado df_dw
# seleccionando únicamente las columnas del DataFrame original df_limpio
df_dw = df_limpio[['fecha','producto','cliente','ventas']]

# Crear carpeta csv si no existe
Path("csv").mkdir(exist_ok=True)

# Guardar archivo limpio en la carpeta csv
df_dw.to_csv("csv/datos_limpios_dw.csv", index=False)

# Leer el archivo CSV llamado "datos_limpios_dw.csv"
# y cargar su contenido en un DataFrame de pandas
df_dw = pd.read_csv("csv/datos_limpios_dw.csv")

# Convertir la columna "fecha" a formato de fecha (datetime)
# Si algún valor no se puede convertir, se reemplaza por NaT (valor nulo)
df_dw["fecha"] = pd.to_datetime(df_dw["fecha"], errors="coerce")

# Convertir la columna "ventas" a valores numéricos
df_dw["ventas"] = pd.to_numeric(df_dw["ventas"], errors="coerce")

# Eliminar las filas que tengan valores nulos (NaT o NaN)
# específicamente en las columnas "fecha" o "ventas"

df_dw = df_dw.dropna(subset=["fecha", "ventas"])
df_dw.head() # mostrar las primeras 5 filas del DataFrame


# Dimensión Tiempo
# Crear la dimensión tiempo a partir de la columna "fecha"
dim_tiempo = (
df_dw[["fecha"]] # seleccionar la columna "fecha" del DataFrame base
.drop_duplicates() # eliminar fechas repetidas
.assign( # crear nuevas columnas derivadas de la fecha 
# Crear un ID de fecha con formato YYYYMMDD
# se usa como clave primaria de la dimensión
date_id=lambda d: d["fecha"].dt.strftime("%Y%m%d").astype(int),
anio=lambda d: d["fecha"].dt.year, # extraer el año de la fecha
mes=lambda d: d["fecha"].dt.month, # extraer el mes de la fecha
dia=lambda d: d["fecha"].dt.day # extraer el día de la fecha
)[["date_id", "fecha", "anio", "mes", "dia"]] # reordenar las columnas de la di
.reset_index(drop=True) # reiniciar el índice para que sea consecutivo
)
# Dimensión Producto
dim_producto = (
df_dw[["producto"]]
.drop_duplicates()
.reset_index(drop=True) # Reiniciar el índice
)
# Crear un identificador único para cada producto
dim_producto["producto_id"] = dim_producto.index + 1
# Reordenar las columnas
dim_producto = dim_producto[["producto_id", "producto"]]
# Dimensión Cliente
dim_cliente = (
df_dw[["cliente"]]
.drop_duplicates()
.reset_index(drop=True)
)
dim_cliente["cliente_id"] = dim_cliente.index + 1
dim_cliente = dim_cliente[["cliente_id", "cliente"]]
# Mostrar las primeras filas de cada dimensión creada
dim_tiempo.head(), dim_producto.head(), dim_cliente.head()

# Mapas para sustituir texto por IDs
# 1
map_producto = dict(zip(dim_producto["producto"], dim_producto["producto_id"]))
# 2
map_cliente = dict(zip(dim_cliente["cliente"], dim_cliente["cliente_id"]))
# --- CREAR TABLA DE HECHOS (FACT_VENTAS)
# Crear una copia del DataFrame base para no modificar df_dw
fact_ventas = df_dw.copy()
# Crear la clave foránea date_id a partir de la fecha
fact_ventas["date_id"] = fact_ventas["fecha"].dt.strftime("%Y%m%d").astype(int)
# Reemplazar el nombre del producto por su producto_id
fact_ventas["producto_id"] = fact_ventas["producto"].map(map_producto)
# Reemplazar el nombre del cliente por su cliente_id
fact_ventas["cliente_id"] = fact_ventas["cliente"].map(map_cliente)
# --- SELECCIONAR SOLO LAS COLUMNAS DE LA TABLA DE HECHOS
# 3
fact_ventas = fact_ventas[["date_id", "producto_id", "cliente_id", "ventas"]]
fact_ventas.head()


# CONEXIÓN A LA BASE DE DATOS SQLITE
# Definir el nombre (y ruta) del archivo de la base de datos
# Si no existe, SQLite lo crea automáticamente
SQLITE_DIR = Path("sqlite")
SQLITE_DIR.mkdir(exist_ok=True)
db_path = SQLITE_DIR / "dw.sqlite"
# Crear la conexión a la base de datos
conn = sqlite3.connect(db_path)
# GUARDAR TABLAS DE DIMENSIÓN
# Guardar la dimensión tiempo en la base de datos
# if_exists="replace" significa que se sobrescribe si ya existe
# index=False evita guardar el índice como columna
dim_tiempo.to_sql("dim_tiempo", conn, if_exists="replace", index=False)
# Guardar la dimensión producto
dim_producto.to_sql("dim_producto", conn, if_exists="replace", index=False)
# Guardar la dimensión cliente
dim_cliente.to_sql("dim_cliente", conn, if_exists="replace", index=False)
# GUARDAR TABLA DE HECHOS
# Guardar la tabla de hechos de ventas
fact_ventas.to_sql("fact_ventas", conn, if_exists="replace", index=False)
# CERRAR CONEXIÓN
conn.close()
# Mostrar la ruta del archivo de la base de datos creada
db_path

conn = sqlite3.connect("sqlite/dw.sqlite") # Conectarse a la base de datos del Data
# Consulta 1: Obtener total de ventas por producto
q1 = """
SELECT p.producto, SUM(f.ventas) AS total_ventas
FROM fact_ventas f
JOIN dim_producto p ON p.producto_id = f.producto_id
GROUP BY p.producto
ORDER BY total_ventas DESC;
"""
ventas_por_producto = pd.read_sql_query(q1, conn) # Ejecutar la consulta y guardar
# Consulta 2: Obtener total de ventas por cliente
q2 = """
SELECT c.cliente, SUM(f.ventas) AS total_ventas
FROM fact_ventas f
JOIN dim_cliente c ON c.cliente_id = f.cliente_id
GROUP BY c.cliente
ORDER BY total_ventas DESC;
"""
ventas_por_cliente = pd.read_sql_query(q2, conn)
# Ventas por mes
q3 = """
SELECT t.anio, t.mes, SUM(f.ventas) AS total_ventas
FROM fact_ventas f
JOIN dim_tiempo t ON t.date_id = f.date_id
GROUP BY t.anio, t.mes
ORDER BY t.anio, t.mes;
"""
ventas_por_mes = pd.read_sql_query(q3, conn)
conn.close()
# Mostrar los resultados obtenidos
ventas_por_producto, ventas_por_cliente, ventas_por_mes
# Carpeta donde se guardarán los CSV del Data Warehouse
CSV_DIR = Path("csv")
CSV_DIR.mkdir(exist_ok=True)
print("Los CSV se guardarán en:", CSV_DIR.resolve())
# Exporta la dimensión de tiempo a un archivo CSV
# index=False evita que se guarde el índice del DataFrame como una columna adiciona
dim_tiempo.to_csv(CSV_DIR / "dim_tiempo.csv", index=False)
# Exporta la dimensión de producto a un archivo CSV
dim_producto.to_csv(CSV_DIR / "dim_producto.csv", index=False)

# Exporta la dimensión de cliente a un archivo CSV
dim_cliente.to_csv(CSV_DIR / "dim_cliente.csv", index=False)
# Exporta la tabla de hechos de ventas a un archivo CSV
fact_ventas.to_csv(CSV_DIR / "fact_ventas.csv", index=False)
# Lista de los archivos CSV generados
# Útil para validación, logging o procesamiento posterior
["dim_tiempo.csv", "dim_producto.csv", "dim_cliente.csv", "fact_ventas.csv"]
