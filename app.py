import streamlit as st
import pdfplumber
import re
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="Control Financiero PRO", layout="wide")

st.title("💳 Control Financiero PRO")

# ------------------------
# FUNCION NUMEROS
# ------------------------
def parsear_numero(s):
    try:
        return float(s.replace(".", "").replace(",", "."))
    except:
        return 0

# ------------------------
# INPUTS
# ------------------------
sueldo_input = st.text_input("💰 Sueldo mensual")
dolar_input = st.text_input("💵 Cotización dólar")

sueldo = parsear_numero(sueldo_input) if sueldo_input else 0
dolar = parsear_numero(dolar_input) if dolar_input else 0

# ------------------------
# SUBIR ARCHIVOS
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
# PARSER GENERAL (CUOTAS + USD)
# ------------------------
def procesar_resumen(texto):
    datos = []
    total_pesos = 0
    total_usd = 0
    cuotas_detectadas = []

    for linea in texto.split("\n"):

        # detectar monto en pesos
        monto_pesos = re.search(r"([\d\.]+,\d+)", linea)

        # detectar USD
        monto_usd = re.search(r"USD\s*([\d\.,]+)", linea)

        # detectar cuotas
        match_cuota = re.search(r"C\.(\d+)/(\d+)", linea)

        valor = 0

        if monto_pesos:
            valor = parsear_numero(monto_pesos.group(1))
            total_pesos += valor

        if monto_usd:
            usd = parsear_numero(monto_usd.group(1))
            total_usd += usd

        # si hay cuotas → calcular pendientes
        if match_cuota and valor > 0:
            actual = int(match_cuota.group(1))
            total = int(match_cuota.group(2))
            restantes = total - actual

            for i in range(restantes):
                cuotas_detectadas.append(valor)

        if monto_pesos or monto_usd:
            datos.append({
                "descripcion": linea,
                "monto": valor
            })

    df = pd.DataFrame(datos)

    return df, total_pesos, total_usd, cuotas_detectadas

# ------------------------
# PROCESAMIENTO
# ------------------------
if archivos and sueldo:

    total_pesos = 0
    total_usd = 0
    lista_df = []
    todas_cuotas = []

    for archivo in archivos:
        texto = extraer_texto(archivo)

        df, pesos, usd, cuotas = procesar_resumen(texto)

        total_pesos += pesos
        total_usd += usd
        lista_df.append(df)
        todas_cuotas.extend(cuotas)

    df_total = pd.concat(lista_df, ignore_index=True)

    # conversion USD
    usd_en_pesos = total_usd * dolar if dolar else 0
    total_final = total_pesos + usd_en_pesos
    saldo = sueldo - total_final

    # ------------------------
    # RESULTADOS
    # ------------------------
    st.subheader("📊 Resultado")

    st.write(f"💸 Total en pesos: ${total_pesos:,.0f}")
    st.write(f"💵 USD: {total_usd:.2f}")

    if dolar:
        st.write(f"💱 USD en pesos: ${usd_en_pesos:,.0f}")

    st.write(f"🔥 TOTAL REAL: ${total_final:,.0f}")
    st.write(f"💰 Saldo disponible: ${saldo:,.0f}")

    # ------------------------
    # CUOTAS
    # ------------------------
    st.subheader("💳 Cuotas pendientes")

    total_cuotas = sum(todas_cuotas)

    st.write(f"Total deuda en cuotas: ${total_cuotas:,.0f}")
    st.write(f"Cantidad de cuotas: {len(todas_cuotas)}")

    # ------------------------
    # PROYECCION
    # ------------------------
    st.subheader("📅 Proyección mensual de cuotas")

    proyeccion = {}

    for i, monto in enumerate(todas_cuotas):
        mes = f"Mes {i+1}"
        proyeccion[mes] = proyeccion.get(mes, 0) + monto

    df_proyeccion = pd.DataFrame(list(proyeccion.items()), columns=["Mes", "Monto"])

    if not df_proyeccion.empty:
        st.bar_chart(df_proyeccion.set_index("Mes"))
        st.dataframe(df_proyeccion)

    # ------------------------
    # DETALLE
    # ------------------------
    st.subheader("📄 Detalle de consumos")
    st.dataframe(df_total)
