from flask import Blueprint, render_template, redirect, url_for, session
from flask_login import login_required, current_user
from models import User, Bet, UserBet

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('auth.access_page'))

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

@main.route('/leaderboard')
@login_required # Or remove @login_required if leaderboard should be public (after gatekeeper)
def leaderboard():
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('auth.access_page')) # Protect leaderboard if not logged in
        
    users = User.query.order_by(User.wins.desc(), User.losses.asc()).all()
    return render_template('leaderboard.html', users=users)