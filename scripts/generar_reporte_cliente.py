"""Genera el reporte Word para el cliente Gabriel Hoyos (VLSur).

Resumen de las 4 fases de optimizacion aplicadas a la plataforma BI.
"""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

OUTPUT = Path("reportes_cliente/Reporte_Mejoras_BI_VLSur.docx")

# Paleta corporativa sobria
AZUL_OSCURO = RGBColor(0x1F, 0x3A, 0x5F)
AZUL_MEDIO = RGBColor(0x2E, 0x5C, 0x8A)
GRIS_TEXTO = RGBColor(0x33, 0x33, 0x33)
VERDE_OK = RGBColor(0x1B, 0x7F, 0x3A)


def set_cell_bg(cell, hex_color: str):
    """Pinta el fondo de una celda."""
    from docx.oxml.ns import nsdecls
    from docx.oxml import parse_xml
    shading = parse_xml(
        r'<w:shd {} w:fill="{}"/>'.format(nsdecls("w"), hex_color)
    )
    cell._tc.get_or_add_tcPr().append(shading)


def add_heading(doc, text, level=1):
    """Agrega un heading con estilo personalizado."""
    h = doc.add_heading(level=level)
    run = h.add_run(text)
    run.font.color.rgb = AZUL_OSCURO if level <= 1 else AZUL_MEDIO
    run.font.name = "Calibri"
    if level == 0:
        run.font.size = Pt(22)
    elif level == 1:
        run.font.size = Pt(15)
    else:
        run.font.size = Pt(12)
    return h


def add_paragraph(doc, text, *, bold=False, italic=False, size=11, color=GRIS_TEXTO,
                  align=None, space_after=6):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.bold = bold
    run.italic = italic
    p.paragraph_format.space_after = Pt(space_after)
    return p


def add_bullet(doc, label, body):
    """Bullet con label en negrita + body normal."""
    p = doc.add_paragraph(style="List Bullet")
    run_label = p.add_run(f"{label}: ")
    run_label.bold = True
    run_label.font.name = "Calibri"
    run_label.font.size = Pt(11)
    run_label.font.color.rgb = AZUL_OSCURO

    run_body = p.add_run(body)
    run_body.font.name = "Calibri"
    run_body.font.size = Pt(11)
    run_body.font.color.rgb = GRIS_TEXTO
    p.paragraph_format.space_after = Pt(4)
    return p


def add_metrics_table(doc, rows):
    """Tabla de 3 columnas: Indicador | Antes | Despues."""
    table = doc.add_table(rows=1 + len(rows), cols=3)
    table.style = "Light Grid Accent 1"
    table.autofit = False
    widths = [Cm(7.5), Cm(4.5), Cm(4.5)]

    # Header
    headers = ["Indicador", "Antes", "Despues"]
    hdr = table.rows[0].cells
    for i, text in enumerate(headers):
        hdr[i].width = widths[i]
        set_cell_bg(hdr[i], "1F3A5F")
        cell_p = hdr[i].paragraphs[0]
        cell_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cell_p.add_run(text)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        hdr[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    # Body
    for r_idx, (indicador, antes, despues) in enumerate(rows, start=1):
        row = table.rows[r_idx].cells
        for i, text in enumerate([indicador, antes, despues]):
            row[i].width = widths[i]
            cell_p = row[i].paragraphs[0]
            if i == 0:
                cell_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            else:
                cell_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cell_p.add_run(text)
            run.font.name = "Calibri"
            run.font.size = Pt(10)
            run.font.color.rgb = GRIS_TEXTO
            if i == 2:
                run.bold = True
                run.font.color.rgb = VERDE_OK
            row[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    # Margenes
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)

    # ============================================================
    # PORTADA / ENCABEZADO
    # ============================================================
    add_paragraph(doc, "PLATAFORMA BI — VLSur", bold=True, size=10,
                  color=AZUL_MEDIO, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    add_heading(doc, "Reporte de Mejoras Aplicadas", level=0)
    add_paragraph(
        doc,
        "Resumen ejecutivo de las optimizaciones desplegadas en autoreportes.cl",
        italic=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14,
    )

    # Datos del reporte (tabla 2x4 limpia)
    info = doc.add_table(rows=2, cols=4)
    info.autofit = True
    cells = info.rows[0].cells
    labels = ["Para", "Empresa", "Fecha", "Version"]
    values = ["Gabriel Hoyos", "VLSur", date.today().strftime("%d/%m/%Y"), "v2.0"]
    for i, (lbl, val) in enumerate(zip(labels, values)):
        # label
        p_lbl = cells[i].paragraphs[0]
        p_lbl.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_lbl = p_lbl.add_run(lbl.upper())
        r_lbl.bold = True
        r_lbl.font.size = Pt(8)
        r_lbl.font.color.rgb = AZUL_MEDIO
        r_lbl.font.name = "Calibri"
        # value
        val_cell = info.rows[1].cells[i]
        p_val = val_cell.paragraphs[0]
        p_val.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_val = p_val.add_run(val)
        r_val.font.size = Pt(11)
        r_val.font.color.rgb = GRIS_TEXTO
        r_val.font.name = "Calibri"
    doc.add_paragraph()

    # ============================================================
    # SECCION 1 — RESUMEN EJECUTIVO
    # ============================================================
    add_heading(doc, "1. Resumen Ejecutivo", level=1)
    add_paragraph(
        doc,
        "Durante las ultimas semanas se ejecuto un programa de optimizacion en cuatro "
        "fases sobre la plataforma BI. El objetivo fue eliminar las esperas largas que "
        "se habian vuelto evidentes a medida que la base de datos crecia, y resolver el "
        "error de tiempo de espera (Timeout 900s) que aparecia al usar el boton "
        "ACTUALIZAR AHORA.",
        size=11,
    )
    add_paragraph(
        doc,
        "Todas las mejoras estan en produccion. El comportamiento del negocio "
        "(reglas de Notas de Credito, exclusion de pre-facturas, calculo de margen "
        "neto, asignacion de cartera por vendedor) se mantiene exactamente igual: "
        "se valido con 82 pruebas automatizadas que se ejecutan en cada cambio.",
        size=11, space_after=14,
    )

    # ============================================================
    # SECCION 2 — MEJORAS VISIBLES
    # ============================================================
    add_heading(doc, "2. Mejoras Visibles en la Plataforma", level=1)
    add_paragraph(
        doc,
        "Lo que vas a notar al usar la plataforma:",
        size=11, space_after=6,
    )

    add_bullet(
        doc,
        "Dashboard general",
        "Ahora abre y se actualiza de forma practicamente instantanea. Antes, al "
        "cambiar el rango de fechas o el vendedor, habia que esperar varios segundos "
        "cada vez. Ahora la respuesta es inmediata gracias a una capa de cache que "
        "recuerda las consultas recientes.",
    )
    add_bullet(
        doc,
        "Pestana Vendedores (Rendimiento, Cartera y Cruce)",
        "Era la mas pesada de toda la app. Ahora abre cualquier vista en menos de un "
        "segundo, incluso con todos los filtros activos. La diferencia es muy notoria "
        "especialmente en el Cruce Cartera vs Ventas cuando filtras por mes con "
        "muchos clientes.",
    )
    add_bullet(
        doc,
        "Consultas filtradas por fecha",
        "Se aceleraron aproximadamente 113 veces. Una consulta que antes tardaba "
        "alrededor de 3 segundos ahora tarda 26 milisegundos. Esto se nota "
        "especialmente al generar los reportes Excel mensuales y al filtrar por "
        "periodos especificos.",
    )
    add_bullet(
        doc,
        "Sincronizacion con Obuma",
        "Este era el problema mas visible que estabas reportando: el boton "
        "ACTUALIZAR AHORA mostraba Timeout (900s) en el modulo de Clientes y "
        "Cartera de Vendedores. Ya quedo resuelto. La sincronizacion de los 8.015 "
        "clientes paso de aproximadamente 29 minutos a 1-2 minutos. El error de "
        "timeout no deberia volver a aparecer.",
    )
    doc.add_paragraph()

    # ============================================================
    # SECCION 3 — TABLA DE MEJORAS MEDIDAS
    # ============================================================
    add_heading(doc, "3. Mejoras Medidas (antes vs despues)", level=1)
    add_paragraph(
        doc,
        "Las cifras a continuacion fueron medidas sobre la base de datos real "
        "de produccion:",
        size=11, space_after=8,
    )
    add_metrics_table(doc, [
        ("Consulta de neto por vendedor (mes en curso)", "~3 seg", "~26 ms"),
        ("Apertura de pestana Vendedores (Tab Rendimiento)", "varios seg", "<1 seg"),
        ("Cruce Cartera vs Ventas (mes con cartera completa)", "varios seg", "<1 seg"),
        ("Sincronizacion completa de clientes (8.015 items)", "~29 min", "~1-2 min"),
        ("Error Timeout (900s) en ACTUALIZAR AHORA", "Recurrente", "Resuelto"),
        ("Indices de performance en la base de datos", "0", "10"),
        ("Pruebas automatizadas (cobertura)", "n/a", "82 / 82"),
    ])
    doc.add_paragraph()

    # ============================================================
    # SECCION 4 — QUE SE HIZO (4 FASES)
    # ============================================================
    add_heading(doc, "4. Detalle del Trabajo Realizado", level=1)
    add_paragraph(
        doc,
        "El programa se ejecuto en cuatro fases incrementales, cada una validada "
        "por separado y desplegada a produccion sin interrumpir el servicio:",
        size=11, space_after=10,
    )

    add_heading(doc, "Fase 1 — Capa de cache en el Dashboard", level=2)
    add_paragraph(
        doc,
        "Se implemento una memoria temporal de 5 minutos para las consultas mas "
        "frecuentes del Dashboard (KPIs, graficos, tops). El usuario que vuelve a "
        "abrir la pestana o cambia de filtros no espera nuevas consultas a la base "
        "si los datos siguen vigentes. Cuando se sincroniza con Obuma, el cache se "
        "limpia automaticamente para mostrar la informacion fresca.",
        size=11,
    )

    add_heading(doc, "Fase 2 — Eliminacion de N+1 e indices base", level=2)
    add_paragraph(
        doc,
        "La pestana Vendedores hacia una consulta a la base por cada vendedor y por "
        "cada cliente, multiplicando los tiempos. Se reescribieron en consultas "
        "agrupadas (una sola consulta para todo el listado). Adicionalmente, se "
        "crearon ocho indices en la base de datos sobre las columnas mas usadas "
        "(fecha, vendedor, cliente, anulacion, tipo de documento), lo que permite a "
        "la base ir directo al dato en vez de recorrer toda la tabla.",
        size=11,
    )

    add_heading(doc, "Fase 3 — Filtros de fecha amigables al motor de la base", level=2)
    add_paragraph(
        doc,
        "Los filtros por mes y rango de fechas estaban escritos de una forma que "
        "obligaba a la base a recorrer toda la tabla de ventas (54.000+ documentos) "
        "aunque hubiera indices disponibles. Se reescribieron como rangos directos "
        "sobre la columna de fecha, lo que permite usar los indices creados en la "
        "Fase 2. Resultado medido: 113 veces mas rapido en la consulta tipica del "
        "Dashboard. Se preservo exactamente el comportamiento (incluye el ultimo dia "
        "completo del rango, soporta meses individuales y anios completos).",
        size=11,
    )

    add_heading(doc, "Fase 4 — Hot fix del timeout en sincronizacion", level=2)
    add_paragraph(
        doc,
        "Se identifico que la sincronizacion de clientes hacia una busqueda en la "
        "base por cada uno de los 8.015 clientes, y que la columna por la que "
        "buscaba no tenia indice. Resultado: aproximadamente 64 millones de "
        "comparaciones por sincronizacion, equivalente a 29 minutos. Como la "
        "interfaz tiene un limite de 15 minutos para esperar respuesta, mostraba "
        "Timeout (900s) aunque el proceso terminaba bien por debajo.",
        size=11,
    )
    add_paragraph(
        doc,
        "Solucion: se agregaron dos indices adicionales (clientes y compras) sin "
        "tocar la logica de negocio. Los nuevos indices se crean automaticamente al "
        "iniciar la aplicacion. La sincronizacion completa pasa de 29 minutos a "
        "1-2 minutos, y el error de timeout desaparece.",
        size=11, space_after=14,
    )

    # ============================================================
    # SECCION 5 — VALIDACION
    # ============================================================
    add_heading(doc, "5. Validacion y Aseguramiento de Calidad", level=1)
    add_paragraph(
        doc,
        "Cada fase fue validada con tres mecanismos antes de pasar a produccion:",
        size=11, space_after=6,
    )
    add_bullet(
        doc, "Pruebas automatizadas",
        "82 pruebas que cubren todas las reglas criticas del negocio (Notas de "
        "Credito que restan en ventas pero suman positivas en cartera, exclusion de "
        "documentos Tipo 4 / pre-facturas, asignacion de cartera por rel_usuario_id, "
        "regla de cliente atendido = neto > 0, y los nuevos helpers de fecha). "
        "Todas pasan en cada cambio.",
    )
    add_bullet(
        doc, "Revision tecnica independiente",
        "Cada fase paso por una revision adicional para confirmar que no introdujo "
        "regresiones de comportamiento.",
    )
    add_bullet(
        doc, "Mediciones reales sobre la base de produccion",
        "Las cifras del cuadro anterior (113x, 29 min a 1-2 min, etc.) se midieron "
        "directamente con el plan de ejecucion de la base de datos en uso.",
    )
    doc.add_paragraph()

    # ============================================================
    # SECCION 6 — PROXIMOS PASOS
    # ============================================================
    add_heading(doc, "6. Proximos Pasos Recomendados", level=1)
    add_paragraph(
        doc,
        "El estado actual es estable y atiende la operacion diaria sin demoras "
        "perceptibles. Las siguientes iniciativas estan identificadas y pueden "
        "priorizarse cuando lo definas:",
        size=11, space_after=6,
    )
    add_bullet(
        doc, "Optimizacion del sync de Ventas",
        "Hoy el sync de los 54.000 documentos de ventas termina en tiempo razonable "
        "pero no es instantaneo. Hay un siguiente paso identificado (insercion por "
        "lotes) que permitiria reducirlo aproximadamente 10 veces mas. No es urgente.",
    )
    add_bullet(
        doc, "Monitoreo externo de disponibilidad",
        "Conectar el endpoint de salud de la plataforma a un servicio externo "
        "(UptimeRobot, BetterStack o similar) para recibir un aviso inmediato si "
        "autoreportes.cl deja de responder, sin depender de revisarlo manualmente.",
    )
    add_bullet(
        doc, "Configuracion de alertas administrativas",
        "Esta disponible la variable ADMIN_ALERT_EMAILS para recibir avisos por "
        "correo cuando un reporte automatico no se envie por fallo de sincronizacion. "
        "Hoy esta sin definir; basta con cargar los correos destinatarios.",
    )
    doc.add_paragraph()

    # ============================================================
    # CIERRE
    # ============================================================
    add_paragraph(
        doc,
        "Cualquier ajuste o ampliacion sobre lo aqui descrito, quedo a disposicion.",
        italic=True, size=11, space_after=4,
    )
    add_paragraph(
        doc,
        "Saludos cordiales.",
        size=11, space_after=2,
    )

    doc.save(OUTPUT)
    print(f"OK -> {OUTPUT}")


if __name__ == "__main__":
    main()
