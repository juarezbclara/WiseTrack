from flask import Flask, request, jsonify
import sqlite3
import requests
import pandas as pd

app = Flask(__name__)

#CONFIGURACIÓN
MONEDA_BASE = 'ARS'
MONEDA_DESTINO = 'USD'

# Ingresan dede la terminal sus datos
usuario = {
    "nombre": input("Ingrese su nombre: "),
    "trabajo": input("Ingrese su ocupación: "),
    "sueldo": float(input("Ingrese su sueldo mensual en ARS: ")),
    "porcentaje_gasto": float(input("Ingrese el porcentaje destinado a gastos mensuales (0%-100%): "))
}

#definimos la clase gasto
class Gasto:
    def __init__(self, descripcion, categoria, monto, moneda, mes):
        self.descripcion = descripcion
        self.categoria = categoria
        self.monto = monto
        self.moneda = moneda
        self.mes = mes

    def to_dict(self):# lo usamos para trasformar las tuplas en diccionarios
        return {
            "descripcion": self.descripcion,
            "categoria": self.categoria,
            "monto": self.monto,
            "moneda": self.moneda,
            "mes": self.mes
        }

#DICCIONARIO DE GASTOS INICIALES
gastos = {
    1: Gasto("Supermercado", "Alimentos", 20000, "ARS", "Enero").to_dict(),
    2: Gasto("Abono de celular", "Servicios", 6000, "ARS", "Febrero").to_dict(),
    3: Gasto("Salida al cine", "Entretenimiento", 4500, "ARS", "Abril").to_dict(),
    4: Gasto("Compra de libros", "Educación", 12000, "ARS", "Mayo").to_dict(),
    5: Gasto("Combustible", "Transporte", 10000, "ARS", "Octubre").to_dict(),
    6: Gasto("Ropa", "Indumentaria", 15000, "ARS", "Septiembre").to_dict()
}
contador_id =max(gastos.keys()) + 1 #ordena los id para que no se superpongan

#CONVERSIÓN DE MONEDA EXTERNA
def convertir_moneda_externa(monto, moneda_origen, moneda_destino):
    if moneda_origen.upper() == moneda_destino.upper():
        return monto

    url = f"https://v6.exchangerate-api.com/v6/4b7522cd6fe330f6a9ea6ac0/latest/{moneda_origen.upper()}" #api de terceros

    try:
        response = requests.get(url)
        if response.status_code == 200:
            tasas = response.json().get("conversion_rates", {})# cambio de moneda lo guarde en un diccionario
            return monto * tasas.get(moneda_destino.upper(), 1) # si no encuentra la tasa no cambia el monto
    except:
        return None


#ENDPOINTS
@app.route("/gastos", methods=["GET"])# Usamos get para poder ver nuestro diccionario
def listar_gastos():
    gastos_convertidos = {}# se almacena lo que se hace en el for

    for id, gasto in gastos.items():
       monto = gasto["monto"]
       moneda = gasto.get("moneda", MONEDA_BASE).upper()
       if moneda != MONEDA_DESTINO:
           monto_convertido = convertir_moneda_externa(monto, moneda, MONEDA_DESTINO)
       else:
          monto_convertido = monto

       gastos_convertidos[id] = {
        "descripcion": gasto["descripcion"],
        "categoria": gasto["categoria"],
        "monto": round(monto_convertido, 2),
        "moneda": MONEDA_DESTINO,
        "mes": gasto["mes"]
         }

    return jsonify(gastos_convertidos)

@app.route("/actualizar_moneda", methods=["PUT"])#Usamos put para modificar el tipo de moneda
def actualizar_moneda():
    global gastos## Accedemos al diccionario global 'gastos' que contiene los datos en memoria
    conn = sqlite3.connect("resumen.db")#conectamos la base de datos
    cursor = conn.cursor()

    tasa = None # donde vamos a guardar las tasas obtenidas desde la API
    try:
        url = f"https://v6.exchangerate-api.com/v6/4b7522cd6fe330f6a9ea6ac0/latest/{MONEDA_BASE}"
        response = requests.get(url)#llama ala api
        if response.status_code == 200:
            tasa = response.json().get("conversion_rates", {}).get(MONEDA_DESTINO, None) # vamos a obtener la tasa de conversion de la moneda destino
    except:
        return jsonify({"error": "Error al obtener tasa de cambio"}), 502 #si el pedido no funciona devuelve un error

    if tasa is None:
        return jsonify({"error": "No se pudo obtener la tasa de cambio"}), 502 #si la TASA no fue encontrada muestra error

    cursor.execute("SELECT id, monto FROM gastos_detallados WHERE moneda = ?", (MONEDA_BASE,)) # selecciona los datos apartir de la tabla
    gastos_ars = cursor.fetchall() #guarda todo los resultados en una lista de tupla

#convertimos de ARS a USD
    for gasto_id, monto_ars in gastos_ars:
        monto_usd = monto_ars * tasa
        cursor.execute("UPDATE gastos_detallados SET monto = ?, moneda = ? WHERE id = ?",
            (round(monto_usd, 2), MONEDA_DESTINO, gasto_id))
        #actualizamos el monto y la moneda en el registro de la base de datos

        if gasto_id in gastos:#Si ese gasto también está en el diccionario en memoria, lo actualizamos ahí también
            gastos[gasto_id]["monto"] = round(monto_usd, 2)
            gastos[gasto_id]["moneda"] = MONEDA_DESTINO

    conn.commit()# se guardan los cambios en la base de datos
    conn.close()#cirra la coneccion con la base de datos

#devuelve un mensaje que indica cuantos gastos fueron actualizados
    return jsonify({"mensaje": f"Se actualizaron {len(gastos_ars)} gastos de {MONEDA_BASE} a {MONEDA_DESTINO}"}), 200

@app.route("/gastos", methods=["POST"])# Vamos a agregar informacion
def agregar_gasto():
    global contador_id # cuando se genera un nuevo id le indica un valor unico
    data = request.get_json() or {} #los datos agregados se convierten en JSON

    try:
        monto = float(data["monto"])
    except (KeyError, ValueError):
        return jsonify({"error": "Monto obligatorio y debe ser numérico"}), 400 #si no es un numero da error

    moneda = data.get("moneda", MONEDA_BASE).upper()

    if moneda != MONEDA_DESTINO:#si la moneda no es la destino se va a convertir el monto
        convertido = convertir_moneda_externa(monto, moneda, MONEDA_DESTINO)# llamamos a la funcion
        if convertido is None:# si falla la conversion te da error
            return jsonify({"error": "Convesión fallida"}), 502
        monto = convertido
#nuevo diccionario con la moneda destino
    nuevo = {
        "descripcion": data.get("descripcion", ""),
        "categoria": data.get("categoria", ""),
        "monto": monto,
        "moneda": MONEDA_DESTINO,
        "mes": data.get("mes", "").strip().capitalize()
    }
    nuevo_id = contador_id# id unico al nuevo gasto
    gastos[nuevo_id] = nuevo # se guarda en el dicc global
    contador_id += 1 #deja el id incrementado para el siguiente gasto
    guardar_resumen_sqlite_todos(gastos)# se guarda en la base de datos
    return jsonify({"mensaje": "Gasto agregado", "id": nuevo_id}), 201


@app.route("/gastos/<int:id>", methods=["PUT"]) #Para actualizar/modificar los datos del id indicado
def actualizar_gasto(id):
    gasto = gastos.get(id) #recurre al dicc global de gastos para cada id
    if not gasto:
        return jsonify({"error": "Gasto no encontrado"}), 404

    data = request.get_json() or {}
    if "monto" in data:
        try:
            monto = float(data["monto"])
            moneda = data.get("moneda", MONEDA_BASE).upper()
            if moneda != MONEDA_DESTINO:
                monto = convertir_moneda_externa(monto, moneda, MONEDA_DESTINO)
            gasto["monto"] = monto# agregas al diccionario el nuevo monto
        except ValueError:
            return jsonify({"error": "Monto inválido"}), 400

    for campo in ["descripcion", "categoria","mes"]:
        if campo in data:
            gasto[campo] = data[campo].strip().capitalize()# va a actualizar el gasto con el nuevo valor, borra los espacios vacios del principio y del final y pone la primera letra mayuscula
    gasto["moneda"] = MONEDA_DESTINO

    return jsonify({"mensaje": "Gasto actualizado"})

@app.route("/gastos/<int:id>", methods=["DELETE"])#para borrar algun gasto
def eliminar_gasto(id):
    if id in gastos:
        del gastos[id]
        return jsonify({"mensaje": "Gasto eliminado"})
    return jsonify({"error": "Gasto no encontrado"}), 404

@app.route("/resumen", methods=["GET"]) #/resumen?mes=Agosto (en el postman)
def resumen_mensual():
        mes = request.args.get("mes", "").strip().capitalize() #Obtenemos el valor del parámetro 'mes' enviado por la URL
        total = 0
        gastos_del_mes = []

        for gasto in gastos.values():
            if gasto["mes"].strip().capitalize() == mes:
                total += gasto["monto"]#sumamos el total
                gastos_del_mes.append(gasto) # guardamos los gastos en la lista

            # Calculamos el límite mensual con los datos del usuario
        limite_permitido = usuario["sueldo"] * (usuario["porcentaje_gasto"] / 100)

        if total > limite_permitido:
            mensaje = "Te pasaste del límite"
        else:
            mensaje = "Estás dentro del límite"

        return jsonify({
            "usuario": usuario["nombre"],
            "trabajo": usuario["trabajo"],
            "sueldo_mensual": usuario["sueldo"],
            "porcentaje_gasto_destinado": usuario["porcentaje_gasto"],
            "mes": mes,
            "total_gastado": total,
            "limite": limite_permitido,
            "mensaje": mensaje,
            "gastos": gastos_del_mes
        })


#GUARDAR EN SQLITE
def guardar_resumen_sqlite_todos(gastos):
# conectamos la base de datos SQLite
    conn = sqlite3.connect("resumen_mensual.db")
    cursor = conn.cursor()

#Creamos la tabla
    cursor.execute('''CREATE TABLE IF NOT EXISTS  gastos_detallados (id INTEGER PRIMARY KEY AUTOINCREMENT, descripcion TEXT, categoria TEXT, monto REAL, moneda TEXT, mes TEXT)''')
#Se borra todo el contenido de la tabla para evitar duplicados cada vez que guardamos
    cursor.execute('DELETE FROM gastos_detallados')


    totales_por_mes = {}#acummula en un dicc vacio los montos por mes

    for id_gasto, gasto in gastos.items():#recorre el diccionario gastos
        monto = gasto.get("monto", 0)
        moneda = gasto.get("moneda", MONEDA_BASE).upper()
        mes = gasto.get("mes", "").strip().capitalize()

        if moneda != MONEDA_DESTINO:
            monto_convertido = convertir_moneda_externa(monto, moneda, MONEDA_DESTINO)
            if monto_convertido is None:
                monto_convertido = monto
        else:
            monto_convertido = monto
#insertamos el gasto en la base de datos
        cursor.execute(''' INSERT INTO gastos_detallados (id, descripcion, categoria, monto, moneda, mes)
           VALUES (?, ?, ?, ?, ?, ?)''', (
        id_gasto,
        gasto.get("descripcion", ""),
        gasto.get("categoria", ""),
        round(monto_convertido, 2),
        MONEDA_DESTINO,
        mes
        ))
#se acumula todo en el diccionario
        totales_por_mes[mes] = totales_por_mes.get(mes, 0) + monto_convertido
#insertamos una fila resumen por cada mes en la misma tabla
    for mes, total in totales_por_mes.items():
        cursor.execute('''INSERT INTO gastos_detallados (descripcion, categoria, monto, moneda, mes)
           VALUES (?, ?, ?, ?, ?)''', (
        f"Total mes {mes}",
        "Total",
        round(total, 2),
        MONEDA_DESTINO,
        mes
        ))

    conn.commit()# se guardan los cambios en la base de datos
    conn.close()#se cierra la conneccion


# Endpoint para guardar resumen en SQLite
@app.route("/guardar_resumen", methods=["POST"])
def guardar_resumen_endpoint():
    guardar_resumen_sqlite_todos(gastos)
    return jsonify({"mensaje": "Resumen guardado exitosamente en resumen_mensual.db"})

# EJECUCIÓN
if __name__ == "__main__":
    app.run(debug=True)
#csv
import csv
gasto1 = {
    1: {"descripcion": "Supermercado", "categoria": "Alimentos", "monto": 20000, "moneda": "ARS", "mes": "Enero"},
    2: {"descripcion": "Abono de celular", "categoria": "Servicios", "monto": 6000, "moneda": "ARS", "mes": "Febrero"},
    3: {"descripcion": "Salida al cine", "categoria": "Entretenimiento", "monto": 4500, "moneda": "ARS", "mes": "Abril"},
    4: {"descripcion": "Compra de libros", "categoria": "Educación", "monto": 12000, "moneda": "ARS", "mes": "Mayo"},
    5: {"descripcion": "Combustible", "categoria": "Transporte", "monto": 10000, "moneda": "ARS", "mes": "Octubre"},
    6: {"descripcion": "Ropa", "categoria": "Indumentaria", "monto": 15000, "moneda": "ARS", "mes": "Septiembre"}
}

# Crear archivo CSV
with open('gasto1.csv', 'w', newline='', encoding='utf-8') as f:# abrimos el archivo en modo escritura
    writer = csv.DictWriter(f, fieldnames=["id","descripcion","categoria","monto","moneda","mes"])
    # Creamos un escritor de CSV que usará un diccionario por fila, con las claves indicadas como encabezados
    writer.writeheader()# Escribimos la primera fila del CSV con los nombres de las columnas
    for id_gasto, datos in gasto1.items():
        fila = {"id": id_gasto}
        fila.update(datos)
        writer.writerow(fila)
df = pd.read_csv('/content/gasto1.csv')# lee el archivo con pandas


