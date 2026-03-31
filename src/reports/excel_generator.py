import os
import json
import logging
from datetime import datetime, date
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, distinct, case as sql_case
from src.models.models import VentaHistorico, ClienteFinal, Empleado, ReporteGenerado, VendedorCartera

logger = logging.getLogger(__name__)

HEADER_FONT = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
CURRENCY_FORMAT = '#,##0'
PERCENT_FORMAT = '0.00%'
THIN_BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)
TITLE_FONT = Font(name="Calibri", bold=True, size=14, color="2F5496")
SUBTITLE_FONT = Font(name="Calibri", bold=True, size=11, color="404040")

YELLOW_FILL = PatternFill(start_color="FFFFFF00", end_color="FFFFFF00", fill_type="solid")
GREEN_FILL = PatternFill(start_color="FF92D050", end_color="FF92D050", fill_type="solid")
RED_FILL = PatternFill(start_color="FFFF6B6B", end_color="FFFF6B6B", fill_type="solid")
LIGHT_GREEN_FILL = PatternFill(start_color="FFE8F5E9", end_color="FFE8F5E9", fill_type="solid")
LIGHT_RED_FILL = PatternFill(start_color="FFFFEBEE", end_color="FFFFEBEE", fill_type="solid")
SEGMENTO_FONT = Font(name="Calibri", bold=True, size=11)

MONTH_NAMES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

BILLING_DOC_TYPES = ['Factura Electr.', 'Factura Exenta', 'Boleta Electr.']
NC_DOC_TYPES = ['Nota Credito']
VALID_DOC_TYPES = BILLING_DOC_TYPES + NC_DOC_TYPES


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


def _get_last_3_months(reference_date):
    months = []
    year = reference_date.year
    month = reference_date.month
    for _ in range(3):
        month -= 1
        if month <= 0:
            month = 12
            year -= 1
        months.append(month)
    return months


def _classify_segmento(acumulado_pct):
    if acumulado_pct <= 0.80:
        return "A"
    elif acumulado_pct <= 0.95:
        return "B"
    elif acumulado_pct <= 0.99:
        return "C"
    else:
        return "D"


def _classify_riesgo(meses_con_venta, ventas_ultimos_3):
    if meses_con_venta >= 8:
        return "BAJO"
    if meses_con_venta >= 6 and ventas_ultimos_3 > 0:
        return "BAJO"
    if meses_con_venta >= 3 and ventas_ultimos_3 > 0:
        return "MEDIO"
    return "ALTO"


def _resolve_date_range(date_from, date_to):
    if date_from is None and date_to is None:
        current_year = date.today().year
        return date(current_year, 1, 1), date(current_year, 12, 31), False
    if date_from is None:
        date_from = date(date_to.year, 1, 1)
    if date_to is None:
        date_to = date.today()
    return date_from, date_to, True


def _build_cartera_sheet(wb, db, vendedor_obuma_id, empleado, date_from, date_to):
    cartera_entries = db.query(VendedorCartera, ClienteFinal).join(
        ClienteFinal, VendedorCartera.cliente_id == ClienteFinal.id
    ).filter(
        VendedorCartera.empleado_obuma_id == vendedor_obuma_id,
        VendedorCartera.activo == True
    ).all()

    if not cartera_entries:
        return

    compraron = []
    no_compraron = []

    for vc, cli in cartera_entries:
        ventas_result = db.query(
            func.sum(
                sql_case(
                    (VentaHistorico.tipo_documento.in_(NC_DOC_TYPES), -VentaHistorico.subtotal),
                    else_=VentaHistorico.subtotal
                )
            ).label("total_ventas"),
            func.count(VentaHistorico.id).label("num_docs")
        ).filter(
            VentaHistorico.cliente_id == cli.id,
            VentaHistorico.vendedor_id == vendedor_obuma_id,
            VentaHistorico.anulada == False,
            func.date(VentaHistorico.fecha) >= date_from,
            func.date(VentaHistorico.fecha) <= date_to,
            VentaHistorico.tipo_documento.in_(VALID_DOC_TYPES)
        ).first()

        total_ventas = ventas_result.total_ventas or 0
        num_docs = ventas_result.num_docs or 0

        if num_docs > 0:
            compraron.append({
                'nombre': cli.nombre or '',
                'rut': cli.rut or '',
                'total_ventas': total_ventas,
                'num_docs': num_docs,
            })
        else:
            ultima_compra = db.query(func.max(VentaHistorico.fecha)).filter(
                VentaHistorico.cliente_id == cli.id,
                VentaHistorico.vendedor_id == vendedor_obuma_id,
                VentaHistorico.anulada == False
            ).scalar()
            dias_sin = None
            ultima_str = "Sin registro"
            if ultima_compra:
                if hasattr(ultima_compra, 'date'):
                    ultima_date = ultima_compra.date()
                else:
                    ultima_date = ultima_compra
                dias_sin = (date.today() - ultima_date).days
                ultima_str = str(ultima_date)

            no_compraron.append({
                'nombre': cli.nombre or '',
                'rut': cli.rut or '',
                'ultima_compra': ultima_str,
                'dias_sin_comprar': dias_sin,
            })

    compraron.sort(key=lambda x: x['total_ventas'], reverse=True)
    no_compraron.sort(key=lambda x: (x['dias_sin_comprar'] is None, -(x['dias_sin_comprar'] or 0)))

    total_cartera = len(cartera_entries)
    total_compraron = len(compraron)
    total_no_compraron = len(no_compraron)
    cobertura = (total_compraron / total_cartera * 100) if total_cartera > 0 else 0

    GREEN_HEADER = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
    RED_HEADER = PatternFill(start_color="EF4444", end_color="EF4444", fill_type="solid")
    BLUE_HEADER = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")

    ws = wb.create_sheet("Cruce Cartera vs Ventas")

    ws.cell(row=1, column=1, value=f"Cruce Cartera vs Ventas - {empleado.nombre}").font = TITLE_FONT
    ws.merge_cells('A1:F1')
    ws.cell(row=2, column=1, value=f"Periodo: {date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}").font = SUBTITLE_FONT
    ws.merge_cells('A2:F2')

    ws.cell(row=4, column=1, value="Total Cartera")
    ws.cell(row=4, column=2, value=total_cartera)
    ws.cell(row=5, column=1, value="Compraron")
    ws.cell(row=5, column=2, value=total_compraron)
    ws.cell(row=6, column=1, value="No Compraron")
    ws.cell(row=6, column=2, value=total_no_compraron)
    ws.cell(row=7, column=1, value="Cobertura")
    ws.cell(row=7, column=2, value=f"{cobertura:.1f}%")
    for r in range(4, 8):
        ws.cell(row=r, column=1).font = Font(bold=True)
        ws.cell(row=r, column=1).border = THIN_BORDER
        ws.cell(row=r, column=2).border = THIN_BORDER
    ws.cell(row=5, column=2).fill = LIGHT_GREEN_FILL
    ws.cell(row=6, column=2).fill = LIGHT_RED_FILL

    row = 9
    ws.cell(row=row, column=1, value=f"CLIENTES QUE COMPRARON ({total_compraron})").font = Font(bold=True, size=12, color="10B981")
    ws.merge_cells(f'A{row}:D{row}')
    row += 1

    comp_headers = ["N°", "RUT", "Razon Social", "Total Ventas", "Documentos"]
    for i, h in enumerate(comp_headers, 1):
        cell = ws.cell(row=row, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = GREEN_HEADER
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER
    row += 1

    for idx, c in enumerate(compraron, 1):
        ws.cell(row=row, column=1, value=idx).border = THIN_BORDER
        ws.cell(row=row, column=2, value=c['rut']).border = THIN_BORDER
        ws.cell(row=row, column=3, value=c['nombre']).border = THIN_BORDER
        cell = ws.cell(row=row, column=4, value=c['total_ventas'])
        cell.number_format = CURRENCY_FORMAT
        cell.border = THIN_BORDER
        ws.cell(row=row, column=5, value=c['num_docs']).border = THIN_BORDER
        row_fill = LIGHT_RED_FILL if c['total_ventas'] < 0 else LIGHT_GREEN_FILL
        for col in range(1, 6):
            ws.cell(row=row, column=col).fill = row_fill
        if c['total_ventas'] < 0:
            cell.font = Font(name="Calibri", size=11, color="C00000", bold=True)
        row += 1

    row += 1
    ws.cell(row=row, column=1, value=f"CLIENTES QUE NO COMPRARON ({total_no_compraron})").font = Font(bold=True, size=12, color="EF4444")
    ws.merge_cells(f'A{row}:D{row}')
    row += 1

    no_headers = ["N°", "RUT", "Razon Social", "Ultima Compra", "Dias sin Comprar"]
    for i, h in enumerate(no_headers, 1):
        cell = ws.cell(row=row, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = RED_HEADER
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER
    row += 1

    for idx, c in enumerate(no_compraron, 1):
        ws.cell(row=row, column=1, value=idx).border = THIN_BORDER
        ws.cell(row=row, column=2, value=c['rut']).border = THIN_BORDER
        ws.cell(row=row, column=3, value=c['nombre']).border = THIN_BORDER
        ws.cell(row=row, column=4, value=c['ultima_compra']).border = THIN_BORDER
        dias = c['dias_sin_comprar']
        cell_dias = ws.cell(row=row, column=5, value=dias if dias is not None else "Sin registro")
        cell_dias.border = THIN_BORDER
        for col in range(1, 6):
            ws.cell(row=row, column=col).fill = LIGHT_RED_FILL
        row += 1

    _auto_width(ws)

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 42
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 18


def generate_vendedor_report(db: Session, vendedor_obuma_id: str, date_from: date = None, date_to: date = None) -> str:
    date_from, date_to, custom_range = _resolve_date_range(date_from, date_to)

    reference_date = date_to if date_to else date.today()
    last_3_months = _get_last_3_months(reference_date)

    empleado = db.query(Empleado).filter(Empleado.obuma_id == vendedor_obuma_id).first()
    if not empleado:
        logger.warning(f"Empleado not found for obuma_id: {vendedor_obuma_id}")
        return None

    ventas = db.query(VentaHistorico).filter(
        VentaHistorico.vendedor_id == vendedor_obuma_id,
        VentaHistorico.anulada != True,
        func.date(VentaHistorico.fecha) >= date_from,
        func.date(VentaHistorico.fecha) <= date_to,
        VentaHistorico.tipo_documento.in_(VALID_DOC_TYPES)
    ).all()

    cartera_clients = db.query(VendedorCartera, ClienteFinal).join(
        ClienteFinal, VendedorCartera.cliente_id == ClienteFinal.id
    ).filter(
        VendedorCartera.empleado_obuma_id == vendedor_obuma_id,
        VendedorCartera.activo == True
    ).all()

    if not ventas and not cartera_clients:
        logger.info(f"No sales or cartera found for vendedor {empleado.nombre} ({vendedor_obuma_id}) in range {date_from} to {date_to}")
        return None

    active_months = set()
    for m in range(1, 13):
        month_start = date(date_from.year, m, 1)
        if m == 12:
            month_end = date(date_from.year, 12, 31)
        else:
            month_end = date(date_from.year, m + 1, 1)
        if month_start <= date_to and month_end > date_from:
            active_months.add(m)

    client_data = defaultdict(lambda: defaultdict(float))
    client_info = {}

    for vc, cli in cartera_clients:
        ckey = f"db_{cli.id}"
        if ckey not in client_info:
            client_info[ckey] = {'rut': cli.rut or '', 'nombre': cli.nombre or ''}

    cartera_db_ids = set(cli.id for _, cli in cartera_clients) if cartera_clients else set()

    excluded_db_ids = set()
    inactive_entries = db.query(VendedorCartera).filter(
        VendedorCartera.empleado_obuma_id == vendedor_obuma_id,
        VendedorCartera.activo == False
    ).all()
    for ie in inactive_entries:
        excluded_db_ids.add(ie.cliente_id)

    for v in ventas:
        ckey = None
        if v.cliente_id:
            if v.cliente_id in excluded_db_ids:
                continue
            if v.cliente_id not in cartera_db_ids:
                cliente = db.query(ClienteFinal).filter(ClienteFinal.id == v.cliente_id).first()
                if cliente:
                    dj = cliente.data_json if isinstance(cliente.data_json, dict) else {}
                    cli_vendedor = str(dj.get('rel_usuario_id', ''))
                    if cli_vendedor != str(vendedor_obuma_id):
                        continue
                    cartera_db_ids.add(v.cliente_id)
            ckey = f"db_{v.cliente_id}"
            if ckey not in client_info:
                cliente = db.query(ClienteFinal).filter(ClienteFinal.id == v.cliente_id).first()
                if cliente:
                    client_info[ckey] = {'rut': cliente.rut or '', 'nombre': cliente.nombre or ''}
                else:
                    client_info[ckey] = {'rut': '', 'nombre': ''}
        else:
            try:
                detalle = json.loads(v.detalle) if v.detalle else {}
            except (json.JSONDecodeError, TypeError):
                detalle = {}
            rel_id = str(detalle.get('rel_cliente_id', '0'))
            if rel_id and rel_id != '0':
                ckey = f"obuma_{rel_id}"
                if ckey not in client_info:
                    cliente = db.query(ClienteFinal).filter(ClienteFinal.obuma_id == rel_id).first()
                    if cliente:
                        dj = cliente.data_json if isinstance(cliente.data_json, dict) else {}
                        cli_vendedor = str(dj.get('rel_usuario_id', ''))
                        if cli_vendedor != str(vendedor_obuma_id):
                            continue
                        client_info[ckey] = {'rut': cliente.rut or '', 'nombre': cliente.nombre or ''}
                    else:
                        client_info[ckey] = {'rut': f'ID-{rel_id}', 'nombre': detalle.get('cliente_razon_social', f'Cliente {rel_id}')}
            else:
                continue

        if ckey and v.fecha:
            month = v.fecha.month
            amount = v.subtotal or 0
            if v.tipo_documento in NC_DOC_TYPES:
                client_data[ckey][month] -= amount
            else:
                client_data[ckey][month] += amount

    all_client_keys = set(client_info.keys()) | set(client_data.keys())

    rows = []
    for cid in all_client_keys:
        monthly = client_data.get(cid, defaultdict(float))
        info = client_info.get(cid, {'rut': '', 'nombre': ''})
        month_values = [max(monthly.get(m, 0), 0) if m in active_months else 0 for m in range(1, 13)]
        total = sum(month_values)
        meses_con_venta = sum(1 for i, v in enumerate(month_values) if v > 0 and (i + 1) in active_months)
        ventas_ultimos_3 = max(sum(max(monthly.get(m, 0), 0) for m in last_3_months), 0)

        rows.append({
            'rut': info['rut'],
            'nombre': info['nombre'],
            'months': month_values,
            'total': total,
            'meses_con_venta': meses_con_venta,
            'ventas_ultimos_3': ventas_ultimos_3,
        })

    rows.sort(key=lambda r: r['total'], reverse=True)

    grand_total = sum(r['total'] for r in rows)

    acumulado = 0
    for r in rows:
        pct_venta = r['total'] / grand_total if grand_total > 0 else 0
        acumulado += pct_venta
        r['pct_venta'] = pct_venta
        r['pct_acumulado'] = acumulado
        r['segmento'] = _classify_segmento(acumulado)
        r['nivel_riesgo'] = _classify_riesgo(r['meses_con_venta'], r['ventas_ultimos_3'])

    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte-Ventas-EvolucionPorClie"

    headers = [
        "N°", "CLIENTE Rut", "CLIENTE Razon Social", "CLIENTE Tipo",
        "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
        "TOTAL", "% Acumulado", "Segmento", "% de la venta",
        "Meses con venta", "Ventas últimos 3 meses", "Nivel de Riesgo"
    ]

    for i, h in enumerate(headers, 1):
        ws.cell(row=1, column=i, value=h)
    _style_header(ws, 1, len(headers))

    for idx, r in enumerate(rows, 1):
        row_num = idx + 1
        ws.cell(row=row_num, column=1, value=idx).border = THIN_BORDER
        ws.cell(row=row_num, column=2, value=r['rut']).border = THIN_BORDER
        ws.cell(row=row_num, column=3, value=r['nombre']).border = THIN_BORDER
        ws.cell(row=row_num, column=4, value="Distribuidor").border = THIN_BORDER

        for m in range(12):
            val = r['months'][m]
            cell = ws.cell(row=row_num, column=5 + m, value=val)
            cell.number_format = CURRENCY_FORMAT
            cell.border = THIN_BORDER
            if val < 0:
                cell.fill = LIGHT_RED_FILL
                cell.font = Font(name="Calibri", size=11, color="C00000", bold=True)
            elif val == 0:
                cell.fill = YELLOW_FILL

        total_val = r['total']
        cell = ws.cell(row=row_num, column=17, value=total_val)
        cell.number_format = CURRENCY_FORMAT
        cell.border = THIN_BORDER
        if total_val < 0:
            cell.fill = LIGHT_RED_FILL
            cell.font = Font(name="Calibri", size=11, color="C00000", bold=True)

        cell = ws.cell(row=row_num, column=18, value=r['pct_acumulado'])
        cell.number_format = PERCENT_FORMAT
        cell.border = THIN_BORDER

        cell = ws.cell(row=row_num, column=19, value=r['segmento'])
        cell.fill = GREEN_FILL
        cell.font = SEGMENTO_FONT
        cell.border = THIN_BORDER

        cell = ws.cell(row=row_num, column=20, value=r['pct_venta'])
        cell.number_format = PERCENT_FORMAT
        cell.border = THIN_BORDER

        ws.cell(row=row_num, column=21, value=r['meses_con_venta']).border = THIN_BORDER

        ult3_val = r['ventas_ultimos_3']
        cell = ws.cell(row=row_num, column=22, value=ult3_val)
        cell.number_format = CURRENCY_FORMAT
        cell.border = THIN_BORDER
        if ult3_val < 0:
            cell.fill = LIGHT_RED_FILL
            cell.font = Font(name="Calibri", size=11, color="C00000", bold=True)
        elif ult3_val == 0:
            cell.fill = YELLOW_FILL

        riesgo_val = r['nivel_riesgo']
        riesgo_cell = ws.cell(row=row_num, column=23, value=riesgo_val)
        riesgo_cell.border = THIN_BORDER
        if riesgo_val == "ALTO":
            riesgo_cell.fill = RED_FILL
            riesgo_cell.font = Font(name="Calibri", size=11, color="FFFFFF", bold=True)
        elif riesgo_val == "MEDIO":
            riesgo_cell.fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
            riesgo_cell.font = Font(name="Calibri", size=11, color="856404", bold=True)
        elif riesgo_val == "BAJO":
            riesgo_cell.fill = LIGHT_GREEN_FILL
            riesgo_cell.font = Font(name="Calibri", size=11, color="155724", bold=True)

    _auto_width(ws)

    _build_cartera_sheet(wb, db, vendedor_obuma_id, empleado, date_from, date_to)

    os.makedirs("reports", exist_ok=True)
    vendedor_rut = (empleado.rut or vendedor_obuma_id).replace(".", "").replace("-", "")
    if custom_range:
        filename = f"vendedor_{vendedor_rut}_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.xlsx"
    else:
        filename = f"vendedor_{vendedor_rut}_{date.today().strftime('%Y%m%d')}.xlsx"
    filepath = os.path.join("reports", filename)
    wb.save(filepath)

    reporte = ReporteGenerado(
        nombre_archivo=filename,
        tipo="vendedor",
        fecha_reporte=date.today(),
        ruta_archivo=filepath,
    )
    db.add(reporte)
    db.commit()

    logger.info(f"Vendedor report generated: {filepath} ({empleado.nombre})")
    return filepath


def generate_all_vendedor_reports(db: Session, date_from: date = None, date_to: date = None) -> list:
    resolved_from, resolved_to, _ = _resolve_date_range(date_from, date_to)

    vendedor_ids = db.query(distinct(VentaHistorico.vendedor_id)).filter(
        VentaHistorico.vendedor_id != None,
        VentaHistorico.anulada != True,
        VentaHistorico.fecha >= resolved_from,
        VentaHistorico.fecha <= resolved_to
    ).all()

    vendedor_ids = [vid[0] for vid in vendedor_ids if vid[0]]

    filepaths = []
    for vid in vendedor_ids:
        try:
            fp = generate_vendedor_report(db, vid, date_from, date_to)
            if fp:
                filepaths.append(fp)
        except Exception as e:
            logger.error(f"Error generating report for vendedor {vid}: {e}")

    logger.info(f"Generated {len(filepaths)} vendedor reports for range {resolved_from} to {resolved_to}")
    return filepaths


def generate_daily_report(db: Session, report_date: date = None) -> str:
    if report_date is None:
        report_date = date.today()

    current_year = report_date.year
    date_from = date(current_year, 1, 1)
    date_to = date(current_year, 12, 31)
    filepaths = generate_all_vendedor_reports(db, date_from, date_to)

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen Consolidado"

    ws.cell(row=1, column=1, value="Reporte Consolidado de Vendedores").font = TITLE_FONT
    ws.cell(row=2, column=1, value=f"Fecha: {report_date.strftime('%d/%m/%Y')} - Año: {current_year}").font = SUBTITLE_FONT
    ws.merge_cells("A1:D1")
    ws.merge_cells("A2:D2")

    headers = ["Vendedor", "RUT", "Clientes", "Venta Total Neto"]
    for i, h in enumerate(headers, 1):
        ws.cell(row=4, column=i, value=h)
    _style_header(ws, 4, len(headers))

    vendedor_ids = db.query(distinct(VentaHistorico.vendedor_id)).filter(
        VentaHistorico.vendedor_id != None,
        VentaHistorico.anulada != True,
        func.date(VentaHistorico.fecha) >= date_from,
        func.date(VentaHistorico.fecha) <= date_to
    ).all()
    vendedor_ids = [vid[0] for vid in vendedor_ids if vid[0]]

    row = 5
    total_general = 0
    for vid in vendedor_ids:
        empleado = db.query(Empleado).filter(Empleado.obuma_id == vid).first()
        if not empleado:
            continue

        stats = db.query(
            func.count(distinct(VentaHistorico.cliente_id)),
            func.sum(
                sql_case(
                    (VentaHistorico.tipo_documento.in_(NC_DOC_TYPES), -VentaHistorico.subtotal),
                    else_=VentaHistorico.subtotal
                )
            )
        ).filter(
            VentaHistorico.vendedor_id == vid,
            VentaHistorico.anulada != True,
            func.date(VentaHistorico.fecha) >= date_from,
            func.date(VentaHistorico.fecha) <= date_to,
            VentaHistorico.tipo_documento.in_(VALID_DOC_TYPES)
        ).first()

        num_clientes = stats[0] or 0
        total_neto = stats[1] or 0

        ws.cell(row=row, column=1, value=empleado.nombre or '').border = THIN_BORDER
        ws.cell(row=row, column=2, value=empleado.rut or '').border = THIN_BORDER
        ws.cell(row=row, column=3, value=num_clientes).border = THIN_BORDER
        cell = ws.cell(row=row, column=4, value=total_neto)
        cell.number_format = CURRENCY_FORMAT
        cell.border = THIN_BORDER

        total_general += total_neto
        row += 1

    row += 1
    ws.cell(row=row, column=3, value="TOTAL GENERAL").font = Font(bold=True)
    ws.cell(row=row, column=3).border = THIN_BORDER
    cell = ws.cell(row=row, column=4, value=total_general)
    cell.number_format = CURRENCY_FORMAT
    cell.font = Font(bold=True)
    cell.border = THIN_BORDER

    _auto_width(ws)

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

    logger.info(f"Daily consolidated report generated: {filepath} with {len(filepaths)} vendedor reports")
    return filepath
