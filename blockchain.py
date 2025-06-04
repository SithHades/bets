import time
import hashlib
import json
from models import db, Block, Transaction

class Blockchain:
    @staticmethod
    def create_genesis_block():
        """Create the first block in the blockchain"""
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            previous_hash="0",
            merkle_root="0",
            nonce=0
        )
        genesis_block.hash = genesis_block.calculate_hash()
        return genesis_block

    @staticmethod
    def get_latest_block():
        """Get the most recent block in the chain"""
        return Block.query.order_by(Block.index.desc()).first()

    @staticmethod
    def create_merkle_root(transactions):
        """Create a merkle root from a list of transactions"""
        if not transactions:
            return "0"
        
        transaction_hashes = [tx.hash for tx in transactions]
        
        while len(transaction_hashes) > 1:
            next_level = []
            for i in range(0, len(transaction_hashes), 2):
                if i + 1 < len(transaction_hashes):
                    combined = transaction_hashes[i] + transaction_hashes[i + 1]
                else:
                    combined = transaction_hashes[i] + transaction_hashes[i]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            transaction_hashes = next_level
        
        return transaction_hashes[0]

    @staticmethod
    def add_block(transactions):
        """Add a new block to the blockchain with the given transactions"""
        latest_block = Blockchain.get_latest_block()
        if not latest_block:
            # Create genesis block if none exists
            genesis = Blockchain.create_genesis_block()
            db.session.add(genesis)
            db.session.commit()
            latest_block = genesis

        merkle_root = Blockchain.create_merkle_root(transactions)
        
        new_block = Block(
            index=latest_block.index + 1,
            timestamp=time.time(),
            previous_hash=latest_block.hash,
            merkle_root=merkle_root,
            nonce=0
        )
        
        new_block.mine_block(difficulty=4)
        db.session.add(new_block)
        db.session.flush()  # Get the block ID
        
        # Assign transactions to this block
        for tx in transactions:
            tx.block_id = new_block.id
            db.session.add(tx)
        
        db.session.commit()
        return new_block

    @staticmethod
    def validate_chain():
        """Validate the entire blockchain"""
        blocks = Block.query.order_by(Block.index.asc()).all()
        
        for i in range(1, len(blocks)):
            current_block = blocks[i]
            previous_block = blocks[i - 1]
            
            # Check if current block's hash is valid
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check if current block points to previous block
            if current_block.previous_hash != previous_block.hash:
                return False
            
            # Validate merkle root
            block_transactions = Transaction.query.filter_by(block_id=current_block.id).all()
            if current_block.merkle_root != Blockchain.create_merkle_root(block_transactions):
                return False
        
        return True

    @staticmethod
    def add_transaction(transaction_type, user_id=None, bet_id=None, data=None):
        """Create and add a transaction to pending transactions"""
        transaction = Transaction(
            transaction_type=transaction_type,
            user_id=user_id,
            bet_id=bet_id,
            data=json.dumps(data) if data else "{}"
        )
        
        # For simplicity, we'll immediately create a block for each transaction
        # In a real blockchain, transactions would be batched
        Blockchain.add_block([transaction])
        return transaction