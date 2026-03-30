from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from .models import User


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username, active=True).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Login realizado com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Usuário ou senha inválidos.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))
