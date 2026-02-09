import os
import logging
from datetime import datetime, date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.models.models import VentaHistorico, CompraHistorico, Producto, ReporteGenerado, ClienteFinal

logger = logging.getLogger(__name__)

HEADER_FONT = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
CURRENCY_FORMAT = '#,##0'
THIN_BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)
TITLE_FONT = Font(name="Calibri", bold=True, size=14, color="2F5496")
SUBTITLE_FONT = Font(name="Calibri", bold=True, size=11, color="404040")


def _style_header(ws, row, col_count):
    for col in range(1, col_count + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER


def _auto_width(ws):
    for col in ws.columns:
        max_length = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_length + 4, 40)


def generate_daily_report(db: Session, report_date: date = None) -> str:
    if report_date is None:
        report_date = date.today()

    wb = Workbook()

    ws_resumen = wb.active
    ws_resumen.title = "Resumen de Ventas"
    ws_resumen.cell(row=1, column=1, value="Reporte Diario - Gabriel Hoyos").font = TITLE_FONT
    ws_resumen.cell(row=2, column=1, value=f"Fecha: {report_date.strftime('%d/%m/%Y')}").font = SUBTITLE_FONT
    ws_resumen.merge_cells("A1:F1")
    ws_resumen.merge_cells("A2:F2")

    headers_ventas = ["Cliente", "Folio", "Tipo Doc.", "Neto", "IVA", "Total", "Costo", "Margen"]
    row_start = 4
    for i, h in enumerate(headers_ventas, 1):
        ws_resumen.cell(row=row_start, column=i, value=h)
    _style_header(ws_resumen, row_start, len(headers_ventas))

    ventas = db.query(VentaHistorico).filter(
        func.date(VentaHistorico.fecha) == report_date
    ).all()

    row = row_start + 1
    total_neto = 0
    total_iva = 0
    total_total = 0
    total_costo = 0
    total_margen = 0

    for v in ventas:
        cliente_nombre = ""
        if v.cliente_id:
            cliente = db.query(ClienteFinal).filter(ClienteFinal.id == v.cliente_id).first()
            cliente_nombre = cliente.nombre if cliente else ""

        ws_resumen.cell(row=row, column=1, value=cliente_nombre)
        ws_resumen.cell(row=row, column=2, value=v.folio)
        ws_resumen.cell(row=row, column=3, value=v.tipo_documento)
        ws_resumen.cell(row=row, column=4, value=v.subtotal or 0).number_format = CURRENCY_FORMAT
        ws_resumen.cell(row=row, column=5, value=v.impuestos or 0).number_format = CURRENCY_FORMAT
        ws_resumen.cell(row=row, column=6, value=v.total or 0).number_format = CURRENCY_FORMAT
        ws_resumen.cell(row=row, column=7, value=v.costo_total or 0).number_format = CURRENCY_FORMAT
        ws_resumen.cell(row=row, column=8, value=v.margen_neto or 0).number_format = CURRENCY_FORMAT

        for col in range(1, len(headers_ventas) + 1):
            ws_resumen.cell(row=row, column=col).border = THIN_BORDER

        total_neto += v.subtotal or 0
        total_iva += v.impuestos or 0
        total_total += v.total or 0
        total_costo += v.costo_total or 0
        total_margen += v.margen_neto or 0
        row += 1

    row += 1
    ws_resumen.cell(row=row, column=3, value="TOTALES").font = Font(bold=True)
    ws_resumen.cell(row=row, column=4, value=total_neto).number_format = CURRENCY_FORMAT
    ws_resumen.cell(row=row, column=5, value=total_iva).number_format = CURRENCY_FORMAT
    ws_resumen.cell(row=row, column=6, value=total_total).number_format = CURRENCY_FORMAT
    ws_resumen.cell(row=row, column=7, value=total_costo).number_format = CURRENCY_FORMAT
    ws_resumen.cell(row=row, column=8, value=total_margen).number_format = CURRENCY_FORMAT
    for col in range(3, len(headers_ventas) + 1):
        ws_resumen.cell(row=row, column=col).font = Font(bold=True)
        ws_resumen.cell(row=row, column=col).border = THIN_BORDER

    _auto_width(ws_resumen)

    ws_utilidad = wb.create_sheet("Utilidad Neta")
    ws_utilidad.cell(row=1, column=1, value="Utilidad Neta del Día").font = TITLE_FONT
    ws_utilidad.cell(row=2, column=1, value=f"Fecha: {report_date.strftime('%d/%m/%Y')}").font = SUBTITLE_FONT
    ws_utilidad.merge_cells("A1:D1")

    headers_util = ["Concepto", "Monto ($)"]
    for i, h in enumerate(headers_util, 1):
        ws_utilidad.cell(row=4, column=i, value=h)
    _style_header(ws_utilidad, 4, len(headers_util))

    datos_utilidad = [
        ("Ingresos por Ventas (Neto)", total_neto),
        ("Costo de Ventas", total_costo),
        ("Utilidad Bruta", total_neto - total_costo),
        ("Margen Bruto (%)", f"{((total_neto - total_costo) / total_neto * 100) if total_neto else 0:.1f}%"),
    ]
    for i, (concepto, monto) in enumerate(datos_utilidad, 5):
        ws_utilidad.cell(row=i, column=1, value=concepto)
        cell = ws_utilidad.cell(row=i, column=2, value=monto)
        if isinstance(monto, (int, float)):
            cell.number_format = CURRENCY_FORMAT
        ws_utilidad.cell(row=i, column=1).border = THIN_BORDER
        ws_utilidad.cell(row=i, column=2).border = THIN_BORDER

    _auto_width(ws_utilidad)

    ws_stock = wb.create_sheet("Alertas de Stock")
    ws_stock.cell(row=1, column=1, value="Alertas de Stock Bajo").font = TITLE_FONT
    ws_stock.merge_cells("A1:D1")

    headers_stock = ["Producto", "SKU", "Stock Actual", "Stock Mínimo"]
    for i, h in enumerate(headers_stock, 1):
        ws_stock.cell(row=3, column=i, value=h)
    _style_header(ws_stock, 3, len(headers_stock))

    productos_bajo_stock = db.query(Producto).filter(
        Producto.stock_actual <= Producto.stock_minimo,
        Producto.activo == True
    ).all()

    for i, p in enumerate(productos_bajo_stock, 4):
        ws_stock.cell(row=i, column=1, value=p.nombre)
        ws_stock.cell(row=i, column=2, value=p.sku)
        ws_stock.cell(row=i, column=3, value=p.stock_actual)
        ws_stock.cell(row=i, column=4, value=p.stock_minimo)
        for col in range(1, 5):
            ws_stock.cell(row=i, column=col).border = THIN_BORDER

    if not productos_bajo_stock:
        ws_stock.cell(row=4, column=1, value="No hay productos con stock bajo")

    _auto_width(ws_stock)

    os.makedirs("reports", exist_ok=True)
    filename = f"reporte_diario_{report_date.strftime('%Y%m%d')}.xlsx"
    filepath = os.path.join("reports", filename)
    wb.save(filepath)

    reporte = ReporteGenerado(
        nombre_archivo=filename,
        tipo="diario",
        fecha_reporte=report_date,
        ruta_archivo=filepath,
    )
    db.add(reporte)
    db.commit()

    logger.info(f"Reporte generado: {filepath}")
    return filepath
