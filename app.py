import streamlit as st
import pdfplumber
import re
import pandas as pd

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
# DETECTAR BANCO
# ------------------------
def detectar_banco(texto):
    texto = texto.lower()

    if "santander" in texto:
        return "Santander"
    elif "supervielle" in texto:
        return "Supervielle"
    else:
        return "Desconocido"

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
# PROCESAR RESUMEN
# ------------------------
def procesar_resumen(texto):

    total_pagar = 0
    total_usd = 0
    cuotas_info = []

    # TOTAL REAL DEL RESUMEN
    match_total = re.search(r"(SALDO ACTUAL|Total Consumos).*?([\d\.,]+)", texto)

    if match_total:
        total_pagar = parsear_numero(match_total.group(2))

    # USD
    usd_matches = re.findall(r"USD\s*([\d\.,]+)", texto)
    for usd in usd_matches:
        total_usd += parsear_numero(usd)

    # CUOTAS
    for linea in texto.split("\n"):

        match_cuota = re.search(r"C\.(\d+)/(\d+)", linea)

        if match_cuota:
            actual = int(match_cuota.group(1))
            total = int(match_cuota.group(2))

            cuotas_info.append({
                "descripcion": linea,
                "cuota_actual": actual,
                "cuotas_totales": total
            })

    return total_pagar, total_usd, cuotas_info

# ------------------------
# INPUTS
# ------------------------
sueldo_input = st.text_input("💰 Sueldo mensual")
dolar_input = st.text_input("💵 Cotización dólar")

sueldo = parsear_numero(sueldo_input) if sueldo_input else 0
dolar = parsear_numero(dolar_input) if dolar_input else 0

# ------------------------
# UPLOAD
# ------------------------
archivos = st.file_uploader("📂 Subí resúmenes", type="pdf", accept_multiple_files=True)

# ------------------------
# PROCESAMIENTO
# ------------------------
if archivos and sueldo:

    total_general = 0
    total_usd = 0
    todas_cuotas = []
    totales_por_banco = {}

    st.subheader("📄 Resumen por tarjeta")

    for archivo in archivos:

        texto = extraer_texto(archivo)

        banco = detectar_banco(texto)

        total, usd, cuotas = procesar_resumen(texto)

        total_general += total
        total_usd += usd
        todas_cuotas.extend(cuotas)

        # acumular por banco
        if banco not in totales_por_banco:
            totales_por_banco[banco] = 0

        totales_por_banco[banco] += total

        # UI por resumen
        st.markdown("---")
        st.subheader(f"🏦 {banco} | 📄 {archivo.name}")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("💰 Total a pagar", f"${total:,.0f}")

        with col2:
            if usd > 0:
                st.metric("💵 Consumos en USD", f"{usd:.2f}")

    # ------------------------
    # CONVERSION USD
    # ------------------------
    usd_en_pesos = total_usd * dolar if dolar else 0
    total_final = total_general + usd_en_pesos
    saldo = sueldo - total_final

    # ------------------------
    # RESULTADO GENERAL
    # ------------------------
    st.subheader("💰 Total general")

    st.write(f"💸 Total en pesos: ${total_general:,.0f}")
    st.write(f"💵 Total USD: {total_usd:.2f}")

    if dolar:
        st.write(f"💱 USD en pesos: ${usd_en_pesos:,.0f}")

    st.write(f"🔥 TOTAL FINAL: ${total_final:,.0f}")
    st.write(f"💰 Saldo disponible: ${saldo:,.0f}")

    # ------------------------
    # DEUDA POR BANCO
    # ------------------------
    st.subheader("🏦 Deuda por banco")

    total_global = sum(totales_por_banco.values())

    for banco, monto in totales_por_banco.items():
        porcentaje = (monto / total_global) * 100 if total_global > 0 else 0
        st.write(f"{banco}: ${monto:,.0f} ({porcentaje:.1f}%)")

    # gráfico
    df_bancos = pd.DataFrame(
        list(totales_por_banco.items()),
        columns=["Banco", "Monto"]
    )

    st.bar_chart(df_bancos.set_index("Banco"))

    # ------------------------
    # CUOTAS
    # ------------------------
    st.subheader("💳 Cuotas detectadas")

    if todas_cuotas:
        df_cuotas = pd.DataFrame(todas_cuotas)
        st.dataframe(df_cuotas)
        st.write(f"Total de compras en cuotas: {len(df_cuotas)}")
    else:
        st.write("No se detectaron cuotas")
