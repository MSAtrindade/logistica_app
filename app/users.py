from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from . import db
from .models import User
from .utils import admin_required


users_bp = Blueprint('users', __name__, url_prefix='/usuarios')


@users_bp.route('/')
@login_required
@admin_required
def list_users():
    users = User.query.order_by(User.full_name.asc()).all()
    return render_template('users.html', users=users)


@users_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'reader')

        if not username or not full_name or not password:
            flash('Preencha todos os campos obrigatórios.', 'warning')
            return render_template('user_form.html', user=None)

        if User.query.filter_by(username=username).first():
            flash('Já existe um usuário com esse login.', 'danger')
            return render_template('user_form.html', user=None)

        user = User(username=username, full_name=full_name, role=role, active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Usuário cadastrado com sucesso.', 'success')
        return redirect(url_for('users.list_users'))

    return render_template('user_form.html', user=None)
