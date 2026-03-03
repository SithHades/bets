import json
from app import create_app
from models import db, Bet, UserBet, User, Transaction, Block, ServiceTransaction

app = create_app()

with app.app_context():
    resolved_bets = Bet.query.filter_by(resolved=True).all()

    for bet in resolved_bets:
        total_participants = bet.user_bets.count()
        winners = [ub for ub in bet.user_bets if ub.chosen_outcome == bet.winning_outcome]

        num_winners = len(winners)
        blocks_per_winner = total_participants // num_winners if num_winners > 0 else 0

        # update the transactions
        txs = Transaction.query.filter_by(bet_id=bet.id, transaction_type='block_reward').all()
        for tx in txs:
            data = json.loads(tx.data)
            data['blocks_awarded'] = blocks_per_winner
            tx.data = json.dumps(data)
            tx.hash = tx.calculate_hash()

    db.session.commit()

    # Recalculate block hashes and merkle roots
    blocks = Block.query.order_by(Block.index.asc()).all()
    for i in range(1, len(blocks)):
        block = blocks[i]
        prev_block = blocks[i-1]

        block.previous_hash = prev_block.hash
        # get all transactions for this block
        block_txs = Transaction.query.filter_by(block_id=block.id).all()
        from blockchain import Blockchain
        block.merkle_root = Blockchain.create_merkle_root(block_txs)

        # re-mine block
        block.mine_block(difficulty=4)

    db.session.commit()

    # Recalculate balances
    users = User.query.all()
    for user in users:
        user.block_balance = 0

    for bet in resolved_bets:
        total_participants = bet.user_bets.count()
        winners = [ub for ub in bet.user_bets if ub.chosen_outcome == bet.winning_outcome]
        num_winners = len(winners)
        blocks_per_winner = total_participants // num_winners if num_winners > 0 else 0

        for winner in winners:
            user = User.query.get(winner.user_id)
            if user:
                user.block_balance += blocks_per_winner

    # Handle service transactions
    sts = ServiceTransaction.query.all()
    for st in sts:
        if st.status == 'pending':
            buyer = User.query.get(st.buyer_id)
            if buyer:
                buyer.block_balance -= st.blocks_spent
        elif st.status == 'completed':
            buyer = User.query.get(st.buyer_id)
            if buyer:
                buyer.block_balance -= st.blocks_spent
            provider = User.query.get(st.service.provider_id)
            if provider:
                provider.block_balance += st.blocks_spent

    db.session.commit()

print("done")
