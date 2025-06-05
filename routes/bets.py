import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, User, Bet, UserBet
from blockchain import Blockchain

bets = Blueprint('bets', __name__)

@bets.route('/create_bet', methods=['GET', 'POST'])
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
            return redirect(url_for('bets.create_bet'))

        try:
            expiration_date = datetime.datetime.strptime(expiration_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date format for expiration date. Use YYYY-MM-DDTHH:MM.', 'danger')
            return redirect(url_for('bets.create_bet'))

        outcomes_list = [o.strip() for o in outcomes_str.split(',') if o.strip()]
        if not outcomes_list or len(outcomes_list) < 2:
            flash('Please provide at least two comma-separated outcomes.', 'danger')
            return redirect(url_for('bets.create_bet'))

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
        return redirect(url_for('main.index'))
    return render_template('create_bet.html')

@bets.route('/place_bet/<int:bet_id>', methods=['POST'])
@login_required
def place_bet(bet_id):
    bet = Bet.query.get_or_404(bet_id)
    if bet.resolved:
        flash('This bet has already been resolved.', 'warning')
        return redirect(url_for('main.index'))
    if datetime.datetime.now() > bet.expiration_date:
        flash('This bet has expired.', 'warning')
        return redirect(url_for('main.index'))

    chosen_outcome = request.form.get('chosen_outcome')
    if not chosen_outcome or chosen_outcome not in bet.get_outcomes_list():
        flash('Invalid outcome selected.', 'danger')
        return redirect(url_for('main.index'))

    existing_bet = UserBet.query.filter_by(user_id=current_user.id, bet_id=bet_id).first()
    if existing_bet:
        flash('You have already placed a bet on this item.', 'warning')
        return redirect(url_for('main.index'))

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
    return redirect(url_for('bets.bet_details', bet_id=bet_id))

@bets.route('/resolve_bet/<int:bet_id>', methods=['POST'])
@login_required
def resolve_bet(bet_id):
    bet = Bet.query.get_or_404(bet_id)
    if bet.creator_id != current_user.id:
        flash('You are not authorized to resolve this bet.', 'danger')
        return redirect(url_for('main.index'))
    if bet.resolved:
        flash('This bet has already been resolved.', 'warning')
        return redirect(url_for('main.index'))

    winning_outcome = request.form.get('winning_outcome')
    if not winning_outcome or winning_outcome not in bet.get_outcomes_list():
        flash('Invalid winning outcome selected.', 'danger')
        return redirect(url_for('main.index'))

    bet.resolved = True
    bet.winning_outcome = winning_outcome

    # Update win/loss records and award blocks to winners
    winners = []
    losers = []
    total_participants = bet.user_bets.count()
    blocks_per_winner = max(1, total_participants // 2)  # Award more blocks for more competitive bets
    
    for user_bet_record in bet.user_bets:
        user = User.query.get(user_bet_record.user_id)
        if user:
            if user_bet_record.chosen_outcome == winning_outcome:
                user.wins = (user.wins or 0) + 1
                user.block_balance = (user.block_balance or 0) + blocks_per_winner
                winners.append({'user_id': user.id, 'name': user.name, 'chosen_outcome': user_bet_record.chosen_outcome, 'blocks_earned': blocks_per_winner})
            else:
                user.losses = (user.losses or 0) + 1
                losers.append({'user_id': user.id, 'name': user.name, 'chosen_outcome': user_bet_record.chosen_outcome})

    db.session.commit()
    
    # Add blockchain transactions for block rewards
    for winner in winners:
        reward_data = {
            'bet_id': bet_id,
            'bet_title': bet.title,
            'winner_id': winner['user_id'],
            'blocks_awarded': winner['blocks_earned'],
            'total_participants': total_participants,
            'reward_time': datetime.datetime.now().isoformat()
        }
        Blockchain.add_transaction('block_reward', user_id=winner['user_id'], bet_id=bet_id, data=reward_data)
    
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
    return redirect(url_for('bets.bet_details', bet_id=bet_id))

@bets.route('/bet/<int:bet_id>')
def bet_details(bet_id):
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('auth.access_page'))
    
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