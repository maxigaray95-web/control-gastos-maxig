import streamlit as st
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="Control Financiero PRO", layout="wide")
st.title("💳 Control Financiero PRO")


# ------------------------
# FUNCION NUMEROS
# FIX: agregado .replace(" ", "") para manejar espacios en montos ("12 500,00")
# ------------------------
def parsear_numero(s):
    try:
        return float(s.replace(" ", "").replace(".", "").replace(",", "."))
    except:
        return 0


# ------------------------
# DETECTAR BANCO
# ------------------------
def detectar_banco(texto):
    texto_lower = texto.lower()
    if "santander" in texto_lower:
        return "Santander"
    elif "supervielle" in texto_lower:
        return "Supervielle"
    else:
        return "Desconocido"


# ------------------------
# EXTRAER TEXTO
# FIX: manejo de páginas sin texto (PDFs escaneados)
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
# FIX 1: regex del total corregido para capturar número completo
# FIX 2: USD ya no se suma al total (evita doble conteo si el banco ya lo convirtió)
# FIX 3: descripción de cuota ahora es solo la parte útil, no la línea entera
# ------------------------
def procesar_resumen(texto):

    total_pagar = 0
    total_usd = 0
    cuotas_info = []

    # TOTAL REAL DEL RESUMEN
    # FIX: [^\d]* en lugar de .*? para no capturar el primer número suelto
    match_total = re.search(
        r"(SALDO ACTUAL|TOTAL A PAGAR|Total Consumos)[^\d]*([\d\.,]+)",
        texto,
        re.IGNORECASE
    )
    if match_total:
        total_pagar = parsear_numero(match_total.group(2))

    # USD
    # FIX: capturamos los consumos en USD para mostrarlos por separado
    # NO los sumamos al total_general para evitar doble conteo
    usd_matches = re.findall(r"USD\s*([\d\.,]+)", texto)
    for usd in usd_matches:
        total_usd += parsear_numero(usd)

    # CUOTAS
    for linea in texto.split("\n"):
        linea = linea.strip()
        if not linea:
            continue

        match_cuota = re.search(r"C\.(\d+)/(\d+)", linea)
        if match_cuota:
            actual = int(match_cuota.group(1))
            total_c = int(match_cuota.group(2))

            # FIX: extraemos descripción corta (hasta 60 chars antes del patrón de cuota)
            descripcion_corta = linea[:linea.index(match_cuota.group(0))].strip()
            if len(descripcion_corta) > 60:
                descripcion_corta = descripcion_corta[:60] + "..."

            # Intentar extraer monto de la línea
            montos = re.findall(r"[\d\.,]{4,}", linea)
            monto_cuota = parsear_numero(montos[-1]) if montos else 0

            cuotas_info.append({
                "Descripción": descripcion_corta or linea[:40],
                "Cuota": f"{actual}/{total_c}",
                "Cuotas restantes": total_c - actual,
                "Monto cuota": monto_cuota,
            })

    return total_pagar, total_usd, cuotas_info


# ------------------------
# INPUTS
# ------------------------
col_s, col_d = st.columns(2)
with col_s:
    sueldo_input = st.text_input("💰 Sueldo mensual")
with col_d:
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
    total_usd_global = 0
    todas_cuotas = []
    totales_por_banco = {}
    archivos_sin_texto = []

    st.subheader("📄 Resumen por tarjeta")

    for archivo in archivos:

        texto = extraer_texto(archivo)

        # FIX: advertencia si el PDF no tiene texto extraíble
        if not texto.strip():
            st.warning(f"⚠️ No se pudo leer texto de **{archivo.name}**. ¿Es un PDF escaneado?")
            archivos_sin_texto.append(archivo.name)
            continue

        banco = detectar_banco(texto)
        total, usd, cuotas = procesar_resumen(texto)

        # FIX: solo sumamos el total en pesos al general (USD se muestra aparte)
        total_general += total
        total_usd_global += usd
        todas_cuotas.extend(cuotas)

        if banco not in totales_por_banco:
            totales_por_banco[banco] = 0
        totales_por_banco[banco] += total

        # UI por resumen
        st.markdown("---")
        st.subheader(f"🏦 {banco} | 📄 {archivo.name}")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total a pagar (ARS)", f"${total:,.0f}")
        with col2:
            if usd > 0:
                st.metric("💵 Consumos en USD", f"USD {usd:.2f}")
        with col3:
            if usd > 0 and dolar:
                st.metric("💱 USD convertido", f"${usd * dolar:,.0f}")

    if not totales_por_banco:
        st.error("No se pudo procesar ningún archivo.")
        st.stop()

    # ------------------------
    # CONVERSION USD y TOTALES
    # ------------------------
    usd_en_pesos = total_usd_global * dolar if dolar else 0

    # FIX: el total_final solo suma USD en pesos si el usuario ingresó cotización
    # Se asume que total_general ya incluye los cargos en ARS del resumen
    # y que los USD mostrados son ADICIONALES no convertidos por el banco
    total_final = total_general + usd_en_pesos
    saldo = sueldo - total_final

    # ------------------------
    # RESULTADO GENERAL
    # ------------------------
    st.markdown("---")
    st.subheader("💰 Total general")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💸 Total ARS", f"${total_general:,.0f}")
    with col2:
        st.metric("💵 Total USD", f"USD {total_usd_global:.2f}")
    with col3:
        if dolar:
            st.metric("🔥 Total Final", f"${total_final:,.0f}")
        else:
            st.metric("🔥 Total Final", f"${total_general:,.0f}", help="Ingresá cotización para incluir USD")
    with col4:
        delta_color = "normal" if saldo >= 0 else "inverse"
        st.metric("💼 Saldo disponible", f"${saldo:,.0f}", delta=f"{'✅' if saldo >= 0 else '❌'}")

    if not dolar and total_usd_global > 0:
        st.info("💡 Ingresá la cotización del dólar para sumar los consumos en USD al total final.")

    # ------------------------
    # DEUDA POR BANCO
    # ------------------------
    st.markdown("---")
    st.subheader("🏦 Deuda por banco")

    total_global = sum(totales_por_banco.values())

    col_tabla, col_grafico = st.columns([1, 2])

    with col_tabla:
        for banco, monto in totales_por_banco.items():
            porcentaje = (monto / total_global) * 100 if total_global > 0 else 0
            st.metric(banco, f"${monto:,.0f}", delta=f"{porcentaje:.1f}% del total")

    with col_grafico:
        df_bancos = pd.DataFrame(
            list(totales_por_banco.items()),
            columns=["Banco", "Monto"]
        )
        st.bar_chart(df_bancos.set_index("Banco"))

    # ------------------------
    # CUOTAS
    # ------------------------
    st.markdown("---")
    st.subheader("💳 Cuotas detectadas")

    if todas_cuotas:
        df_cuotas = pd.DataFrame(todas_cuotas)

        # Ordenar por cuotas restantes
        df_cuotas = df_cuotas.sort_values("Cuotas restantes", ascending=True)

        st.dataframe(df_cuotas, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"**Compras en cuotas detectadas:** {len(df_cuotas)}")
        with col_b:
            proximas = df_cuotas[df_cuotas["Cuotas restantes"] <= 2]
            if not proximas.empty:
                st.warning(f"⚠️ {len(proximas)} compra(s) con 2 cuotas o menos restantes")
    else:
        st.info("No se detectaron cuotas en los resúmenes.")

elif archivos and not sueldo:
    st.warning("⚠️ Ingresá tu sueldo mensual para ver el análisis completo.")
