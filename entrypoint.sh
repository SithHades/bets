#!/bin/sh

# Define the path to the database file
DB_FILE="/app/instance/bets.db"

# Check if the database directory and file exist
if [ ! -f "$DB_FILE" ]; then
    echo "Database not found. Initializing database..."
    flask init-db
else
    echo "Database found."
fi

# Execute the main command (run the Flask app)
echo "Starting Flask application..."
exec flask run 