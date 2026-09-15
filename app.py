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

import pandas as pd
import numpy as np
import io
import os
from google.colab import files

# Instalar ReportLab si no está presente
!pip install reportlab

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

print("="*75)
print(" SISTEMA AUTOMATIZADO: REPORTE 2 (CÁLCULOS AUDITADOS Y CORREGIDOS) ")
print("="*75)

# -------------------------------------------------------------
# FUNCIÓN MANUAL: Encabezado y Pie de Página Institucional
# -------------------------------------------------------------
def encabezado_y_pie_institucional(canvas, doc):
    canvas.saveState()

    # --- ENCABEZADO ---
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(colors.HexColor('#2c3e50'))
    canvas.drawString(36, 762, "@profealvaro.cl — Ensayos SIMCE")

    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#7f8c8d'))
    canvas.drawRightString(576, 762, "Colegio DEMO - 8° Básico")

    # Línea divisoria del encabezado
    canvas.setStrokeColor(colors.HexColor('#bdc3c7'))
    canvas.setLineWidth(0.5)
    canvas.line(36, 754, 576, 754)

    # --- PIE DE PÁGINA ---
    canvas.line(36, 42, 576, 42) # Línea divisoria del pie

    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#7f8c8d'))
    canvas.drawString(36, 30, "Elaborado por: Alvaro Rene Ruiz Aguilera")

    # Número de página dinámico
    num_pagina = canvas.getPageNumber()
    canvas.drawRightString(576, 30, f"Página {num_pagina}")

    canvas.restoreState()


# -------------------------------------------------------------
# PASO 1: Carga de Archivos Maestros y Complementarios
# -------------------------------------------------------------
print("\n[PASO 1/4] Sube tu archivo principal 'Tabla_Atributos_Historia_8vo_1.txt':")
subidos_attr = files.upload()
nombre_attr = list(subidos_attr.keys())[0]
df_atributos = pd.read_csv(io.BytesIO(subidos_attr[nombre_attr]), sep='\t')
print(f"-> ¡Tabla de atributos cargada! Registros: {len(df_atributos)}")

print("\n[PASO 2/4] Sube tu Tabla Complementaria de Preguntas con Alternativas ('Ensayo_Preguntas_8Basico.txt')[cite: 1]:")
subidos_comp = files.upload()
nombre_comp = list(subidos_comp.keys())[0]
df_complementaria = pd.read_csv(io.BytesIO(subidos_comp[nombre_comp]), sep='\t')
print(f"-> ¡Tabla complementaria cargada! Registros: {len(df_complementaria)}")

print("\n[PASO 3/4] Selecciona el formato de las respuestas de los estudiantes:")
print("  [1] Formato Vertical (ZipGrade): Columnas -> estudiante_id | N° | respuesta_estudiante")
print("  [2] Formato Horizontal (Google Forms): Columnas -> estudiante_id | 1 | 2 | 3 | ... | 40")
opcion_formato = input("Ingresa tu opción (1 o 2): ").strip()

print("\nSube tu archivo de respuestas de los estudiantes:")
subidos_resp = files.upload()
nombre_resp = list(subidos_resp.keys())[0]
df_respuestas_raw = pd.read_csv(io.BytesIO(subidos_resp[nombre_resp]), sep='\t')

# -------------------------------------------------------------
# PASO 2: Normalización y Cruce Matemático Auditado
# -------------------------------------------------------------
if opcion_formato == '1':
    df_respuestas = df_respuestas_raw.copy()
    df_respuestas.columns = [c.strip().lower() for c in df_respuestas.columns]
    if 'n°' in df_respuestas.columns:
        df_respuestas.rename(columns={'n°': 'N°'}, inplace=True)
    elif 'n' in df_respuestas.columns:
        df_respuestas.rename(columns={'n': 'N°'}, inplace=True)
elif opcion_formato == '2':
    id_col = df_respuestas_raw.columns[0]
    df_respuestas = df_respuestas_raw.melt(
        id_vars=[id_col],
        var_name='N°',
        value_name='respuesta_estudiante'
    )
    df_respuestas.rename(columns={id_col: 'estudiante_id'}, inplace=True)
else:
    raise ValueError("Opción inválida. Ejecuta la celda nuevamente y selecciona 1 o 2.")

# Normalizar columnas de la tabla complementaria
df_complementaria.columns = [c.strip().lower() for c in df_complementaria.columns]
if 'numero' in df_complementaria.columns:
    df_complementaria.rename(columns={'numero': 'N°'}, inplace=True)
elif 'n°' in df_complementaria.columns:
    df_complementaria.rename(columns={'n°': 'N°'}, inplace=True)

# Compatibilidad de tipos
df_respuestas['N°'] = pd.to_numeric(df_respuestas['N°'])
df_atributos['N°'] = pd.to_numeric(df_atributos['N°'])
df_complementaria['N°'] = pd.to_numeric(df_complementaria['N°'])

df_respuestas['respuesta_estudiante'] = df_respuestas['respuesta_estudiante'].astype(str).str.strip().str.upper()
df_atributos['Opción'] = df_atributos['Opción'].astype(str).str.strip().str.upper()

# 1. Extraer las claves correctas oficiales de la tabla de atributos
df_claves = df_atributos[df_atributos['Estado'].astype(str).str.strip().str.lower() == 'clave'][['N°', 'Opción']].rename(columns={'Opción': 'clave_oficial'})

# 2. Obtener metadatos únicos por pregunta (Eje y Habilidad)
df_metadatos = df_atributos[['N°', 'Eje Curricular', 'Habilidad Medida']].drop_duplicates(subset=['N°'])

# 3. Construir la base de evaluación unificada para CADA respuesta de estudiante
df_cruce = pd.merge(df_respuestas, df_metadatos, on='N°', how='left')
df_cruce = pd.merge(df_cruce, df_claves, on='N°', how='left')

# 4. Evaluación binaria estricta (1 si coincide con la clave oficial, 0 si no)
df_cruce['es_correcta'] = (df_cruce['respuesta_estudiante'] == df_cruce['clave_oficial']).astype(int)
print("-> ¡Cruce y auditoría matemática de respuestas completados con éxito!")

# -------------------------------------------------------------
# PASO 3: Generación del Reporte 2 en PDF
# -------------------------------------------------------------
carpeta_reportes = "reportes_salida"
if not os.path.exists(carpeta_reportes):
    os.makedirs(carpeta_reportes)

print(f"\n[PASO 4/4] Generando el Reporte 2 Consolidado para UTP y Dirección...")
styles = getSampleStyleSheet()

style_celda = ParagraphStyle(
    'EstiloCeldaTablaInf2',
    parent=styles['Normal'],
    fontSize=8,
    leading=10,
    textColor=colors.HexColor('#2c3e50')
)

style_header_tabla = ParagraphStyle(
    'EstiloHeaderTablaInf2',
    parent=styles['Normal'],
    fontSize=9,
    leading=11,
    textColor=colors.white,
    fontName='Helvetica-Bold'
)

texto_descripcion_inf2 = (
    "<b>Descripción del Informe Ejecutivo:</b> Este documento consolida la visión panorámica del curso para la "
    "Dirección y la Unidad Técnico-Pedagógica (UTP). Presenta el desempeño agregado mediante barras de progreso "
    "por Habilidad y Eje Curricular, el análisis crítico de ítems con texto de alternativas y los rankings "
    "de los estudiantes con mayor logro y atención prioritaria (general, por habilidad y por eje)."
)

pdf_path_2 = os.path.join(carpeta_reportes, "2_Reporte_Consolidado_Curso.pdf")
doc2 = SimpleDocTemplate(pdf_path_2, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=45, bottomMargin=45)
story2 = []

# Título y metadatos
story2.append(Paragraph(f"<b>Informe Ejecutivo: Panorámica General del Curso</b>", styles['Heading1']))
story2.append(Paragraph(f"<b>Destinatario: Dirección y UTP</b><br/><i>Resumen Agregado de Rendimiento, Análisis de Ítems y Rankings</i><br/><br/>", styles['Normal']))
story2.append(Paragraph(texto_descripcion_inf2, styles['Normal']))
story2.append(Spacer(1, 15))

# --- AGREGACIÓN 1: Por Habilidad Medida ---
subtotales_habilidad = df_cruce.groupby('Habilidad Medida').agg(
    correctas=('es_correcta', 'sum'),
    total=('es_correcta', 'count')
).reset_index()
subtotales_habilidad['pct_logro'] = round((subtotales_habilidad['correctas'] / subtotales_habilidad['total']) * 100, 1)

story2.append(Paragraph("<b>1. Desempeño Consolidado por Habilidad Medida</b>", styles['Heading3']))
story2.append(Spacer(1, 4))

elementos_barra_hab = []
for _, row_hab in subtotales_habilidad.iterrows():
    hab_nombre = row_hab['Habilidad Medida']
    pct = row_hab['pct_logro']
    color_barra = '#e74c3c' if pct < 60.0 else '#2980b9'

    ancho_logro = max(2, int(3 * pct))
    ancho_restante = max(2, int(3 * (100 - pct)))

    t_progreso = Table([['']], colWidths=[ancho_logro, ancho_restante])
    t_progreso.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor(color_barra)),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#ecf0f1')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))

    t_fila = Table([
        [Paragraph(f"<b>{hab_nombre}</b>: {pct}% de logro (Correctas: {int(row_hab['correctas'])}/{int(row_hab['total'])})", style_celda)],
        [t_progreso]
    ], colWidths=[540])
    t_fila.setStyle(TableStyle([('BOTTOMPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2)]))
    elementos_barra_hab.append(t_fila)
    elementos_barra_hab.append(Spacer(1, 3))

story2.append(KeepTogether(elementos_barra_hab))
story2.append(Spacer(1, 12))

# --- AGREGACIÓN 2: Por Eje Curricular ---
subtotales_eje_curso = df_cruce.groupby('Eje Curricular').agg(
    correctas=('es_correcta', 'sum'),
    total=('es_correcta', 'count')
).reset_index()
subtotales_eje_curso['pct_logro'] = round((subtotales_eje_curso['correctas'] / subtotales_eje_curso['total']) * 100, 1)

story2.append(Paragraph("<b>2. Desempeño Consolidado por Eje Curricular</b>", styles['Heading3']))
story2.append(Spacer(1, 4))

elementos_barra_eje = []
for _, row_eje in subtotales_eje_curso.iterrows():
    eje_nombre = row_eje['Eje Curricular']
    pct = row_eje['pct_logro']
    color_barra = '#e74c3c' if pct < 60.0 else '#2980b9'

    ancho_logro = max(2, int(3 * pct))
    ancho_restante = max(2, int(3 * (100 - pct)))

    t_progreso = Table([['']], colWidths=[ancho_logro, ancho_restante])
    t_progreso.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor(color_barra)),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#ecf0f1')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))

    t_fila = Table([
        [Paragraph(f"<b>{eje_nombre}</b>: {pct}% de logro (Correctas: {int(row_eje['correctas'])}/{int(row_eje['total'])})", style_celda)],
        [t_progreso]
    ], colWidths=[540])
    t_fila.setStyle(TableStyle([('BOTTOMPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2)]))
    elementos_barra_eje.append(t_fila)
    elementos_barra_eje.append(Spacer(1, 3))

story2.append(KeepTogether(elementos_barra_eje))

# Salto de página explícito
story2.append(PageBreak())

# --- AGREGACIÓN 3: Análisis de Preguntas con Texto Literal de Alternativas ---
analisis_preguntas = df_cruce.groupby(['N°', 'Eje Curricular', 'Habilidad Medida']).agg(
    correctas=('es_correcta', 'sum'),
    total_respuestas=('es_correcta', 'count')
).reset_index()
analisis_preguntas['pct_acierto'] = round((analisis_preguntas['correctas'] / analisis_preguntas['total_respuestas']) * 100, 1)

dict_enunciados = dict(zip(df_complementaria['N°'], df_complementaria['enunciado']))
dict_a = dict(zip(df_complementaria['N°'], df_complementaria['a']))
dict_b = dict(zip(df_complementaria['N°'], df_complementaria['b']))
dict_c = dict(zip(df_complementaria['N°'], df_complementaria['c']))
dict_d = dict(zip(df_complementaria['N°'], df_complementaria['d']))
dict_claves = dict(zip(df_claves['N°'], df_claves['clave_oficial']))

def generar_detalle_alternativas(n_pregunta, df_completo):
    df_p = df_completo[df_completo['N°'] == n_pregunta]
    total_resp = len(df_p)
    if total_resp == 0:
        return "Sin registros de respuestas."

    conteo = df_p['respuesta_estudiante'].value_counts()
    textos_op = {
        'A': dict_a.get(n_pregunta, ''),
        'B': dict_b.get(n_pregunta, ''),
        'C': dict_c.get(n_pregunta, ''),
        'D': dict_d.get(n_pregunta, '')
    }

    clave_correcta_q = dict_claves.get(n_pregunta, '')

    lineas_detalle = []
    for letra in ['A', 'B', 'C', 'D']:
        cant = conteo.get(letra, 0)
        pct = round((cant / total_resp) * 100, 1) if total_resp > 0 else 0.0
        es_cl = (letra == clave_correcta_q)
        tag_estado = "<b>(Clave Correcta)</b>" if es_cl else "(Distractor)"
        txt_alt = textos_op.get(letra, '')
        lineas_detalle.append(f"• <b>Opción {letra}</b> {tag_estado} - <b>{pct}%</b> ({cant} est.): <i>{txt_alt}</i>")

    return "<br/>".join(lineas_detalle)

top_aciertos = analisis_preguntas.sort_values(by='pct_acierto', ascending=False).head(5)
top_errores = analisis_preguntas.sort_values(by='pct_acierto', ascending=True).head(5)

story2.append(Paragraph("<b>3. Análisis de Ítems Críticos y Destacados</b>", styles['Heading3']))
story2.append(Spacer(1, 4))

# -- Top 5 Más Aciertos --
data_aciertos = [
    [Paragraph("<b>Top 5 - Preguntas con Mayor Acierto (Fortalezas del Curso)</b>", style_header_tabla), Paragraph("", style_header_tabla), Paragraph("", style_header_tabla)],
    [Paragraph("<b>N°</b>", style_header_tabla), Paragraph("<b>Enunciado y Desglose Literal de Alternativas</b>", style_header_tabla), Paragraph("<b>% Acierto</b>", style_header_tabla)]
]

for _, row_a in top_aciertos.iterrows():
    n_preg = row_a['N°']
    enunciado_txt = dict_enunciados.get(n_preg, "Enunciado no disponible.")
    detalle_ops = generar_detalle_alternativas(n_preg, df_cruce)

    contenido_celda = (
        f"<b>Pregunta {n_preg}</b> (Logro del Curso: <b>{row_a['pct_acierto']}%</b>)<br/>"
        f"<i>Eje:</i> {row_a['Eje Curricular']} | <i>Habilidad:</i> {row_a['Habilidad Medida']}<br/>"
        f"<b>Enunciado:</b> {enunciado_txt}<br/><br/>"
        f"<b>Distribución y Textos de Opciones:</b><br/>{detalle_ops}"
    )

    data_aciertos.append([
        Paragraph(str(n_preg), style_celda),
        Paragraph(contenido_celda, style_celda),
        Paragraph(f"<b>{row_a['pct_acierto']}%</b>", style_celda)
    ])

t_aciertos = Table(data_aciertos, colWidths=[35, 415, 90])
t_aciertos.setStyle(TableStyle([
    ('SPAN', (0,0), (2,0)),
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
    ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#34495e')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ('TOPPADDING', (0,0), (-1,-1), 4),
    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
]))
story2.append(t_aciertos)
story2.append(Spacer(1, 12))

# -- Top 5 Más Errores --
data_errores = [
    [Paragraph("<b>Top 5 - Preguntas con Mayor Error (Áreas Críticas del Curso)</b>", style_header_tabla), Paragraph("", style_header_tabla), Paragraph("", style_header_tabla)],
    [Paragraph("<b>N°</b>", style_header_tabla), Paragraph("<b>Enunciado y Desglose Literal de Alternativas</b>", style_header_tabla), Paragraph("<b>% Acierto (Crítico)</b>", style_header_tabla)]
]

for _, row_e in top_errores.iterrows():
    n_preg = row_e['N°']
    enunciado_txt = dict_enunciados.get(n_preg, "Enunciado no disponible.")
    detalle_ops = generar_detalle_alternativas(n_preg, df_cruce)

    contenido_celda = (
        f"<b>Pregunta {n_preg}</b> (Logro del Curso: <b>{row_e['pct_acierto']}%</b>)<br/>"
        f"<i>Eje:</i> {row_e['Eje Curricular']} | <i>Habilidad:</i> {row_e['Habilidad Medida']}<br/>"
        f"<b>Enunciado:</b> {enunciado_txt}<br/><br/>"
        f"<b>Distribución y Textos de Opciones:</b><br/>{detalle_ops}"
    )

    data_errores.append([
        Paragraph(str(n_preg), style_celda),
        Paragraph(contenido_celda, style_celda),
        Paragraph(f"<b>{row_e['pct_acierto']}%</b>", style_celda)
    ])

t_errores = Table(data_errores, colWidths=[35, 415, 90])
t_errores.setStyle(TableStyle([
    ('SPAN', (0,0), (2,0)),
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#c0392b')),
    ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#d9534f')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ('TOPPADDING', (0,0), (-1,-1), 4),
    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
]))
story2.append(t_errores)

# Salto de página explícito
story2.append(PageBreak())

# --- AGREGACIÓN 4: Rankings de Estudiantes ---
story2.append(Paragraph("<b>4. Rankings de Estudiantes (Extremos de Rendimiento)</b>", styles['Heading3']))
story2.append(Spacer(1, 4))

# 4.1 General
df_est_gen = df_cruce.groupby('estudiante_id').agg(
    correctas=('es_correcta', 'sum'),
    total=('es_correcta', 'count')
).reset_index()
df_est_gen['pct_logro'] = round((df_est_gen['correctas'] / df_est_gen['total']) * 100, 1)

top3_gen = df_est_gen.sort_values(by='pct_logro', ascending=False).head(3)
bot3_gen = df_est_gen.sort_values(by='pct_logro', ascending=True).head(3)

data_rank_gen = [[Paragraph("<b>Estudiantes - Rendimiento General (Mayor Logro y Atención Prioritaria)</b>", style_header_tabla), Paragraph("", style_header_tabla), Paragraph("", style_header_tabla)]]
data_rank_gen.append([Paragraph("<b>Categoría</b>", style_header_tabla), Paragraph("<b>Estudiante (ID)</b>", style_header_tabla), Paragraph("<b>% Logro General</b>", style_header_tabla)])

for _, r in top3_gen.iterrows():
    data_rank_gen.append([Paragraph("Top 3 (Mayor Logro)", style_celda), Paragraph(str(r['estudiante_id']), style_celda), Paragraph(f"<b>{r['pct_logro']}%</b>", style_celda)])
for _, r in bot3_gen.iterrows():
    data_rank_gen.append([Paragraph("Atención Prioritaria", style_celda), Paragraph(str(r['estudiante_id']), style_celda), Paragraph(f"<b>{r['pct_logro']}%</b>", style_celda)])

t_r_gen = Table(data_rank_gen, colWidths=[150, 270, 120])
t_r_gen.setStyle(TableStyle([
    ('SPAN', (0,0), (2,0)),
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
    ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#34495e')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story2.append(KeepTogether(t_r_gen))
story2.append(Spacer(1, 8))

# 4.2 Por Habilidad
df_est_hab = df_cruce.groupby(['Habilidad Medida', 'estudiante_id']).agg(
    correctas=('es_correcta', 'sum'),
    total=('es_correcta', 'count')
).reset_index()
df_est_hab['pct_logro'] = round((df_est_hab['correctas'] / df_est_hab['total']) * 100, 1)

data_rank_hab = [[Paragraph("<b>Estudiantes - Mayor Logro y Atención Prioritaria por Habilidad Medida</b>", style_header_tabla), Paragraph("", style_header_tabla), Paragraph("", style_header_tabla), Paragraph("", style_header_tabla)]]
data_rank_hab.append([Paragraph("<b>Habilidad</b>", style_header_tabla), Paragraph("<b>Categoría</b>", style_header_tabla), Paragraph("<b>Estudiante (ID)</b>", style_header_tabla), Paragraph("<b>% Logro</b>", style_header_tabla)])

for hab in df_est_hab['Habilidad Medida'].unique():
    df_h = df_est_hab[df_est_hab['Habilidad Medida'] == hab]
    t3_h = df_h.sort_values(by='pct_logro', ascending=False).head(3)
    b3_h = df_h.sort_values(by='pct_logro', ascending=True).head(3)

    for _, r in t3_h.iterrows():
        data_rank_hab.append([Paragraph(hab, style_celda), Paragraph("Top 3 (Mayor Logro)", style_celda), Paragraph(str(r['estudiante_id']), style_celda), Paragraph(f"<b>{r['pct_logro']}%</b>", style_celda)])
    for _, r in b3_h.iterrows():
        data_rank_hab.append([Paragraph(hab, style_celda), Paragraph("Atención Prioritaria", style_celda), Paragraph(str(r['estudiante_id']), style_celda), Paragraph(f"<b>{r['pct_logro']}%</b>", style_celda)])

t_r_hab = Table(data_rank_hab, colWidths=[150, 110, 180, 100])
t_r_hab.setStyle(TableStyle([
    ('SPAN', (0,0), (3,0)),
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
    ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#34495e')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story2.append(KeepTogether(t_r_hab))
story2.append(Spacer(1, 8))

# 4.3 Por Eje Curricular
df_est_eje = df_cruce.groupby(['Eje Curricular', 'estudiante_id']).agg(
    correctas=('es_correcta', 'sum'),
    total=('es_correcta', 'count')
).reset_index()
df_est_eje['pct_logro'] = round((df_est_eje['correctas'] / df_est_eje['total']) * 100, 1)

data_rank_eje = [[Paragraph("<b>Estudiantes - Mayor Logro y Atención Prioritaria por Eje Curricular</b>", style_header_tabla), Paragraph("", style_header_tabla), Paragraph("", style_header_tabla), Paragraph("", style_header_tabla)]]
data_rank_eje.append([Paragraph("<b>Eje Curricular</b>", style_header_tabla), Paragraph("<b>Categoría</b>", style_header_tabla), Paragraph("<b>Estudiante (ID)</b>", style_header_tabla), Paragraph("<b>% Logro</b>", style_header_tabla)])

for eje in df_est_eje['Eje Curricular'].unique():
    df_e = df_est_eje[df_est_eje['Eje Curricular'] == eje]
    t3_e = df_e.sort_values(by='pct_logro', ascending=False).head(3)
    b3_e = df_e.sort_values(by='pct_logro', ascending=True).head(3)

    for _, r in t3_e.iterrows():
        data_rank_eje.append([Paragraph(eje, style_celda), Paragraph("Top 3 (Mayor Logro)", style_celda), Paragraph(str(r['estudiante_id']), style_celda), Paragraph(f"<b>{r['pct_logro']}%</b>", style_celda)])
    for _, r in b3_e.iterrows():
        data_rank_eje.append([Paragraph(eje, style_celda), Paragraph("Atención Prioritaria", style_celda), Paragraph(str(r['estudiante_id']), style_celda), Paragraph(f"<b>{r['pct_logro']}%</b>", style_celda)])

t_r_eje = Table(data_rank_eje, colWidths=[150, 110, 180, 100])
t_r_eje.setStyle(TableStyle([
    ('SPAN', (0,0), (3,0)),
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
    ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#34495e')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story2.append(KeepTogether(t_r_eje))

# Construir documento PDF aplicando el encabezado y pie de página institucional
doc2.build(
    story2,
    onFirstPage=encabezado_y_pie_institucional,
    onLaterPages=encabezado_y_pie_institucional
)

print("="*65)
print(" ¡INFORME 2 RECALCULADO Y GENERADO EXITOSAMENTE! ")
print("="*65)
print(f"Archivo generado: {pdf_path_2}")

files.download(pdf_path_2)

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

        response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
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
