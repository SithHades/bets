import bcrypt
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    bets_placed = db.relationship('UserBet', backref='user', lazy='dynamic')
    created_bets = db.relationship('Bet', backref='creator', lazy='dynamic')
    wins = db.Column(db.Integer, default=0, nullable=False)
    losses = db.Column(db.Integer, default=0, nullable=False)
    block_balance = db.Column(db.Integer, default=0, nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=False)
    outcomes = db.Column(db.String(500), nullable=False) # Comma-separated string of outcomes
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resolved = db.Column(db.Boolean, default=False, nullable=False)
    winning_outcome = db.Column(db.String(100), nullable=True)
    user_bets = db.relationship('UserBet', backref='bet', lazy='dynamic')

    def get_outcomes_list(self):
        return [o.strip() for o in self.outcomes.split(',')]

class UserBet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bet_id = db.Column(db.Integer, db.ForeignKey('bet.id'), nullable=False)
    chosen_outcome = db.Column(db.String(100), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'bet_id', name='_user_bet_uc'),)

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.Integer, nullable=False, unique=True)
    timestamp = db.Column(db.Float, nullable=False)
    previous_hash = db.Column(db.String(64), nullable=False)
    hash = db.Column(db.String(64), nullable=False, unique=True)
    nonce = db.Column(db.Integer, nullable=False, default=0)
    merkle_root = db.Column(db.String(64), nullable=False)
    transactions = db.relationship('Transaction', backref='block', lazy='dynamic')

    def calculate_hash(self):
        import hashlib
        block_string = f"{self.index}{self.timestamp}{self.previous_hash}{self.merkle_root}{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty=4):
        target = "0" * difficulty
        self.hash = self.calculate_hash()
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    block_id = db.Column(db.Integer, db.ForeignKey('block.id'), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # 'user_registration', 'bet_creation', 'bet_placement', 'bet_resolution'
    user_id = db.Column(db.Integer, nullable=True)
    bet_id = db.Column(db.Integer, nullable=True)
    data = db.Column(db.Text, nullable=False)  # JSON string containing transaction details
    hash = db.Column(db.String(64), nullable=False, unique=True)
    timestamp = db.Column(db.Float, nullable=False)

    def calculate_hash(self):
        import hashlib
        transaction_string = f"{self.transaction_type}{self.user_id}{self.bet_id}{self.data}{self.timestamp}"
        return hashlib.sha256(transaction_string.encode()).hexdigest()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.timestamp:
            import time
            self.timestamp = time.time()
        if not self.hash:
            self.hash = self.calculate_hash()

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    block_cost = db.Column(db.Integer, nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='available', nullable=False)  # 'available', 'pending', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    provider = db.relationship('User', backref='services_offered', lazy=True)

class ServiceTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocks_spent = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # 'pending', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    completed_at = db.Column(db.DateTime, nullable=True)
    service = db.relationship('Service', backref='transactions', lazy=True)
    buyer = db.relationship('User', backref='service_purchases', lazy=True)