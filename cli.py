import datetime
import click
from flask import current_app
from models import db, User, Bet, UserBet, Block, Transaction
from blockchain import Blockchain

def register_cli_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Clear existing data and create new tables."""
        with app.app_context():
            db.create_all()
        click.echo("Initialized the database.")

    @app.cli.command("migrate-to-blockchain")
    def migrate_to_blockchain_command():
        """Migrate existing betting data to blockchain transactions."""
        with app.app_context():
            # Create genesis block if it doesn't exist
            if not Block.query.first():
                genesis = Blockchain.create_genesis_block()
                db.session.add(genesis)
                db.session.commit()
                click.echo("Created genesis block.")
            
            # Check if we already have transactions
            existing_transactions = Transaction.query.count()
            if existing_transactions > 0:
                click.echo(f"Found {existing_transactions} existing blockchain transactions.")
                click.echo("Blockchain already migrated - skipping migration to avoid duplicates.")
                return
            
            transactions_created = 0
            
            # Migrate user registrations
            users = User.query.order_by(User.id.asc()).all()
            click.echo(f"Migrating {len(users)} users...")
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
            click.echo(f"Migrating {len(bets)} bet creations...")
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
            click.echo(f"Migrating {len(user_bets)} bet placements...")
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
            click.echo(f"Migrating {len(resolved_bets)} bet resolutions...")
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
            
            click.echo("\nMigration completed!")
            click.echo(f"Created {transactions_created} blockchain transactions.")
            click.echo(f"Total blocks in chain: {Block.query.count()}")
            click.echo(f"Chain is valid: {Blockchain.validate_chain()}")