from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import LogisticsRecord
from .utils import admin_required, week_day_pt


records_bp = Blueprint('records', __name__, url_prefix='/registros')


def parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


def produto_class(produto):
    produto = (produto or '').strip().lower()
    mapa = {
        'sinter': 'produto-sinter',
        'npo': 'produto-npo',
        'htt': 'produto-htt',
    }
    return mapa.get(produto, 'produto-default')


@records_bp.app_context_processor
def inject_helpers():
    return {'produto_class': produto_class}


@records_bp.route('/')
@login_required
def list_records():
    query = LogisticsRecord.query

    produto = request.args.get('produto', '').strip()
    cliente = request.args.get('cliente', '').strip()
    data_inicio = request.args.get('data_inicio', '').strip()
    data_fim = request.args.get('data_fim', '').strip()

    if produto:
        query = query.filter(LogisticsRecord.produto.ilike(f'%{produto}%'))
    if cliente:
        query = query.filter(LogisticsRecord.cliente.ilike(f'%{cliente}%'))
    if data_inicio:
        query = query.filter(LogisticsRecord.data_referencia >= parse_date(data_inicio))
    if data_fim:
        query = query.filter(LogisticsRecord.data_referencia <= parse_date(data_fim))

    records = query.order_by(LogisticsRecord.data_referencia.desc(), LogisticsRecord.id.desc()).all()
    return render_template('records.html', records=records)


@records_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def create_record():
    if request.method == 'POST':
        data_referencia = parse_date(request.form['data_referencia'])
        record = LogisticsRecord(
            produto=request.form.get('produto', '').strip(),
            cliente=request.form.get('cliente', '').strip(),
            terminal=request.form.get('terminal', '').strip(),
            termo=request.form.get('termo', '').strip(),
            data_referencia=data_referencia,
            dia_semana=week_day_pt(data_referencia),
            plano=float(request.form.get('plano') or 0),
            d1=float(request.form.get('d1') or 0),
            real=float(request.form.get('real') or 0),
            observacao=request.form.get('observacao', '').strip(),
            created_by=current_user.username,
        )
        db.session.add(record)
        db.session.commit()
        flash('Registro cadastrado com sucesso.', 'success')
        return redirect(url_for('records.list_records'))

    return render_template('record_form.html', record=None)


@records_bp.route('/lancamento-em-massa', methods=['GET', 'POST'])
@login_required
@admin_required
def bulk_record():
    if request.method == 'POST':
        produto = request.form.get('produto', '').strip()
        cliente = request.form.get('cliente', '').strip()
        terminal = request.form.get('terminal', '').strip()
        termo = request.form.get('termo', '').strip()
        observacao = request.form.get('observacao', '').strip()
        total_salvos = 0

        for idx in range(1, 32):
            data_txt = request.form.get(f'data_{idx}', '').strip()
            if not data_txt:
                continue
            data_ref = parse_date(data_txt)
            record = LogisticsRecord(
                produto=produto,
                cliente=cliente,
                terminal=terminal,
                termo=termo,
                data_referencia=data_ref,
                dia_semana=week_day_pt(data_ref),
                plano=float(request.form.get(f'plano_{idx}') or 0),
                d1=float(request.form.get(f'd1_{idx}') or 0),
                real=float(request.form.get(f'real_{idx}') or 0),
                observacao=observacao,
                created_by=current_user.username,
            )
            db.session.add(record)
            total_salvos += 1

        db.session.commit()
        flash(f'{total_salvos} registro(s) lançados com sucesso.', 'success')
        return redirect(url_for('records.list_records'))

    modo = request.args.get('modo', 'semana')
    hoje = datetime.today().date()
    if modo == 'mes':
        inicio_txt = request.args.get('inicio')
        if inicio_txt:
            inicio = parse_date(inicio_txt).replace(day=1)
        else:
            inicio = hoje.replace(day=1)
        prox_mes = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
        quantidade = (prox_mes - inicio).days
    else:
        inicio_txt = request.args.get('inicio')
        if inicio_txt:
            inicio = parse_date(inicio_txt)
        else:
            inicio = hoje - timedelta(days=hoje.weekday())
        quantidade = 7

    dias = []
    for i in range(quantidade):
        dt = inicio + timedelta(days=i)
        dias.append({'idx': i+1, 'date': dt, 'weekday': week_day_pt(dt)})

    return render_template('bulk_record_form.html', dias=dias, modo=modo, inicio=inicio)


@records_bp.route('/<int:record_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_record(record_id):
    record = LogisticsRecord.query.get_or_404(record_id)

    if request.method == 'POST':
        data_referencia = parse_date(request.form['data_referencia'])
        record.produto = request.form.get('produto', '').strip()
        record.cliente = request.form.get('cliente', '').strip()
        record.terminal = request.form.get('terminal', '').strip()
        record.termo = request.form.get('termo', '').strip()
        record.data_referencia = data_referencia
        record.dia_semana = week_day_pt(data_referencia)
        record.plano = float(request.form.get('plano') or 0)
        record.d1 = float(request.form.get('d1') or 0)
        record.real = float(request.form.get('real') or 0)
        record.observacao = request.form.get('observacao', '').strip()
        db.session.commit()
        flash('Registro atualizado com sucesso.', 'success')
        return redirect(url_for('records.list_records'))

    return render_template('record_form.html', record=record)


@records_bp.route('/<int:record_id>/excluir', methods=['POST'])
@login_required
@admin_required
def delete_record(record_id):
    record = LogisticsRecord.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    flash('Registro excluído com sucesso.', 'info')
    return redirect(url_for('records.list_records'))
