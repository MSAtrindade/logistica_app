from datetime import date, datetime, timedelta
import calendar
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from sqlalchemy import func
from . import db
from .models import LogisticsRecord, LocomotivaEntry, LocomotivaTCSEntry, PlanejadoLocomotivaEntry


main_bp = Blueprint('main', __name__)


def parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


def parse_float_br(value):
    raw = (value or '').strip()
    if not raw:
        return 0.0
    raw = raw.replace(' ', '')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    return float(raw)


def apply_record_filters(query, args):
    data_inicio = args.get('data_inicio', '').strip()
    data_fim = args.get('data_fim', '').strip()
    produto = args.get('produto', '').strip()
    cliente = args.get('cliente', '').strip()
    terminal = args.get('terminal', '').strip()
    termo = args.get('termo', '').strip()

    if data_inicio:
        query = query.filter(LogisticsRecord.data_referencia >= parse_date(data_inicio))
    if data_fim:
        query = query.filter(LogisticsRecord.data_referencia <= parse_date(data_fim))
    if produto:
        query = query.filter(LogisticsRecord.produto == produto)
    if cliente:
        query = query.filter(LogisticsRecord.cliente == cliente)
    if terminal:
        query = query.filter(LogisticsRecord.terminal == terminal)
    if termo:
        query = query.filter(LogisticsRecord.termo == termo)
    return query


def format_month_label(ref_date):
    meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    return f"{meses[ref_date.month - 1]}/{str(ref_date.year)[2:]}"


def locomotiva_real_agg(start_date, end_date):
    rows = (
        LogisticsRecord.query.with_entities(
            LogisticsRecord.data_referencia,
            func.coalesce(
                func.sum(
                    db.case(
                        (func.lower(LogisticsRecord.produto).in_(['sinter', 'sf']), LogisticsRecord.real),
                        else_=0,
                    )
                ), 0
            ).label('real_sf'),
            func.coalesce(
                func.sum(
                    db.case(
                        (func.lower(LogisticsRecord.produto) == 'npo', LogisticsRecord.real),
                        else_=0,
                    )
                ), 0
            ).label('real_gg'),
            func.coalesce(
                func.sum(
                    db.case(
                        (func.lower(LogisticsRecord.produto).in_(['sinter', 'sf']), LogisticsRecord.plano),
                        else_=0,
                    )
                ), 0
            ).label('plano_sf'),
            func.coalesce(
                func.sum(
                    db.case(
                        (func.lower(LogisticsRecord.produto) == 'npo', LogisticsRecord.plano),
                        else_=0,
                    )
                ), 0
            ).label('plano_gg'),
        )
        .filter(LogisticsRecord.cliente == 'AMT')
        .filter(LogisticsRecord.terminal == 'TISL')
        .filter(LogisticsRecord.data_referencia >= start_date)
        .filter(LogisticsRecord.data_referencia <= end_date)
        .group_by(LogisticsRecord.data_referencia)
        .order_by(LogisticsRecord.data_referencia.asc())
        .all()
    )
    return {row.data_referencia: row for row in rows}


def recompute_locomotiva(start_date, end_date):
    agg_map = locomotiva_real_agg(start_date, end_date)
    previous_entry = (
        LocomotivaEntry.query
        .filter(LocomotivaEntry.data_referencia < start_date)
        .order_by(LocomotivaEntry.data_referencia.desc())
        .first()
    )
    saldo_sf = float(previous_entry.estoque_sf or 0) if previous_entry else 0.0
    saldo_gg = float(previous_entry.estoque_gg or 0) if previous_entry else 0.0

    current = start_date
    while current <= end_date:
        entry = LocomotivaEntry.query.filter_by(data_referencia=current).first()
        if not entry:
            entry = LocomotivaEntry(
                data_referencia=current,
                trem_sf=0,
                trem_gg=0,
                estoque_sf=saldo_sf,
                estoque_gg=saldo_gg,
            )
            db.session.add(entry)
            db.session.flush()

        agg = agg_map.get(current)
        real_sf = float(agg.real_sf or 0) if agg else 0.0
        real_gg = float(agg.real_gg or 0) if agg else 0.0

        trem_sf = float(entry.trem_sf or 0)
        trem_gg = float(entry.trem_gg or 0)

        saldo_sf = saldo_sf + real_sf - trem_sf
        saldo_gg = saldo_gg + real_gg - trem_gg

        entry.estoque_sf = saldo_sf
        entry.estoque_gg = saldo_gg

        current += timedelta(days=1)





def locomotiva_tcs_real_agg(start_date, end_date):
    rows = (
        LogisticsRecord.query.with_entities(
            LogisticsRecord.data_referencia,
            func.coalesce(
                func.sum(
                    db.case(
                        (func.lower(LogisticsRecord.produto).in_(['sinter', 'sf']), LogisticsRecord.real),
                        else_=0,
                    )
                ), 0
            ).label('real_sf'),
        )
        .filter(LogisticsRecord.terminal == 'TCS')
        .filter(LogisticsRecord.data_referencia >= start_date)
        .filter(LogisticsRecord.data_referencia <= end_date)
        .group_by(LogisticsRecord.data_referencia)
        .order_by(LogisticsRecord.data_referencia.asc())
        .all()
    )
    return {row.data_referencia: row for row in rows}


def recompute_locomotiva_tcs(start_date, end_date):
    agg_map = locomotiva_tcs_real_agg(start_date, end_date)
    previous_entry = (
        LocomotivaTCSEntry.query
        .filter(LocomotivaTCSEntry.data_referencia < start_date)
        .order_by(LocomotivaTCSEntry.data_referencia.desc())
        .first()
    )
    saldo_sf = float(previous_entry.estoque_sf or 0) if previous_entry else 0.0

    current = start_date
    while current <= end_date:
        entry = LocomotivaTCSEntry.query.filter_by(data_referencia=current).first()
        if not entry:
            entry = LocomotivaTCSEntry(
                data_referencia=current,
                trem_sf=0,
                estoque_sf=saldo_sf,
            )
            db.session.add(entry)
            db.session.flush()

        agg = agg_map.get(current)
        real_sf = float(agg.real_sf or 0) if agg else 0.0
        trem_sf = float(entry.trem_sf or 0)

        saldo_sf = saldo_sf + real_sf - trem_sf
        entry.estoque_sf = saldo_sf

        current += timedelta(days=1)



def get_planejado_locomotiva_map(locomotiva_tipo, start_date, end_date):
    rows = (
        PlanejadoLocomotivaEntry.query
        .filter(PlanejadoLocomotivaEntry.locomotiva_tipo == locomotiva_tipo)
        .filter(PlanejadoLocomotivaEntry.data_referencia >= start_date)
        .filter(PlanejadoLocomotivaEntry.data_referencia <= end_date)
        .order_by(PlanejadoLocomotivaEntry.data_referencia.asc())
        .all()
    )
    return {row.data_referencia: row for row in rows}


def build_planejado_locomotiva_rows(locomotiva_tipo, start_date, end_date):
    planejado_map = get_planejado_locomotiva_map(locomotiva_tipo, start_date, end_date)
    rows = []
    current = start_date
    while current <= end_date:
        item = planejado_map.get(current)
        rows.append({
            'data': current,
            'plano_ferro': float(item.plano_ferro or 0) if item else 0.0,
            'real_ferro': float(item.real_ferro or 0) if item else 0.0,
        })
        current += timedelta(days=1)
    return rows


def build_locomotiva_dashboard_data(data_inicio, data_fim, produto_filtro='todos'):
    recompute_locomotiva(data_inicio, data_fim)
    db.session.commit()

    agg_map = locomotiva_real_agg(data_inicio, data_fim)
    entry_map = {
        item.data_referencia: item
        for item in LocomotivaEntry.query
        .filter(LocomotivaEntry.data_referencia >= data_inicio)
        .filter(LocomotivaEntry.data_referencia <= data_fim)
        .order_by(LocomotivaEntry.data_referencia.asc())
        .all()
    }
    planejado_map = get_planejado_locomotiva_map('tisl', data_inicio, data_fim)

    labels = []
    real_sf = []
    real_gg = []
    estoque_sf = []
    estoque_gg = []
    plano_sf = []
    plano_gg = []
    plano_ferro = []
    real_ferro = []

    total_plano_sf = total_plano_gg = 0.0
    total_real_sf = total_real_gg = 0.0

    current = data_inicio
    while current <= data_fim:
        labels.append(current.strftime('%d/%m'))
        agg = agg_map.get(current)
        entry = entry_map.get(current)
        planejado = planejado_map.get(current)

        valor_real_sf = float(agg.real_sf or 0) if agg else 0.0
        valor_real_gg = float(agg.real_gg or 0) if agg else 0.0
        valor_plano_sf = float(agg.plano_sf or 0) if agg else 0.0
        valor_plano_gg = float(agg.plano_gg or 0) if agg else 0.0
        valor_estoque_sf = float(entry.estoque_sf or 0) if entry else 0.0
        valor_estoque_gg = float(entry.estoque_gg or 0) if entry else 0.0

        total_plano_sf += valor_plano_sf
        total_plano_gg += valor_plano_gg
        total_real_sf += valor_real_sf
        total_real_gg += valor_real_gg

        valor_plano_ferro = float(planejado.plano_ferro or 0) if planejado else 0.0
        valor_real_ferro = float(planejado.real_ferro or 0) if planejado else 0.0

        if produto_filtro == 'sf':
            real_sf.append(valor_real_sf)
            real_gg.append(None)
            estoque_sf.append(valor_estoque_sf)
            estoque_gg.append(None)
            plano_sf.append(valor_plano_sf)
            plano_gg.append(None)
            plano_ferro.append(valor_plano_ferro)
            real_ferro.append(valor_real_ferro)
        elif produto_filtro == 'npo':
            real_sf.append(None)
            real_gg.append(valor_real_gg)
            estoque_sf.append(None)
            estoque_gg.append(valor_estoque_gg)
            plano_sf.append(None)
            plano_gg.append(valor_plano_gg)
            plano_ferro.append(valor_plano_ferro)
            real_ferro.append(valor_real_ferro)
        else:
            real_sf.append(valor_real_sf)
            real_gg.append(valor_real_gg)
            estoque_sf.append(valor_estoque_sf)
            estoque_gg.append(valor_estoque_gg)
            plano_sf.append(valor_plano_sf)
            plano_gg.append(valor_plano_gg)
            plano_ferro.append(valor_plano_ferro)
            real_ferro.append(valor_real_ferro)

        current += timedelta(days=1)

    last_entry = (
        LocomotivaEntry.query
        .filter(LocomotivaEntry.data_referencia <= data_fim)
        .order_by(LocomotivaEntry.data_referencia.desc())
        .first()
    )
    ultimo_estoque_sf = float(last_entry.estoque_sf or 0) if last_entry else 0.0
    ultimo_estoque_gg = float(last_entry.estoque_gg or 0) if last_entry else 0.0

    if produto_filtro == 'sf':
        estoque_bar_labels = ['SF MSA']
        estoque_bar_values = [ultimo_estoque_sf]
    elif produto_filtro == 'npo':
        estoque_bar_labels = ['NPO MSA']
        estoque_bar_values = [ultimo_estoque_gg]
    else:
        estoque_bar_labels = ['NPO MSA', 'SF MSA']
        estoque_bar_values = [ultimo_estoque_gg, ultimo_estoque_sf]

    if produto_filtro == 'sf':
        volume_labels = ['SF']
        volume_plano = [total_plano_sf]
        volume_real = [total_real_sf]
        volume_colors_plano = ['#5b8cc6']
        volume_colors_real = ['#c96a63']
    elif produto_filtro == 'npo':
        volume_labels = ['NPO']
        volume_plano = [total_plano_gg]
        volume_real = [total_real_gg]
        volume_colors_plano = ['#a8c56b']
        volume_colors_real = ['#8f79ba']
    else:
        volume_labels = ['SF', 'NPO']
        volume_plano = [total_plano_sf, total_plano_gg]
        volume_real = [total_real_sf, total_real_gg]
        volume_colors_plano = ['#5b8cc6', '#a8c56b']
        volume_colors_real = ['#c96a63', '#8f79ba']

    return {
        'line_labels': labels,
        'real_sf': real_sf,
        'real_gg': real_gg,
        'estoque_sf': estoque_sf,
        'estoque_gg': estoque_gg,
        'plano_ferro': plano_ferro,
        'real_ferro': real_ferro,
        'estoque_bar_labels': estoque_bar_labels,
        'estoque_bar_values': estoque_bar_values,
        'volume_labels': volume_labels,
        'volume_plano': volume_plano,
        'volume_real': volume_real,
        'volume_colors_plano': volume_colors_plano,
        'volume_colors_real': volume_colors_real,
        'stock_title_date': data_fim.strftime('%d/%m/%y'),
    }


@main_bp.route('/')
@login_required
def dashboard():
    base_query = apply_record_filters(LogisticsRecord.query, request.args)

    total_registros = base_query.count()
    total_plano = base_query.with_entities(func.coalesce(func.sum(LogisticsRecord.plano), 0)).scalar() or 0
    total_d1 = base_query.with_entities(func.coalesce(func.sum(LogisticsRecord.d1), 0)).scalar() or 0
    total_real = base_query.with_entities(func.coalesce(func.sum(LogisticsRecord.real), 0)).scalar() or 0
    total_dif = total_real - total_plano
    total_ader = (total_real / total_plano * 100) if total_plano else 0

    ultimos = base_query.order_by(LogisticsRecord.data_referencia.desc(), LogisticsRecord.id.desc()).limit(10).all()

    tabela_total = (
        base_query.with_entities(
            LogisticsRecord.produto,
            LogisticsRecord.cliente,
            LogisticsRecord.terminal,
            LogisticsRecord.termo,
            func.coalesce(func.sum(LogisticsRecord.plano), 0).label('plano'),
            func.coalesce(func.sum(LogisticsRecord.d1), 0).label('d1'),
            func.coalesce(func.sum(LogisticsRecord.real), 0).label('real'),
        )
        .group_by(
            LogisticsRecord.produto,
            LogisticsRecord.cliente,
            LogisticsRecord.terminal,
            LogisticsRecord.termo,
        )
        .order_by(
            LogisticsRecord.produto.asc(),
            LogisticsRecord.cliente.asc(),
            LogisticsRecord.terminal.asc(),
            LogisticsRecord.termo.asc(),
        )
        .all()
    )

    chart1_labels = []
    chart1_plano = []
    chart1_real = []
    chart1_d1 = []
    for item in tabela_total:
        chart1_labels.append(item.cliente)
        chart1_plano.append(float(item.plano or 0))
        chart1_real.append(float(item.real or 0))
        chart1_d1.append(float(item.d1 or 0))

    daily_rows = (
        base_query.with_entities(
            LogisticsRecord.data_referencia,
            func.coalesce(func.sum(LogisticsRecord.plano), 0).label('plano'),
            func.coalesce(func.sum(LogisticsRecord.d1), 0).label('d1'),
            func.coalesce(func.sum(LogisticsRecord.real), 0).label('real'),
        )
        .group_by(LogisticsRecord.data_referencia)
        .order_by(LogisticsRecord.data_referencia.asc())
        .all()
    )

    chart2_labels = []
    chart2_plano = []
    chart2_d1 = []
    chart2_real = []

    if daily_rows:
        reference_date = daily_rows[-1].data_referencia
    else:
        today = date.today()
        data_fim = request.args.get('data_fim', '').strip()
        reference_date = parse_date(data_fim) if data_fim else today

    days_in_month = calendar.monthrange(reference_date.year, reference_date.month)[1]
    daily_map = {row.data_referencia.day: row for row in daily_rows if row.data_referencia.month == reference_date.month and row.data_referencia.year == reference_date.year}

    for day in range(1, days_in_month + 1):
        chart2_labels.append(f"{day}/{reference_date.month}")
        row = daily_map.get(day)
        chart2_plano.append(float(row.plano or 0) if row else 0)
        chart2_d1.append(float(row.d1 or 0) if row else 0)
        chart2_real.append(float(row.real or 0) if row else 0)

    max_day_with_data = max(daily_map.keys()) if daily_map else 1
    ritmo = (total_real / max_day_with_data * days_in_month) if max_day_with_data else 0
    plano_mes = total_plano
    acumulado_real = total_real

    chart2_labels.extend(['ACUMULADO REAL', 'RITMO', 'PLANO / MÊS'])
    chart2_plano.extend([None, None, None])
    chart2_d1.extend([None, None, None])
    chart2_real.extend([None, None, None])

    filtros = {
        'produtos': [x[0] for x in LogisticsRecord.query.with_entities(LogisticsRecord.produto).distinct().order_by(LogisticsRecord.produto.asc()).all() if x[0]],
        'clientes': [x[0] for x in LogisticsRecord.query.with_entities(LogisticsRecord.cliente).distinct().order_by(LogisticsRecord.cliente.asc()).all() if x[0]],
        'terminais': [x[0] for x in LogisticsRecord.query.with_entities(LogisticsRecord.terminal).distinct().order_by(LogisticsRecord.terminal.asc()).all() if x[0]],
        'termos': [x[0] for x in LogisticsRecord.query.with_entities(LogisticsRecord.termo).distinct().order_by(LogisticsRecord.termo.asc()).all() if x[0]],
    }

    return render_template(
        'dashboard.html',
        total_registros=total_registros,
        total_plano=total_plano,
        total_d1=total_d1,
        total_real=total_real,
        total_dif=total_dif,
        total_ader=total_ader,
        ultimos=ultimos,
        tabela_total=tabela_total,
        filtros=filtros,
        chart1_labels=chart1_labels,
        chart1_plano=chart1_plano,
        chart1_real=chart1_real,
        chart1_d1=chart1_d1,
        chart2_labels=chart2_labels,
        chart2_plano=chart2_plano,
        chart2_d1=chart2_d1,
        chart2_real=chart2_real,
        chart2_acumulado_real=acumulado_real,
        chart2_ritmo=ritmo,
        chart2_plano_mes=plano_mes,
        month_label=format_month_label(reference_date),
    )


@main_bp.route('/locomotiva', methods=['GET', 'POST'])
@login_required
def locomotiva():
    hoje = date.today()
    data_inicio_txt = request.values.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d')).strip()
    data_fim_txt = request.values.get('data_fim', hoje.strftime('%Y-%m-%d')).strip()

    data_inicio = parse_date(data_inicio_txt)
    data_fim = parse_date(data_fim_txt)
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
        data_inicio_txt, data_fim_txt = data_inicio.strftime('%Y-%m-%d'), data_fim.strftime('%Y-%m-%d')

    if request.method == 'POST':
        if not current_user.is_admin:
            flash('Somente administradores podem alterar os dados da locomotiva.', 'danger')
            return redirect(url_for('main.locomotiva', data_inicio=data_inicio_txt, data_fim=data_fim_txt))

        current = data_inicio
        while current <= data_fim:
            key = current.strftime('%Y-%m-%d')
            trem_sf = parse_float_br(request.form.get(f'trem_sf_{key}', '0'))
            trem_gg = parse_float_br(request.form.get(f'trem_gg_{key}', '0'))

            entry = LocomotivaEntry.query.filter_by(data_referencia=current).first()
            if not entry:
                entry = LocomotivaEntry(data_referencia=current)
                db.session.add(entry)

            entry.trem_sf = trem_sf
            entry.trem_gg = trem_gg
            current += timedelta(days=1)

        recompute_locomotiva(data_inicio, data_fim)
        db.session.commit()
        flash('Lançamentos da locomotiva salvos com sucesso.', 'success')
        return redirect(url_for('main.locomotiva', data_inicio=data_inicio_txt, data_fim=data_fim_txt))

    recompute_locomotiva(data_inicio, data_fim)
    db.session.commit()

    agg_map = locomotiva_real_agg(data_inicio, data_fim)
    entry_map = {
        item.data_referencia: item
        for item in LocomotivaEntry.query
        .filter(LocomotivaEntry.data_referencia >= data_inicio)
        .filter(LocomotivaEntry.data_referencia <= data_fim)
        .order_by(LocomotivaEntry.data_referencia.asc())
        .all()
    }

    linhas = []
    current = data_inicio
    while current <= data_fim:
        agg = agg_map.get(current)
        entry = entry_map.get(current)
        linhas.append({
            'data': current,
            'real_sf': float(agg.real_sf or 0) if agg else 0,
            'real_gg': float(agg.real_gg or 0) if agg else 0,
            'estoque_sf': float(entry.estoque_sf or 0) if entry else 0,
            'estoque_gg': float(entry.estoque_gg or 0) if entry else 0,
            'trem_sf': float(entry.trem_sf or 0) if entry else 0,
            'trem_gg': float(entry.trem_gg or 0) if entry else 0,
        })
        current += timedelta(days=1)

    return render_template(
        'locomotiva.html',
        linhas=linhas,
        data_inicio=data_inicio_txt,
        data_fim=data_fim_txt,
    )







def build_locomotiva_tcs_dashboard_data(data_inicio, data_fim, produto_filtro='todos'):
    recompute_locomotiva_tcs(data_inicio, data_fim)
    db.session.commit()

    agg_map = locomotiva_tcs_real_agg(data_inicio, data_fim)
    entry_map = {
        item.data_referencia: item
        for item in LocomotivaTCSEntry.query
        .filter(LocomotivaTCSEntry.data_referencia >= data_inicio)
        .filter(LocomotivaTCSEntry.data_referencia <= data_fim)
        .order_by(LocomotivaTCSEntry.data_referencia.asc())
        .all()
    }

    labels = []
    real_sf = []
    estoque_sf = []
    plano_ferro = []
    real_ferro = []
    total_plano_sf = 0.0
    total_real_sf = 0.0

    current = data_inicio
    while current <= data_fim:
        labels.append(current.strftime('%d/%m'))
        agg = agg_map.get(current)
        entry = entry_map.get(current)

        valor_real_sf = float(agg.real_sf or 0) if agg else 0.0
        valor_plano_sf = float(
            LogisticsRecord.query.with_entities(func.coalesce(func.sum(LogisticsRecord.plano), 0))
            .filter(LogisticsRecord.terminal == 'TCS')
            .filter(func.lower(LogisticsRecord.produto).in_(['sinter', 'sf']))
            .filter(LogisticsRecord.data_referencia == current)
            .scalar() or 0
        )
        valor_estoque_sf = float(entry.estoque_sf or 0) if entry else 0.0
        valor_trem_sf = float(entry.trem_sf or 0) if entry else 0.0

        total_plano_sf += valor_plano_sf
        total_real_sf += valor_real_sf

        real_sf.append(valor_real_sf)
        estoque_sf.append(valor_estoque_sf)
        plano_ferro.append(valor_trem_sf)
        real_ferro.append(valor_real_sf)

        current += timedelta(days=1)

    last_entry = (
        LocomotivaTCSEntry.query
        .filter(LocomotivaTCSEntry.data_referencia <= data_fim)
        .order_by(LocomotivaTCSEntry.data_referencia.desc())
        .first()
    )
    ultimo_estoque_sf = float(last_entry.estoque_sf or 0) if last_entry else 0.0

    return {
        'line_labels': labels,
        'real_sf': real_sf,
        'estoque_sf': estoque_sf,
        'plano_ferro': plano_ferro,
        'real_ferro': real_ferro,
        'estoque_bar_labels': ['SF MSA'],
        'estoque_bar_values': [ultimo_estoque_sf],
        'volume_labels': ['SF'],
        'volume_plano': [total_plano_sf],
        'volume_real': [total_real_sf],
        'stock_title_date': data_fim.strftime('%d/%m/%y'),
        'control_title_date': data_fim.strftime('%d/%m/%Y'),
    }

@main_bp.route('/locomotiva-tcs', methods=['GET', 'POST'])
@login_required
def locomotiva_tcs():
    hoje = date.today()
    data_inicio_txt = request.values.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d')).strip()
    data_fim_txt = request.values.get('data_fim', hoje.strftime('%Y-%m-%d')).strip()

    data_inicio = parse_date(data_inicio_txt)
    data_fim = parse_date(data_fim_txt)
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
        data_inicio_txt, data_fim_txt = data_inicio.strftime('%Y-%m-%d'), data_fim.strftime('%Y-%m-%d')

    if request.method == 'POST':
        if not current_user.is_admin:
            flash('Somente administradores podem alterar os dados da locomotiva TCS.', 'danger')
            return redirect(url_for('main.locomotiva_tcs', data_inicio=data_inicio_txt, data_fim=data_fim_txt))

        current = data_inicio
        while current <= data_fim:
            key = current.strftime('%Y-%m-%d')
            trem_sf = parse_float_br(request.form.get(f'trem_sf_{key}', '0'))

            entry = LocomotivaTCSEntry.query.filter_by(data_referencia=current).first()
            if not entry:
                entry = LocomotivaTCSEntry(data_referencia=current)
                db.session.add(entry)

            entry.trem_sf = trem_sf
            current += timedelta(days=1)

        recompute_locomotiva_tcs(data_inicio, data_fim)
        db.session.commit()
        flash('Lançamentos da locomotiva TCS salvos com sucesso.', 'success')
        return redirect(url_for('main.locomotiva_tcs', data_inicio=data_inicio_txt, data_fim=data_fim_txt))

    recompute_locomotiva_tcs(data_inicio, data_fim)
    db.session.commit()

    agg_map = locomotiva_tcs_real_agg(data_inicio, data_fim)
    entry_map = {
        item.data_referencia: item
        for item in LocomotivaTCSEntry.query
        .filter(LocomotivaTCSEntry.data_referencia >= data_inicio)
        .filter(LocomotivaTCSEntry.data_referencia <= data_fim)
        .order_by(LocomotivaTCSEntry.data_referencia.asc())
        .all()
    }

    linhas = []
    current = data_inicio
    while current <= data_fim:
        agg = agg_map.get(current)
        entry = entry_map.get(current)
        linhas.append({
            'data': current,
            'real_sf': float(agg.real_sf or 0) if agg else 0,
            'estoque_sf': float(entry.estoque_sf or 0) if entry else 0,
            'trem_sf': float(entry.trem_sf or 0) if entry else 0,
        })
        current += timedelta(days=1)

    return render_template(
        'locomotiva_tcs.html',
        linhas=linhas,
        data_inicio=data_inicio_txt,
        data_fim=data_fim_txt,
    )



@main_bp.route('/dashboard-locomotiva-tcs')
@login_required
def dashboard_locomotiva_tcs():
    hoje = date.today()
    data_inicio_txt = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d')).strip()
    data_fim_txt = request.args.get('data_fim', hoje.strftime('%Y-%m-%d')).strip()
    produto = request.args.get('produto', 'todos').strip().lower() or 'todos'

    data_inicio = parse_date(data_inicio_txt)
    data_fim = parse_date(data_fim_txt)
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
        data_inicio_txt, data_fim_txt = data_inicio.strftime('%Y-%m-%d'), data_fim.strftime('%Y-%m-%d')

    if produto not in ['todos', 'sf']:
        produto = 'todos'

    chart_data = build_locomotiva_tcs_dashboard_data(data_inicio, data_fim, produto)

    return render_template(
        'dashboard_locomotiva_tcs.html',
        data_inicio=data_inicio_txt,
        data_fim=data_fim_txt,
        produto=produto,
        chart_data=chart_data,
    )

@main_bp.route('/dashboard-locomotiva')
@login_required
def dashboard_locomotiva():
    hoje = date.today()
    data_inicio_txt = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d')).strip()
    data_fim_txt = request.args.get('data_fim', hoje.strftime('%Y-%m-%d')).strip()
    produto = request.args.get('produto', 'todos').strip().lower() or 'todos'

    data_inicio = parse_date(data_inicio_txt)
    data_fim = parse_date(data_fim_txt)
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
        data_inicio_txt, data_fim_txt = data_inicio.strftime('%Y-%m-%d'), data_fim.strftime('%Y-%m-%d')

    if produto not in ['todos', 'sf', 'npo']:
        produto = 'todos'

    chart_data = build_locomotiva_dashboard_data(data_inicio, data_fim, produto)

    return render_template(
        'dashboard_locomotiva.html',
        data_inicio=data_inicio_txt,
        data_fim=data_fim_txt,
        produto=produto,
        chart_data=chart_data,
    )



@main_bp.route('/simulador-frete', methods=['GET', 'POST'])
@login_required
def simulador_frete():
    frete_antigo = 58.50
    fator = 4.20
    gestao = 1.50

    if request.method == 'POST':
        frete_antigo = parse_float_br(request.form.get('frete_antigo', '58,50'))
        fator = parse_float_br(request.form.get('fator', '4,20'))
        gestao = parse_float_br(request.form.get('gestao', '1,50'))

    reajuste = frete_antigo * (fator / 100.0)
    frete_atual = frete_antigo + reajuste
    total = frete_atual + gestao

    comparativo = {
        'dif_reajuste': reajuste,
        'dif_frete': frete_atual - frete_antigo,
        'dif_total_vs_antigo': total - frete_antigo,
        'perc_total_vs_antigo': ((total / frete_antigo) - 1) * 100 if frete_antigo else 0,
        'total_sem_gestao': frete_atual,
        'gestao': gestao,
    }

    return render_template(
        'simulador_frete.html',
        frete_antigo=frete_antigo,
        fator=fator,
        gestao=gestao,
        reajuste=reajuste,
        frete_atual=frete_atual,
        total=total,
        comparativo=comparativo,
    )


def _fmt_num_br(value):
    return f"{float(value or 0):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _export_dashboard_base_query(data_inicio=None, data_fim=None, produto=None):
    query = LogisticsRecord.query
    if data_inicio:
        query = query.filter(LogisticsRecord.data_referencia >= data_inicio)
    if data_fim:
        query = query.filter(LogisticsRecord.data_referencia <= data_fim)
    if produto:
        query = query.filter(LogisticsRecord.produto == produto)
    return query


@main_bp.route('/exportar-dashboards')
@login_required
def exportar_dashboards():
    import io
    import os
    import tempfile
    from matplotlib import pyplot as plt
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image
    )

    hoje = date.today()
    data_inicio_txt = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d')).strip()
    data_fim_txt = request.args.get('data_fim', hoje.strftime('%Y-%m-%d')).strip()
    produto = request.args.get('produto', '').strip()

    data_inicio = parse_date(data_inicio_txt)
    data_fim = parse_date(data_fim_txt)
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio

    # Dashboard principal
    base_query = _export_dashboard_base_query(data_inicio, data_fim, produto if produto else None)
    total_registros = base_query.count()
    total_plano = base_query.with_entities(func.coalesce(func.sum(LogisticsRecord.plano), 0)).scalar() or 0
    total_d1 = base_query.with_entities(func.coalesce(func.sum(LogisticsRecord.d1), 0)).scalar() or 0
    total_real = base_query.with_entities(func.coalesce(func.sum(LogisticsRecord.real), 0)).scalar() or 0
    total_dif = total_real - total_plano
    total_ader = (total_real / total_plano * 100) if total_plano else 0

    tabela_total = (
        base_query.with_entities(
            LogisticsRecord.produto,
            LogisticsRecord.cliente,
            LogisticsRecord.terminal,
            LogisticsRecord.termo,
            func.coalesce(func.sum(LogisticsRecord.plano), 0).label('plano'),
            func.coalesce(func.sum(LogisticsRecord.d1), 0).label('d1'),
            func.coalesce(func.sum(LogisticsRecord.real), 0).label('real'),
        )
        .group_by(
            LogisticsRecord.produto,
            LogisticsRecord.cliente,
            LogisticsRecord.terminal,
            LogisticsRecord.termo,
        )
        .order_by(
            LogisticsRecord.produto.asc(),
            LogisticsRecord.cliente.asc(),
        )
        .all()
    )

    # Dashboards locomotiva
    locomotiva_data = build_locomotiva_dashboard_data(data_inicio, data_fim, produto.lower() if produto.lower() in ['todos','sf','npo'] else 'todos')
    locomotiva_tcs_data = build_locomotiva_tcs_dashboard_data(data_inicio, data_fim, 'sf')

    temp_dir = tempfile.mkdtemp(prefix='export_dash_')

    def save_chart(path, title, labels, series, kind='line'):
        plt.figure(figsize=(11, 4.2))
        if kind == 'line':
            for item in series:
                plt.plot(labels, item['data'], label=item['label'], linewidth=2)
            plt.xticks(rotation=45, ha='right')
            plt.grid(True, alpha=0.25)
        elif kind == 'bar':
            import numpy as np
            x = np.arange(len(labels))
            width = 0.35
            if len(series) == 1:
                plt.bar(labels, series[0]['data'], width=0.6, label=series[0]['label'])
            else:
                offsets = [(-width/2), (width/2)]
                for idx, item in enumerate(series[:2]):
                    plt.bar(x + offsets[idx], item['data'], width=width, label=item['label'])
                plt.xticks(x, labels)
            plt.grid(True, axis='y', alpha=0.25)
        elif kind == 'hbar':
            plt.barh(labels, series[0]['data'])
            plt.grid(True, axis='x', alpha=0.25)
        plt.title(title, fontsize=14, fontweight='bold')
        plt.legend()
        plt.tight_layout()
        plt.savefig(path, dpi=180, bbox_inches='tight')
        plt.close()

    # Generate images
    principal_path = os.path.join(temp_dir, 'principal.png')
    save_chart(
        principal_path,
        'Atendimento aos Clientes',
        [x.cliente for x in tabela_total][:12] if tabela_total else ['Sem dados'],
        [
            {'label': 'Plano', 'data': [float(x.plano) for x in tabela_total][:12] if tabela_total else [0]},
            {'label': 'Real', 'data': [float(x.real) for x in tabela_total][:12] if tabela_total else [0]},
        ],
        kind='bar'
    )

    loco1 = os.path.join(temp_dir, 'loco_estoque.png')
    save_chart(
        loco1,
        f"ESTOQUE (t) {locomotiva_data['stock_title_date']}",
        locomotiva_data['estoque_bar_labels'],
        [{'label': 'Estoque', 'data': locomotiva_data['estoque_bar_values']}],
        kind='hbar'
    )
    loco2 = os.path.join(temp_dir, 'loco_evolucao.png')
    save_chart(
        loco2,
        'Controle TISL',
        locomotiva_data['line_labels'],
        [
            {'label': 'Real SF', 'data': locomotiva_data['real_sf']},
            {'label': 'Real GG', 'data': locomotiva_data['real_gg']},
            {'label': 'Estoque SF', 'data': locomotiva_data['estoque_sf']},
            {'label': 'Estoque GG', 'data': locomotiva_data['estoque_gg']},
        ],
        kind='line'
    )

    tcs1 = os.path.join(temp_dir, 'tcs_estoque.png')
    save_chart(
        tcs1,
        f"ESTOQUE (t) {locomotiva_tcs_data['stock_title_date']}",
        locomotiva_tcs_data['estoque_bar_labels'],
        [{'label': 'Estoque SF', 'data': locomotiva_tcs_data['estoque_bar_values']}],
        kind='hbar'
    )
    tcs2 = os.path.join(temp_dir, 'tcs_evolucao.png')
    save_chart(
        tcs2,
        f"CONTROLE TCS - {locomotiva_tcs_data['control_title_date']}",
        locomotiva_tcs_data['line_labels'],
        [
            {'label': 'Real SF', 'data': locomotiva_tcs_data['real_sf']},
            {'label': 'Estoque SF', 'data': locomotiva_tcs_data['estoque_sf']},
        ],
        kind='line'
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1*cm, leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Small', fontSize=9, leading=11))
    styles.add(ParagraphStyle(name='TitleBlue', fontSize=20, leading=24, textColor=colors.HexColor('#0f5d73')))
    story = []

    def add_header(title, subtitle=None):
        story.append(Paragraph(title, styles['TitleBlue']))
        if subtitle:
            story.append(Paragraph(subtitle, styles['Small']))
        story.append(Spacer(1, 0.3*cm))

    add_header("Exportação de Dashboards", f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
    resumo = [
        ['Indicador', 'Valor'],
        ['Registros', str(total_registros)],
        ['Plano', _fmt_num_br(total_plano)],
        ['D+1', _fmt_num_br(total_d1)],
        ['Real', _fmt_num_br(total_real)],
        ['Dif.', _fmt_num_br(total_dif)],
        ['Ader.', f"{total_ader:.0f}%"],
    ]
    resumo_tbl = Table(resumo, colWidths=[6*cm, 5*cm])
    resumo_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f5d73')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
    ]))
    story.append(resumo_tbl)
    story.append(Spacer(1, 0.4*cm))
    story.append(Image(principal_path, width=24*cm, height=9*cm))
    story.append(Spacer(1, 0.4*cm))

    detalhes = [['Produto','Cliente','Terminal','Termo','Plano','D+1','Real','Dif.','Ader.']]
    for item in tabela_total[:18]:
        dif = float(item.real or 0) - float(item.plano or 0)
        ader = ((float(item.real or 0) / float(item.plano or 0)) * 100) if float(item.plano or 0) else 0
        detalhes.append([
            item.produto, item.cliente, item.terminal or '-', item.termo or '-',
            _fmt_num_br(item.plano), _fmt_num_br(item.d1), _fmt_num_br(item.real),
            _fmt_num_br(dif), f"{ader:.0f}%"
        ])
    det_tbl = Table(detalhes, repeatRows=1, colWidths=[2.2*cm,4*cm,2.2*cm,2.2*cm,2.2*cm,2.2*cm,2.2*cm,2.2*cm,1.8*cm])
    det_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f5d73')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#d0d0d0')),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (4,1), (-1,-1), 'RIGHT'),
    ]))
    story.append(det_tbl)

    story.append(PageBreak())
    add_header("Dashboard Locomotiva", "Base AMT / TISL")
    story.append(Image(loco1, width=12*cm, height=5*cm))
    story.append(Spacer(1, 0.2*cm))
    story.append(Image(loco2, width=24*cm, height=9.5*cm))

    story.append(PageBreak())
    add_header("Dashboard Locomotiva TCS", "Base Terminal TCS")
    story.append(Image(tcs1, width=12*cm, height=5*cm))
    story.append(Spacer(1, 0.2*cm))
    story.append(Image(tcs2, width=24*cm, height=9.5*cm))

    doc.build(story)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name='dashboards_logistica.pdf',
        mimetype='application/pdf'
    )




@main_bp.route('/planejado-locomotiva', methods=['GET', 'POST'])
@login_required
def planejado_locomotiva():
    hoje = date.today()
    data_inicio_txt = request.values.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d')).strip()
    data_fim_txt = request.values.get('data_fim', hoje.strftime('%Y-%m-%d')).strip()
    locomotiva_tipo = request.values.get('locomotiva_tipo', 'tisl').strip().lower()

    if locomotiva_tipo not in ['tisl', 'tcs']:
        locomotiva_tipo = 'tisl'

    data_inicio = parse_date(data_inicio_txt)
    data_fim = parse_date(data_fim_txt)
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
        data_inicio_txt, data_fim_txt = data_inicio.strftime('%Y-%m-%d'), data_fim.strftime('%Y-%m-%d')

    if request.method == 'POST':
        if not current_user.is_admin:
            flash('Somente administradores podem alterar o planejado da locomotiva.', 'danger')
            return redirect(url_for('main.planejado_locomotiva', data_inicio=data_inicio_txt, data_fim=data_fim_txt, locomotiva_tipo=locomotiva_tipo))

        current = data_inicio
        while current <= data_fim:
            key = current.strftime('%Y-%m-%d')
            plano_ferro = parse_float_br(request.form.get(f'plano_ferro_{key}', '0'))
            real_ferro = parse_float_br(request.form.get(f'real_ferro_{key}', '0'))

            item = (
                PlanejadoLocomotivaEntry.query
                .filter_by(locomotiva_tipo=locomotiva_tipo, data_referencia=current)
                .first()
            )
            if not item:
                item = PlanejadoLocomotivaEntry(locomotiva_tipo=locomotiva_tipo, data_referencia=current)
                db.session.add(item)

            item.plano_ferro = plano_ferro
            item.real_ferro = real_ferro
            current += timedelta(days=1)

        db.session.commit()
        flash('Planejado da locomotiva salvo com sucesso.', 'success')
        return redirect(url_for('main.planejado_locomotiva', data_inicio=data_inicio_txt, data_fim=data_fim_txt, locomotiva_tipo=locomotiva_tipo))

    rows = build_planejado_locomotiva_rows(locomotiva_tipo, data_inicio, data_fim)
    return render_template(
        'planejado_locomotiva.html',
        data_inicio=data_inicio_txt,
        data_fim=data_fim_txt,
        locomotiva_tipo=locomotiva_tipo,
        rows=rows,
    )

