import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import datetime
import bcrypt
import hashlib
import json
import time

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_fallback_secret_key_for_development')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

DEFAULT_SIGNUP_PASSWORD = os.environ.get('DEFAULT_SIGNUP_PASSWORD')

@app.context_processor
def inject_global_template_variables():
    return {
        'current_year': datetime.datetime.now().year,
        'current_server_time': datetime.datetime.now()
    }

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    bets_placed = db.relationship('UserBet', backref='user', lazy='dynamic')
    created_bets = db.relationship('Bet', backref='creator', lazy='dynamic')
    wins = db.Column(db.Integer, default=0, nullable=False)
    losses = db.Column(db.Integer, default=0, nullable=False)

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

# Blockchain Models
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
        transaction_string = f"{self.transaction_type}{self.user_id}{self.bet_id}{self.data}{self.timestamp}"
        return hashlib.sha256(transaction_string.encode()).hexdigest()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.hash:
            self.hash = self.calculate_hash()


# Blockchain Core Functions
class Blockchain:
    @staticmethod
    def create_genesis_block():
        """Create the first block in the blockchain"""
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            previous_hash="0",
            merkle_root="0",
            nonce=0
        )
        genesis_block.hash = genesis_block.calculate_hash()
        return genesis_block

    @staticmethod
    def get_latest_block():
        """Get the most recent block in the chain"""
        return Block.query.order_by(Block.index.desc()).first()

    @staticmethod
    def create_merkle_root(transactions):
        """Create a merkle root from a list of transactions"""
        if not transactions:
            return "0"
        
        transaction_hashes = [tx.hash for tx in transactions]
        
        while len(transaction_hashes) > 1:
            next_level = []
            for i in range(0, len(transaction_hashes), 2):
                if i + 1 < len(transaction_hashes):
                    combined = transaction_hashes[i] + transaction_hashes[i + 1]
                else:
                    combined = transaction_hashes[i] + transaction_hashes[i]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            transaction_hashes = next_level
        
        return transaction_hashes[0]

    @staticmethod
    def add_block(transactions):
        """Add a new block to the blockchain with the given transactions"""
        latest_block = Blockchain.get_latest_block()
        if not latest_block:
            # Create genesis block if none exists
            genesis = Blockchain.create_genesis_block()
            db.session.add(genesis)
            db.session.commit()
            latest_block = genesis

        merkle_root = Blockchain.create_merkle_root(transactions)
        
        new_block = Block(
            index=latest_block.index + 1,
            timestamp=time.time(),
            previous_hash=latest_block.hash,
            merkle_root=merkle_root,
            nonce=0
        )
        
        new_block.mine_block(difficulty=4)
        db.session.add(new_block)
        db.session.flush()  # Get the block ID
        
        # Assign transactions to this block
        for tx in transactions:
            tx.block_id = new_block.id
            db.session.add(tx)
        
        db.session.commit()
        return new_block

    @staticmethod
    def validate_chain():
        """Validate the entire blockchain"""
        blocks = Block.query.order_by(Block.index.asc()).all()
        
        for i in range(1, len(blocks)):
            current_block = blocks[i]
            previous_block = blocks[i - 1]
            
            # Check if current block's hash is valid
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check if current block points to previous block
            if current_block.previous_hash != previous_block.hash:
                return False
            
            # Validate merkle root
            block_transactions = Transaction.query.filter_by(block_id=current_block.id).all()
            if current_block.merkle_root != Blockchain.create_merkle_root(block_transactions):
                return False
        
        return True

    @staticmethod
    def add_transaction(transaction_type, user_id=None, bet_id=None, data=None):
        """Create and add a transaction to pending transactions"""
        transaction = Transaction(
            transaction_type=transaction_type,
            user_id=user_id,
            bet_id=bet_id,
            data=json.dumps(data) if data else "{}"
        )
        
        # For simplicity, we'll immediately create a block for each transaction
        # In a real blockchain, transactions would be batched
        Blockchain.add_block([transaction])
        return transaction

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('access_page'))

    active_bets = Bet.query.filter_by(resolved=False).order_by(Bet.expiration_date.desc()).all()
    resolved_bets = Bet.query.filter_by(resolved=True).order_by(Bet.expiration_date.desc()).all()

    bet_data = []
    for bet in active_bets + resolved_bets:
        outcome_counts = {outcome: 0 for outcome in bet.get_outcomes_list()}
        total_bets_on_this_bet = 0
        user_bets_on_this = UserBet.query.filter_by(bet_id=bet.id).all()
        users_who_betted = []

        for user_bet in user_bets_on_this:
            if user_bet.chosen_outcome in outcome_counts:
                outcome_counts[user_bet.chosen_outcome] += 1
            total_bets_on_this_bet += 1
            user_b = User.query.get(user_bet.user_id)
            if user_b:
                 users_who_betted.append(user_b.name)

        outcome_percentages = {}
        if total_bets_on_this_bet > 0:
            for outcome, count in outcome_counts.items():
                outcome_percentages[outcome] = (count / total_bets_on_this_bet) * 100
        else:
            for outcome in bet.get_outcomes_list():
                outcome_percentages[outcome] = 0

        bet_data.append({
            'bet': bet,
            'outcome_percentages': outcome_percentages,
            'users_who_betted': list(set(users_who_betted)),
            'total_bets_on_this_bet': total_bets_on_this_bet
        })
    return render_template('index.html', bet_data=bet_data)

@app.route('/access', methods=['GET', 'POST'])
def access_page():
    if session.get('has_passed_gate') or current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        access_password = request.form.get('access_password')
        if not DEFAULT_SIGNUP_PASSWORD:
            flash('Site access password is not configured on the server.', 'danger')
            return render_template('access_page.html')

        if access_password == DEFAULT_SIGNUP_PASSWORD:
            session['has_passed_gate'] = True
            flash('Access granted.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Incorrect access password.', 'danger')
    return render_template('access_page.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        signup_password = request.form.get('signup_password')

        if not DEFAULT_SIGNUP_PASSWORD:
            flash('Sign-up password is not configured on the server.', 'danger')
            return redirect(url_for('register'))

        if signup_password != DEFAULT_SIGNUP_PASSWORD:
            flash('Invalid sign-up password.', 'danger')
            return redirect(url_for('register'))

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email address already registered.', 'warning')
            return redirect(url_for('register'))

        new_user = User(name=name, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        # Add blockchain transaction for user registration
        user_data = {
            'name': name,
            'email': email,
            'registration_time': datetime.datetime.now().isoformat()
        }
        Blockchain.add_transaction('user_registration', user_id=new_user.id, data=user_data)
        
        session.pop('has_passed_gate', None) # Clear gate pass after registration
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            session.pop('has_passed_gate', None) # Clear gate pass after successful login
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('has_passed_gate', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login')) # Redirect to login, which will then check gate or auth

@app.route('/create_bet', methods=['GET', 'POST'])
@login_required
def create_bet():
    # Gatekeeper check for index page should suffice; direct access to create_bet requires login.
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        expiration_date_str = request.form.get('expiration_date')
        outcomes_str = request.form.get('outcomes')

        if not all([title, expiration_date_str, outcomes_str]):
            flash('Title, expiration date, and outcomes are required.', 'danger')
            return redirect(url_for('create_bet'))

        try:
            expiration_date = datetime.datetime.strptime(expiration_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format for expiration date. Use YYYY-MM-DDTHH:MM.', 'danger')
            return redirect(url_for('create_bet'))

        outcomes_list = [o.strip() for o in outcomes_str.split(',') if o.strip()]
        if not outcomes_list or len(outcomes_list) < 2:
            flash('Please provide at least two comma-separated outcomes.', 'danger')
            return redirect(url_for('create_bet'))

        new_bet = Bet(
            title=title,
            description=description,
            expiration_date=expiration_date,
            outcomes=','.join(outcomes_list),
            creator_id=current_user.id
        )
        db.session.add(new_bet)
        db.session.commit()
        
        # Add blockchain transaction for bet creation
        bet_data = {
            'title': title,
            'description': description,
            'expiration_date': expiration_date.isoformat(),
            'outcomes': outcomes_list,
            'creator_id': current_user.id,
            'creation_time': datetime.datetime.now().isoformat()
        }
        Blockchain.add_transaction('bet_creation', user_id=current_user.id, bet_id=new_bet.id, data=bet_data)
        
        flash('Bet created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('create_bet.html')

@app.route('/place_bet/<int:bet_id>', methods=['POST'])
@login_required
def place_bet(bet_id):
    bet = Bet.query.get_or_404(bet_id)
    if bet.resolved:
        flash('This bet has already been resolved.', 'warning')
        return redirect(url_for('index'))
    if datetime.datetime.now() > bet.expiration_date:
        flash('This bet has expired.', 'warning')
        return redirect(url_for('index'))

    chosen_outcome = request.form.get('chosen_outcome')
    if not chosen_outcome or chosen_outcome not in bet.get_outcomes_list():
        flash('Invalid outcome selected.', 'danger')
        return redirect(url_for('index'))

    existing_bet = UserBet.query.filter_by(user_id=current_user.id, bet_id=bet_id).first()
    if existing_bet:
        flash('You have already placed a bet on this item.', 'warning')
        return redirect(url_for('index'))

    new_user_bet = UserBet(user_id=current_user.id, bet_id=bet_id, chosen_outcome=chosen_outcome)
    db.session.add(new_user_bet)
    db.session.commit()
    
    # Add blockchain transaction for bet placement
    bet_placement_data = {
        'user_id': current_user.id,
        'bet_id': bet_id,
        'chosen_outcome': chosen_outcome,
        'bet_title': bet.title,
        'placement_time': datetime.datetime.now().isoformat()
    }
    Blockchain.add_transaction('bet_placement', user_id=current_user.id, bet_id=bet_id, data=bet_placement_data)
    
    flash(f'You have successfully bet on "{chosen_outcome}"!', 'success')
    return redirect(url_for('bet_details', bet_id=bet_id))


@app.route('/resolve_bet/<int:bet_id>', methods=['POST'])
@login_required
def resolve_bet(bet_id):
    bet = Bet.query.get_or_404(bet_id)
    if bet.creator_id != current_user.id:
        flash('You are not authorized to resolve this bet.', 'danger')
        return redirect(url_for('index'))
    if bet.resolved:
        flash('This bet has already been resolved.', 'warning')
        return redirect(url_for('index'))

    winning_outcome = request.form.get('winning_outcome')
    if not winning_outcome or winning_outcome not in bet.get_outcomes_list():
        flash('Invalid winning outcome selected.', 'danger')
        return redirect(url_for('index'))

    bet.resolved = True
    bet.winning_outcome = winning_outcome

    # Update win/loss records for participants
    winners = []
    losers = []
    for user_bet_record in bet.user_bets:
        user = User.query.get(user_bet_record.user_id)
        if user:
            if user_bet_record.chosen_outcome == winning_outcome:
                user.wins = (user.wins or 0) + 1
                winners.append({'user_id': user.id, 'name': user.name, 'chosen_outcome': user_bet_record.chosen_outcome})
            else:
                user.losses = (user.losses or 0) + 1
                losers.append({'user_id': user.id, 'name': user.name, 'chosen_outcome': user_bet_record.chosen_outcome})

    db.session.commit()
    
    # Add blockchain transaction for bet resolution
    resolution_data = {
        'bet_id': bet_id,
        'bet_title': bet.title,
        'winning_outcome': winning_outcome,
        'resolver_id': current_user.id,
        'winners': winners,
        'losers': losers,
        'resolution_time': datetime.datetime.now().isoformat()
    }
    Blockchain.add_transaction('bet_resolution', user_id=current_user.id, bet_id=bet_id, data=resolution_data)
    
    flash(f'Bet "{bet.title}" resolved. Winning outcome: {winning_outcome}', 'success')
    return redirect(url_for('bet_details', bet_id=bet_id))

@app.route('/bet/<int:bet_id>')
def bet_details(bet_id):
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('access_page'))
    
    bet = Bet.query.get_or_404(bet_id)
    
    # Calculate detailed statistics
    user_bets_on_this = UserBet.query.filter_by(bet_id=bet_id).all()
    outcome_counts = {outcome: 0 for outcome in bet.get_outcomes_list()}
    total_bets_on_this_bet = len(user_bets_on_this)
    users_by_outcome = {outcome: [] for outcome in bet.get_outcomes_list()}
    
    for user_bet in user_bets_on_this:
        if user_bet.chosen_outcome in outcome_counts:
            outcome_counts[user_bet.chosen_outcome] += 1
        user = User.query.get(user_bet.user_id)
        if user and user_bet.chosen_outcome in users_by_outcome:
            users_by_outcome[user_bet.chosen_outcome].append(user)
    
    outcome_percentages = {}
    if total_bets_on_this_bet > 0:
        for outcome, count in outcome_counts.items():
            outcome_percentages[outcome] = (count / total_bets_on_this_bet) * 100
    else:
        for outcome in bet.get_outcomes_list():
            outcome_percentages[outcome] = 0
    
    # Check if current user has placed a bet
    user_bet = None
    if current_user.is_authenticated:
        user_bet = UserBet.query.filter_by(user_id=current_user.id, bet_id=bet_id).first()
    
    # Calculate time remaining
    time_remaining = None
    if not bet.resolved and bet.expiration_date > datetime.datetime.now():
        time_remaining = bet.expiration_date - datetime.datetime.now()
    
    bet_data = {
        'bet': bet,
        'outcome_counts': outcome_counts,
        'outcome_percentages': outcome_percentages,
        'users_by_outcome': users_by_outcome,
        'total_bets': total_bets_on_this_bet,
        'user_bet': user_bet,
        'time_remaining': time_remaining,
        'is_expired': datetime.datetime.now() > bet.expiration_date,
        'can_bet': (current_user.is_authenticated and 
                   not bet.resolved and 
                   datetime.datetime.now() <= bet.expiration_date and
                   not user_bet),
        'can_resolve': (current_user.is_authenticated and 
                       current_user.id == bet.creator_id and 
                       not bet.resolved)
    }
    
    return render_template('bet_details.html', **bet_data)

@app.route('/blockchain')
def blockchain_explorer():
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('access_page'))
    
    blocks = Block.query.order_by(Block.index.desc()).all()
    chain_valid = Blockchain.validate_chain()
    
    block_data = []
    for block in blocks:
        transactions = Transaction.query.filter_by(block_id=block.id).all()
        transaction_data = []
        
        for tx in transactions:
            tx_data = {
                'hash': tx.hash,
                'type': tx.transaction_type,
                'user_id': tx.user_id,
                'bet_id': tx.bet_id,
                'data': json.loads(tx.data),
                'timestamp': datetime.datetime.fromtimestamp(tx.timestamp)
            }
            transaction_data.append(tx_data)
        
        block_info = {
            'block': block,
            'transactions': transaction_data,
            'transaction_count': len(transaction_data),
            'timestamp': datetime.datetime.fromtimestamp(block.timestamp)
        }
        block_data.append(block_info)
    
    return render_template('blockchain.html', 
                         block_data=block_data, 
                         chain_valid=chain_valid,
                         total_blocks=len(blocks))

@app.route('/api/blockchain')
def api_blockchain():
    """API endpoint for blockchain data"""
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return jsonify({'error': 'Access denied'}), 403
    
    blocks = Block.query.order_by(Block.index.asc()).all()
    chain_data = []
    
    for block in blocks:
        transactions = Transaction.query.filter_by(block_id=block.id).all()
        tx_data = []
        
        for tx in transactions:
            tx_info = {
                'hash': tx.hash,
                'type': tx.transaction_type,
                'user_id': tx.user_id,
                'bet_id': tx.bet_id,
                'data': json.loads(tx.data),
                'timestamp': tx.timestamp
            }
            tx_data.append(tx_info)
        
        block_info = {
            'index': block.index,
            'timestamp': block.timestamp,
            'previous_hash': block.previous_hash,
            'hash': block.hash,
            'nonce': block.nonce,
            'merkle_root': block.merkle_root,
            'transactions': tx_data
        }
        chain_data.append(block_info)
    
    return jsonify({
        'blockchain': chain_data,
        'valid': Blockchain.validate_chain(),
        'length': len(chain_data)
    })

@app.route('/leaderboard')
@login_required # Or remove @login_required if leaderboard should be public (after gatekeeper)
def leaderboard():
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('access_page')) # Protect leaderboard if not logged in
        
    users = User.query.order_by(User.wins.desc(), User.losses.asc()).all()
    return render_template('leaderboard.html', users=users)

def create_tables():
    with app.app_context():
        db.create_all()

@app.cli.command("init-db")
def init_db_command():
    """Clear existing data and create new tables."""
    create_tables()
    print("Initialized the database.")

@app.cli.command("migrate-to-blockchain")
def migrate_to_blockchain_command():
    """Migrate existing betting data to blockchain transactions."""
    with app.app_context():
        # Create genesis block if it doesn't exist
        if not Block.query.first():
            genesis = Blockchain.create_genesis_block()
            db.session.add(genesis)
            db.session.commit()
            print("Created genesis block.")
        
        # Check if we already have transactions
        existing_transactions = Transaction.query.count()
        if existing_transactions > 0:
            print(f"Found {existing_transactions} existing blockchain transactions.")
            print("Blockchain already migrated - skipping migration to avoid duplicates.")
            return
        
        transactions_created = 0
        
        # Migrate user registrations
        users = User.query.order_by(User.id.asc()).all()
        print(f"Migrating {len(users)} users...")
        for user in users:
            user_data = {
                'name': user.name,
                'email': user.email,
                'registration_time': datetime.datetime.now().isoformat(),
                'migrated': True
            }
            Blockchain.add_transaction('user_registration', user_id=user.id, data=user_data)
            transactions_created += 1
        
        # Migrate bet creations
        bets = Bet.query.order_by(Bet.id.asc()).all()
        print(f"Migrating {len(bets)} bet creations...")
        for bet in bets:
            bet_data = {
                'title': bet.title,
                'description': bet.description,
                'expiration_date': bet.expiration_date.isoformat(),
                'outcomes': bet.get_outcomes_list(),
                'creator_id': bet.creator_id,
                'creation_time': datetime.datetime.now().isoformat(),
                'migrated': True
            }
            Blockchain.add_transaction('bet_creation', user_id=bet.creator_id, bet_id=bet.id, data=bet_data)
            transactions_created += 1
        
        # Migrate bet placements
        user_bets = UserBet.query.order_by(UserBet.id.asc()).all()
        print(f"Migrating {len(user_bets)} bet placements...")
        for user_bet in user_bets:
            bet = Bet.query.get(user_bet.bet_id)
            bet_placement_data = {
                'user_id': user_bet.user_id,
                'bet_id': user_bet.bet_id,
                'chosen_outcome': user_bet.chosen_outcome,
                'bet_title': bet.title if bet else 'Unknown',
                'placement_time': datetime.datetime.now().isoformat(),
                'migrated': True
            }
            Blockchain.add_transaction('bet_placement', user_id=user_bet.user_id, bet_id=user_bet.bet_id, data=bet_placement_data)
            transactions_created += 1
        
        # Migrate bet resolutions
        resolved_bets = Bet.query.filter_by(resolved=True).order_by(Bet.id.asc()).all()
        print(f"Migrating {len(resolved_bets)} bet resolutions...")
        for bet in resolved_bets:
            winners = []
            losers = []
            for user_bet_record in bet.user_bets:
                user = User.query.get(user_bet_record.user_id)
                if user:
                    if user_bet_record.chosen_outcome == bet.winning_outcome:
                        winners.append({'user_id': user.id, 'name': user.name, 'chosen_outcome': user_bet_record.chosen_outcome})
                    else:
                        losers.append({'user_id': user.id, 'name': user.name, 'chosen_outcome': user_bet_record.chosen_outcome})
            
            resolution_data = {
                'bet_id': bet.id,
                'bet_title': bet.title,
                'winning_outcome': bet.winning_outcome,
                'resolver_id': bet.creator_id,
                'winners': winners,
                'losers': losers,
                'resolution_time': datetime.datetime.now().isoformat(),
                'migrated': True
            }
            Blockchain.add_transaction('bet_resolution', user_id=bet.creator_id, bet_id=bet.id, data=resolution_data)
            transactions_created += 1
        
        print("\nMigration completed!")
        print(f"Created {transactions_created} blockchain transactions.")
        print(f"Total blocks in chain: {Block.query.count()}")
        print(f"Chain is valid: {Blockchain.validate_chain()}")

if __name__ == '__main__':
    app.run(debug=True) 