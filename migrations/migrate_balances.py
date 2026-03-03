from app import create_app
from models import db, User, Transaction, Block, ServiceTransaction

def reset_blockchain_balance():
    app = create_app()
    with app.app_context():
        # First zero out all user balances
        for user in User.query.all():
            user.block_balance = 0

        # Add balances back exclusively from the blockchain ledger (block_reward transactions)
        import json
        reward_txs = Transaction.query.filter_by(transaction_type='block_reward').all()
        for tx in reward_txs:
            data = json.loads(tx.data)
            user = User.query.get(tx.user_id)
            if user:
                user.block_balance += data.get('blocks_awarded', 0)

        # Handle regular transfers if they exist in the codebase
        # E.g., service transactions
        for tx in Transaction.query.filter_by(transaction_type='service_purchase').all():
            data = json.loads(tx.data)
            buyer = User.query.get(tx.user_id)
            if buyer:
                buyer.block_balance -= data.get('blocks_spent', 0)

        for tx in Transaction.query.filter_by(transaction_type='service_completion').all():
            data = json.loads(tx.data)
            provider = User.query.get(data.get('provider_id'))
            if provider:
                provider.block_balance += data.get('blocks_transferred', 0)

        db.session.commit()
        print("Blockchain balance recalculated based on ledger.")

if __name__ == '__main__':
    reset_blockchain_balance()
