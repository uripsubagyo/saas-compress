from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    subscription_tier = db.Column(db.String(50), default='free') # 'free' or 'pro'
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    daily_usage_count = db.Column(db.Integer, default=0)
    last_usage_date = db.Column(db.Date, nullable=True)
