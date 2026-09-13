import streamlit as st
import pandas as pd
import numpy as np
import io
import os
from google import genai

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuración de la página web
st.set_page_config(page_title="Sistema SIMCE - Informes Escolares", page_icon="📊", layout="centered")

st.title("📊 Sistema Automatizado de Informes SIMCE")
st.markdown("Plataforma oficial para generación de reportes individuales y retroalimentación pedagógica.")

# --- BARRA LATERAL ---
st.sidebar.header("Configuración de Acceso")
api_key_input = st.sidebar.text_input("Gemini API Key:", type="password", placeholder="Ingresa tu clave")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Consejo:** Asegúrate de subir tus archivos de atributos y respuestas en formato `.txt` o `.csv` tabulado.")

# --- PASO 1: CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    archivo_attr = st.file_uploader("1. Tabla de Atributos", type=["txt", "csv"])
with col2:
    archivo_resp = st.file_uploader("2. Respuestas de Estudiantes", type=["txt", "csv"])

formato_opcion = st.selectbox("Selecciona el formato de respuestas:", ["Formato Vertical (ZipGrade)", "Formato Horizontal (Google Forms)"])

# Función de respaldo inteligente
def generar_recomendacion_respaldo(correctas, incorrectas, subtotales_eje):
    total = correctas + incorrectas
    pct = round((correctas / total) * 100, 1) if total > 0 else 0
    ejes_bajos = subtotales_eje[subtotales_eje['pct_logro'] < 60.0]['Eje Curricular'].tolist()
    
    if pct >= 60:
        texto = f"Excelente desempeño general con un {pct}% de logro ({correctas} correctas de {total}). El/la estudiante demuestra un dominio sólido de los contenidos evaluados. Se le sugiere mantener sus hábitos de estudio y profundizar en lectura crítica."
    else:
        ejes_txt = ", ".join(ejes_bajos) if ejes_bajos else "los ejes descendidos"
        texto = f"El/la estudiante obtuvo un {pct}% de logro ({correctas} correctas y {incorrectas} incorrectas). Se observa la necesidad de enfocar el estudio en {ejes_txt}. Se recomienda realizar lecturas guiadas y revisar los errores conceptuales detectados."
    return texto

# Función de IA masiva
def generar_recomendaciones_masivas(df_cruce_global, api_key):
    diccionario_resultado = {}
    try:
        client = genai.Client(api_key=api_key)
        resumen_curso = {}
        for est in df_cruce_global['estudiante_id'].unique():
            df_e = df_cruce_global[df_cruce_global['estudiante_id'] == est]
            correctas = int(df_e['es_correcta'].sum())
            incorrectas = int(len(df_e) - correctas)
            
            ejes_est = df_e.groupby('Eje Curricular').agg(
                correctas=('es_correcta', 'sum'),
                total=('es_correcta', 'count')
            ).reset_index()
            ejes_est['pct_logro'] = round((ejes_est['correctas'] / ejes_est['total']) * 100, 1)
            
            resumen_curso[str(est)] = {
                "correctas": correctas,
                "incorrectas": incorrectas,
                "rendimiento_ejes": ejes_est[['Eje Curricular', 'pct_logro']].to_dict(orient="records")
            }

        prompt = f"""
        Actúa como un profesor asesor experto en la prueba SIMCE en Chile.
        Te voy a entregar un resumen de datos de un curso. 
        Para CADA estudiante, redacta una retroalimentación pedagógica motivadora y breve (máximo 2 párrafos) con su desempeño y consejos de estudio.

        FORMATO OBLIGATORIO: 
        Responde estrictamente usando este formato de separación por líneas, sin markdown extra:
        ---ESTUDIANTE: [ID_DEL_ESTUDIANTE]---
        [Texto de la recomendación]

        Datos del curso:
        {resumen_curso}
        """

        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        bloques = response.text.strip().split("---ESTUDIANTE:")
        
        for bloque in bloques:
            if "---" in bloque:
                partes = bloque.split("---")
                est_id = partes[0].strip()
                recomendacion = partes[1].strip()
                if est_id:
                    diccionario_resultado[est_id] = recomendacion
    except Exception as e:
        st.sidebar.warning(f"Aviso de IA: {e}. Usando modo de respaldo analítico.")

    for est in df_cruce_global['estudiante_id'].unique():
        if str(est) not in diccionario_resultado or len(diccionario_resultado[str(est)]) < 10:
            df_e = df_cruce_global[df_cruce_global['estudiante_id'] == est]
            c = int(df_e['es_correcta'].sum())
            i = int(len(df_e) - c)
            sub_eje = df_e.groupby('Eje Curricular').agg(correctas=('es_correcta', 'sum'), total=('es_correcta', 'count')).reset_index()
            sub_eje['pct_logro'] = round((sub_eje['correctas'] / sub_eje['total']) * 100, 1)
            diccionario_resultado[str(est)] = generar_recomendacion_respaldo(c, i, sub_eje)
            
    return diccionario_resultado

# --- BOTÓN DE ACCIÓN ---
if st.button("🚀 Procesar Curso y Generar Informes PDF", type="primary"):
    if not api_key_input:
        st.error("Por favor, ingresa tu API Key de Gemini en la barra lateral.")
    elif not archivo_attr or not archivo_resp:
        st.error("Por favor, sube ambos archivos necesarios.")
    else:
        with st.spinner("Procesando datos del curso y compilando informes PDF..."):
            try:
                df_atributos = pd.read_csv(archivo_attr, sep='\t')
                df_respuestas_raw = pd.read_csv(archivo_resp, sep='\t')
                
                if "Vertical" in formato_opcion:
                    df_respuestas = df_respuestas_raw.copy()
                    df_respuestas.columns = [c.strip().lower() for c in df_respuestas.columns]
                    if 'n°' in df_respuestas.columns: df_respuestas.rename(columns={'n°': 'N°'}, inplace=True)
                    elif 'n' in df_respuestas.columns: df_respuestas.rename(columns={'n': 'N°'}, inplace=True)
                else:
                    id_col = df_respuestas_raw.columns[0]
                    df_respuestas = df_respuestas_raw.melt(id_vars=[id_col], var_name='N°', value_name='respuesta_estudiante')
                    df_respuestas.rename(columns={id_col: 'estudiante_id'}, inplace=True)
                
                df_respuestas['N°'] = pd.to_numeric(df_respuestas['N°'])
                df_atributos['N°'] = pd.to_numeric(df_atributos['N°'])
                df_respuestas['respuesta_estudiante'] = df_respuestas['respuesta_estudiante'].astype(str).str.strip().str.upper()
                df_atributos['Opción'] = df_atributos['Opción'].astype(str).str.strip().str.upper()

                df_cruce = pd.merge(df_respuestas, df_atributos, left_on=['N°', 'respuesta_estudiante'], right_on=['N°', 'Opción'], how='left')
                df_cruce['es_correcta'] = df_cruce['Estado'].apply(lambda x: 1 if str(x).strip().lower() == 'clave' else 0)
                df_cruce['Análisis Pedagógico / Diagnóstico del Error'] = df_cruce['Análisis Pedagógico / Diagnóstico del Error'].fillna('Respuesta no registrada.')
                df_cruce['Actividad Sugerida de Remediación'] = df_cruce['Actividad Sugerida de Remediación'].fillna('Revisar contenidos generales.')

                diccionario_ia = generar_recomendaciones_masivas(df_cruce, api_key_input)

                pdf_output_path = "1_Reporte_Detallado_Estudiantes.pdf"
                doc1 = SimpleDocTemplate(pdf_output_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
                story1 = []
                styles = getSampleStyleSheet()

                style_celda = ParagraphStyle('EstiloCelda', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#2c3e50'))
                style_header_tabla = ParagraphStyle('EstiloHeader', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.white, fontName='Helvetica-Bold')
                texto_desc = "<b>Descripción del Informe:</b> Desempeño individual del estudiante con recomendaciones personalizadas, subtotales y gráficos de logro por eje."

                estudiantes = df_cruce['estudiante_id'].unique()
                for idx, estudiante in enumerate(estudiantes):
                    story1.append(Paragraph("<b>Informe Individual: Detalle por Estudiante y Pregunta</b>", styles['Heading1']))
                    story1.append(Paragraph(f"<b>Estudiante: {estudiante}</b><br/><i>Destinatario: Estudiante, Apoderado, Profesor Jefe y UTP</i><br/><br/>", styles['Normal']))
                    story1.append(Paragraph(texto_desc, styles['Normal']))
                    story1.append(Spacer(1, 10))

                    data_est = [[Paragraph("N°", style_header_tabla), Paragraph("Respuesta", style_header_tabla), Paragraph("Estado", style_header_tabla), Paragraph("Análisis Pedagógico y Remediación", style_header_tabla)]]
                    df_est = df_cruce[df_cruce['estudiante_id'] == estudiante].sort_values(by='N°')
                    
                    for _, row in df_est.iterrows():
                        estado_txt = "<b>CORRECTA</b>" if row['es_correcta'] == 1 else "<b>INCORRECTA</b>"
                        detalles_texto = f"<b>Diag:</b> {row['Análisis Pedagógico / Diagnóstico del Error']}<br/><b>Remediación:</b> {row['Actividad Sugerida de Remediación']}"
                        data_est.append([Paragraph(str(row['N°']), style_celda), Paragraph(str(row['respuesta_estudiante']), style_celda), Paragraph(estado_txt, style_celda), Paragraph(detalles_texto, style_celda)])

                    t_est = Table(data_est, colWidths=[30, 60, 75, 375])
                    t_est.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
                    story1.append(t_est)
                    story1.append(Spacer(1, 10))

                    total_c = int(df_est['es_correcta'].sum())
                    total_i = int(len(df_est) - total_c)
                    subtotales_eje = df_est.groupby('Eje Curricular').agg(correctas=('es_correcta', 'sum'), total=('es_correcta', 'count')).reset_index()
                    subtotales_eje['incorrectas'] = subtotales_eje['total'] - subtotales_eje['correctas']
                    subtotales_eje['pct_logro'] = round((subtotales_eje['correctas'] / subtotales_eje['total']) * 100, 1)

                    data_sub = [[Paragraph("<b>Subtotales Generales y por Eje Curricular</b>", style_header_tabla), "", ""]]
                    data_sub.append([Paragraph(f"<b>Total General:</b> Correctas: {total_c} | Incorrectas: {total_i} (Total: {len(df_est)})", style_celda), "", ""])
                    for _, rs in subtotales_eje.iterrows():
                        data_sub.append([Paragraph(f"<b>Eje - {rs['Eje Curricular']}:</b> Correctas: {int(rs['correctas'])} | Incorrectas: {int(rs['incorrectas'])}", style_celda), "", ""])

                    t_sub = Table(data_sub, colWidths=[180, 180, 180])
                    t_sub.setStyle(TableStyle([('SPAN', (0,0), (2,0)), ('SPAN', (0,1), (2,1)), ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#34495e')), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
                    story1.append(t_sub)
                    story1.append(Spacer(1, 10))

                    elementos_barra = [Paragraph("<b>Porcentaje de Logro por Eje Curricular (Estudiante)</b>", styles['Heading3']), Spacer(1, 4)]
                    for _, re in subtotales_eje.iterrows():
                        pct = re['pct_logro']
                        color_b = '#e74c3c' if pct < 60.0 else '#2980b9'
                        t_vis = Table([['']], colWidths=[max(2, int(3 * pct)), max(2, int(3 * (100 - pct)))])
                        t_vis.setStyle(TableStyle([('BACKGROUND', (0,0), (0,0), colors.HexColor(color_b)), ('BACKGROUND', (1,0), (1,0), colors.HexColor('#ecf0f1'))]))
                        t_fila = Table([[Paragraph(f"<b>{re['Eje Curricular']}</b>: {pct}%", style_celda)], [t_vis]], colWidths=[540])
                        elementos_barra.append(t_fila)
                        elementos_barra.append(Spacer(1, 4))
                    story1.append(KeepTogether(elementos_barra))
                    story1.append(Spacer(1, 10))

                    story1.append(Paragraph("<b>Orientación Pedagógica Personalizada</b>", styles['Heading3']))
                    story1.append(Spacer(1, 3))
                    txt_ia = diccionario_ia.get(str(estudiante), "Desempeño registrado.")
                    t_ia = Table([[Paragraph(str(txt_ia).replace('\n', '<br/>'), style_celda)]], colWidths=[540])
                    t_ia.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#2980b9')), ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f8ff'))]))
                    story1.append(t_ia)
                    story1.append(Spacer(1, 10))

                    ejes_ref = subtotales_eje[subtotales_eje['pct_logro'] < 60.0]['Eje Curricular'].tolist()
                    txt_ref = f"<b>Designación de Reforzamiento:</b> Zonas con < 60%: <b>{', '.join(ejes_ref)}</b>.<br/><br/>" if ejes_ref else "<b>Designación de Reforzamiento:</b> Logros satisfactorios (>= 60%).<br/><br/>"
                    t_obs = Table([[Paragraph(f"{txt_ref}<i>Comentarios adicionales:</i><br/><br/><br/><br/><br/>", style_celda)]], colWidths=[540])
                    t_obs.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f9f9f9'))]))
                    
                    bloque_cierre = [Paragraph("<b>Observaciones para el Apoderado:</b>", styles['Normal']), Spacer(1, 4), t_obs, Spacer(1, 30),
                                     Table([[Paragraph("___________________________________<br/><b>Profesor Jefe</b>", style_celda), Paragraph("___________________________________<br/><b>UTP</b>", style_celda)]], colWidths=[270, 270], style=[('ALIGN', (0,0), (-1,-1), 'CENTER')])]
                    story1.append(KeepTogether(bloque_cierre))

                    if idx < len(estudiantes) - 1:
                        story1.append(PageBreak())

                doc1.build(story1)
                
                st.success("¡Informes generados exitosamente!")
                
                with open(pdf_output_path, "rb") as f:
                    st.download_button(
                        label="📥 Descargar PDF Consolidado del Curso",
                        data=f,
                        file_name="Reportes_SIMCE_Estudiantes.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
            except Exception as e:
                st.error(f"Error durante el procesamiento: {e}")