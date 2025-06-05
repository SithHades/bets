#!/usr/bin/env python3
"""
Migration script to add block_balance column to existing users table
"""
import sqlite3
from pathlib import Path

def migrate_add_block_balance():
    """Add block_balance column to users table if it doesn't exist"""
    
    # Path to the database file
    db_path = Path(__file__).parent / "instance" / "bets.db"
    
    if not db_path.exists():
        print("Database file not found. No migration needed.")
        return
    
    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if block_balance column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'block_balance' not in columns:
            print("Adding block_balance column to user table...")
            cursor.execute("ALTER TABLE user ADD COLUMN block_balance INTEGER DEFAULT 0 NOT NULL")
            conn.commit()
            print("✓ Successfully added block_balance column")
        else:
            print("✓ block_balance column already exists")
        
        # Check if Service table exists, if not create it
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service'")
        if not cursor.fetchone():
            print("Creating Service table...")
            cursor.execute("""
                CREATE TABLE service (
                    id INTEGER NOT NULL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    block_cost INTEGER NOT NULL,
                    provider_id INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'available',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(provider_id) REFERENCES user (id)
                )
            """)
            print("✓ Successfully created Service table")
        else:
            print("✓ Service table already exists")
        
        # Check if ServiceTransaction table exists, if not create it
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_transaction'")
        if not cursor.fetchone():
            print("Creating ServiceTransaction table...")
            cursor.execute("""
                CREATE TABLE service_transaction (
                    id INTEGER NOT NULL PRIMARY KEY,
                    service_id INTEGER NOT NULL,
                    buyer_id INTEGER NOT NULL,
                    blocks_spent INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    FOREIGN KEY(service_id) REFERENCES service (id),
                    FOREIGN KEY(buyer_id) REFERENCES user (id)
                )
            """)
            print("✓ Successfully created ServiceTransaction table")
        else:
            print("✓ ServiceTransaction table already exists")
        
        conn.commit()
        print("\n🎉 Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_add_block_balance()