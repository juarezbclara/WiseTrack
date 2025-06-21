import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# lo conectamos con nuestra base de datos
conn = sqlite3.connect('resumen_mensual.db')

# Lee los datos de la tabla
df = pd.read_sql_query("SELECT * FROM gastos_detallados", conn)

# cierra la conneccion
conn.close()

# va a mostrar las primeras filas
print(df.head())

# Va a eliminar todas las filas de total
df = df.query("categoria != 'Total'")

# Agrupa por categoría
gastos_por_categoria = df.groupby('categoria')['monto'].sum().sort_values(ascending=False)

#paleta de colores para cada categoria
colores = plt.cm.tab20.colors

# crea grafico de torta
plt.figure(figsize=(8, 8))
plt.pie(
    gastos_por_categoria,
    labels=gastos_por_categoria.index,#etiqueta
    autopct='%1.1f%%',# mostrar los porcentajes
    colors=colores[:len(gastos_por_categoria)],# le da un color a cada categoria
    wedgeprops={'edgecolor': 'black'}# divide las porciones con un borde negro
)

# Título del gráfico
plt.title('Distribución de Gastos por Categoría (USD)', fontsize=14, fontweight='bold')

plt.show()# muestra el grafico
