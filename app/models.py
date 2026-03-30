from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='reader')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @classmethod
    def create_default_admin(cls):
        admin = cls.query.filter_by(username='admin').first()
        if not admin:
            admin = cls(username='admin', full_name='Administrador', role='admin', active=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()


class LogisticsRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto = db.Column(db.String(50), nullable=False)
    cliente = db.Column(db.String(120), nullable=False)
    terminal = db.Column(db.String(50), nullable=True)
    termo = db.Column(db.String(20), nullable=True)
    data_referencia = db.Column(db.Date, nullable=False)
    dia_semana = db.Column(db.String(30), nullable=False)
    plano = db.Column(db.Float, default=0)
    d1 = db.Column(db.Float, default=0)
    real = db.Column(db.Float, default=0)
    observacao = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class LocomotivaEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date, unique=True, nullable=False, index=True)
    trem_sf = db.Column(db.Float, default=0)
    trem_gg = db.Column(db.Float, default=0)
    estoque_sf = db.Column(db.Float, default=0)
    estoque_gg = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class LocomotivaTCSEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_referencia = db.Column(db.Date, unique=True, nullable=False, index=True)
    trem_sf = db.Column(db.Float, default=0)
    estoque_sf = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class PlanejadoLocomotivaEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    locomotiva_tipo = db.Column(db.String(20), nullable=False, index=True)  # 'tisl' ou 'tcs'
    data_referencia = db.Column(db.Date, nullable=False, index=True)
    plano_ferro = db.Column(db.Float, default=0)
    real_ferro = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('locomotiva_tipo', 'data_referencia', name='uq_planejado_locomotiva_tipo_data'),
    )
