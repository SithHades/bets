#!/bin/sh

# Define the path to the database file
DB_FILE="/app/instance/bets.db"

# Check if the database directory and file exist
if [ ! -f "$DB_FILE" ]; then
    echo "Database not found. Initializing database..."
    flask init-db
    echo "Running initial blockchain migration..."
    flask migrate-to-blockchain
else
    echo "Database found. Ensuring database schema is up to date..."
    flask init-db
    
    # Check if blockchain migration is needed
    echo "Checking blockchain migration status..."
    python -c "
from app import app, Block, Transaction
import sqlalchemy
with app.app_context():
    try:
        block_count = Block.query.count()
        tx_count = Transaction.query.count()
        print(f'Current blockchain has {block_count} blocks and {tx_count} transactions')
        if block_count <= 1 and tx_count == 0:
            print('No blockchain data found - migration needed')
            exit(1)
        else:
            print('Blockchain already has data - skipping migration')
            exit(0)
    except sqlalchemy.exc.OperationalError as e:
        print('Blockchain tables do not exist - migration needed')
        exit(1)
" && echo "Blockchain migration not needed." || {
    echo "Running blockchain migration..."
    flask migrate-to-blockchain
}
fi

# Execute the main command (run the Flask app)
echo "Starting Flask application..."
exec flask run 