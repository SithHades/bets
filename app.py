import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import datetime
import bcrypt

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
    flash(f'You have successfully bet on "{chosen_outcome}"!', 'success')
    return redirect(url_for('index'))


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
    for user_bet_record in bet.user_bets:
        user = User.query.get(user_bet_record.user_id)
        if user:
            if user_bet_record.chosen_outcome == winning_outcome:
                user.wins = (user.wins or 0) + 1
            else:
                user.losses = (user.losses or 0) + 1

    db.session.commit()
    flash(f'Bet "{bet.title}" resolved. Winning outcome: {winning_outcome}', 'success')
    return redirect(url_for('index'))

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

if __name__ == '__main__':
    app.run(debug=True) 