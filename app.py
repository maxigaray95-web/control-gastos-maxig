import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="Control Financiero PRO", layout="wide")

st.title("💳 Control Financiero PRO")

# ------------------------
# PARSE NUMEROS
# ------------------------
def parsear_numero(s):
    try:
        return float(s.replace(".", "").replace(",", "."))
    except:
        return None

# ------------------------
# INPUTS
# ------------------------
sueldo_input = st.text_input("💰 Sueldo mensual (ej: 1093000,50)")
sueldo = parsear_numero(sueldo_input)

dolar_input = st.text_input("💵 Cotización dólar (ej: 1450)")
dolar = parsear_numero(dolar_input)

# ------------------------
# PRESUPUESTOS
# ------------------------
st.subheader("🎯 Presupuesto por categoría")

presupuestos = {
    "Supermercado": st.number_input("Supermercado", value=200000),
    "Combustible": st.number_input("Combustible", value=120000),
    "Entretenimiento": st.number_input("Entretenimiento", value=50000),
    "Salud": st.number_input("Salud", value=40000),
    "Educación": st.number_input("Educación", value=50000),
    "Estudios": st.number_input("Estudios", value=250000),
    "Impuestos": st.number_input("Impuestos", value=80000),
    "Otros": st.number_input("Otros", value=50000),
}

# ------------------------
# FILE UPLOAD
# ------------------------
archivos = st.file_uploader("📂 Subí resúmenes", type="pdf", accept_multiple_files=True)

# ------------------------
# EXTRAER TEXTO
# ------------------------
def extraer_texto(pdf):
    texto = ""
    with pdfplumber.open(pdf) as pdf_file:
        for pagina in pdf_file.pages:
            contenido = pagina.extract_text()
            if contenido:
                texto += contenido + "\n"
    return texto

# ------------------------
# CATEGORIAS
# ------------------------
def categorizar(desc):
    d = desc.lower()

    if "ypf" in d or "shell" in d:
        return "Combustible"
    elif "mercado" in d:
        return "Supermercado"
    elif "netflix" in d or "spotify" in d:
        return "Entretenimiento"
    elif "farmacia" in d:
        return "Salud"
    elif "udemy" in d:
        return "Educación"
    elif "pagotic" in d or "unsiglo" in d:
        return "Estudios"
    elif "impuesto" in d or "iva" in d:
        return "Impuestos"
    else:
        return "Otros"

# ------------------------
# PARSER SUPERVIELLE
# ------------------------
def parser_supervielle(texto):
    datos = []
    lineas = texto.split("\n")

    for linea in lineas:
        if "C." in linea:
            match = re.search(r"C\.(\d+)/(\d+)", linea)
            monto = re.search(r"([\d\.]+,\d+)$", linea)

            if match and monto:
                valor = parsear_numero(monto.group(1))

                datos.append({
                    "descripcion": linea,
                    "monto": valor,
                    "restantes": int(match.group(2)) - int(match.group(1))
                })

    df = pd.DataFrame(datos)

    total_match = re.search(r"SALDO ACTUAL\s+([\d\.,]+)", texto)
    total = parsear_numero(total_match.group(1)) if total_match else 0

    return df, total, 0

# ------------------------
# PARSER SANTANDER
# ------------------------
def parser_santander(texto):
    datos = []
    total_usd = 0

    for linea in texto.split("\n"):
        monto_pesos = re.search(r"([\d\.]+,\d+)", linea)
        monto_usd = re.search(r"USD\s*([\d\.,]+)", linea)

        if monto_pesos:
            valor = parsear_numero(monto_pesos.group(1))
        else:
            valor = 0

        if monto_usd:
            total_usd += parsear_numero(monto_usd.group(1))

        if monto_pesos or monto_usd:
            datos.append({
                "descripcion": linea,
                "monto": valor
            })

    df = pd.DataFrame(datos)

    total_match = re.search(r"Total Consumos.*?([\d\.,]+)", texto)
    total = parsear_numero(total_match.group(1)) if total_match else 0

    return df, total, total_usd

# ------------------------
# HISTORIAL
# ------------------------
def guardar_historial(total, saldo):
    archivo = "historial.csv"
    fecha = datetime.now().strftime("%Y-%m")

    nuevo = pd.DataFrame([{
        "mes": fecha,
        "total_gastado": total,
        "saldo": saldo
    }])

    if os.path.exists(archivo):
        viejo = pd.read_csv(archivo)
        viejo = viejo[viejo["mes"] != fecha]
        df = pd.concat([viejo, nuevo], ignore_index=True)
    else:
        df = nuevo

    df.to_csv(archivo, index=False)

# ------------------------
# PROCESAMIENTO
# ------------------------
if archivos and sueldo:

    total_pesos = 0
    total_usd = 0
    lista_df = []

    for archivo in archivos:
        texto = extraer_texto(archivo)

        if "Supervielle" in texto:
            df, total, usd = parser_supervielle(texto)
        else:
            df, total, usd = parser_santander(texto)

        total_pesos += total
        total_usd += usd
        lista_df.append(df)

    df_total = pd.concat(lista_df, ignore_index=True)
    df_total["categoria"] = df_total["descripcion"].apply(categorizar)

    gastos_categoria = df_total.groupby("categoria")["monto"].sum()

    usd_en_pesos = total_usd * dolar if dolar else 0
    total_final = total_pesos + usd_en_pesos
    saldo = sueldo - total_final

    guardar_historial(total_final, saldo)

    # ------------------------
    # RESULTADOS
    # ------------------------
    st.subheader("📊 Resultado")
    st.write(f"Total: ${total_final:,.0f}")
    st.write(f"Saldo: ${saldo:,.0f}")

    # ------------------------
    # ALERTAS
    # ------------------------
    st.subheader("🚨 Alertas")

    for cat, gasto in gastos_categoria.items():
        presupuesto = presupuestos.get(cat, 0)
        if gasto > presupuesto:
            st.error(f"{cat}: te pasaste")

    if saldo < 0:
        st.error("Estás en negativo")

    # ------------------------
    # PREDICCION
    # ------------------------
    st.subheader("🔮 Predicción")

    if os.path.exists("historial.csv"):
        hist = pd.read_csv("historial.csv")

        if len(hist) >= 2:
            promedio = hist["total_gastado"].mean()
            tendencia = hist["total_gastado"].iloc[-1] - hist["total_gastado"].iloc[-2]
            pred = promedio + tendencia

            st.write(f"Predicción: ${pred:,.0f}")

    # ------------------------
    # RECOMENDACIONES
    # ------------------------
    st.subheader("🧠 Recomendaciones")

    for cat, gasto in gastos_categoria.items():
        presupuesto = presupuestos.get(cat, 0)
        if gasto > presupuesto:
            st.warning(f"Bajá {cat}")

    if saldo < sueldo * 0.2:
        st.warning("Tenés poco margen")

    # ------------------------
    # GRAFICOS
    # ------------------------
    st.subheader("📊 Categorías")
    st.bar_chart(gastos_categoria)

# ------------------------
# DASHBOARD
# ------------------------
if os.path.exists("historial.csv"):
    hist = pd.read_csv("historial.csv")

    st.subheader("📈 Evolución")
    st.line_chart(hist.set_index("mes"))