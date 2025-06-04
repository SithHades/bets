#!/bin/bash

# Simulate deployment process
echo "=== Testing Deployment Process ==="

# Set Flask app
export FLASK_APP=app.py

# Clean start
rm -f instance/bets.db

echo ""
echo "=== First Deployment (Fresh Database) ==="
echo "Database not found. Initializing database..."
.venv/bin/python -m flask init-db

echo "Running initial blockchain migration..."
.venv/bin/python -m flask migrate-to-blockchain

echo ""
echo "=== Second Deployment (Existing Database) ==="
echo "Database found. Ensuring database schema is up to date..."
.venv/bin/python -m flask init-db

echo "Checking blockchain migration status..."
.venv/bin/python -c "
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
    .venv/bin/python -m flask migrate-to-blockchain
}

echo ""
echo "=== Third Deployment (Should Skip Migration) ==="
echo "Checking blockchain migration status..."
.venv/bin/python -c "
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
    .venv/bin/python -m flask migrate-to-blockchain
}

echo ""
echo "=== Deployment Test Complete ==="
