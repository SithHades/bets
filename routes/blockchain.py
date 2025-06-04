import json
import datetime
from flask import Blueprint, render_template, redirect, url_for, session, jsonify
from flask_login import current_user
from models import Block, Transaction
from blockchain import Blockchain

blockchain_bp = Blueprint('blockchain', __name__)

@blockchain_bp.route('/blockchain')
def blockchain_explorer():
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return redirect(url_for('auth.access_page'))
    
    blocks = Block.query.order_by(Block.index.desc()).all()
    chain_valid = Blockchain.validate_chain()
    
    block_data = []
    for block in blocks:
        transactions = Transaction.query.filter_by(block_id=block.id).all()
        transaction_data = []
        
        for tx in transactions:
            tx_data = {
                'hash': tx.hash,
                'type': tx.transaction_type,
                'user_id': tx.user_id,
                'bet_id': tx.bet_id,
                'data': json.loads(tx.data),
                'timestamp': datetime.datetime.fromtimestamp(tx.timestamp)
            }
            transaction_data.append(tx_data)
        
        block_info = {
            'block': block,
            'transactions': transaction_data,
            'transaction_count': len(transaction_data),
            'timestamp': datetime.datetime.fromtimestamp(block.timestamp)
        }
        block_data.append(block_info)
    
    return render_template('blockchain.html', 
                         block_data=block_data, 
                         chain_valid=chain_valid,
                         total_blocks=len(blocks))

@blockchain_bp.route('/api/blockchain')
def api_blockchain():
    """API endpoint for blockchain data"""
    if not current_user.is_authenticated and not session.get('has_passed_gate'):
        return jsonify({'error': 'Access denied'}), 403
    
    blocks = Block.query.order_by(Block.index.asc()).all()
    chain_data = []
    
    for block in blocks:
        transactions = Transaction.query.filter_by(block_id=block.id).all()
        tx_data = []
        
        for tx in transactions:
            tx_info = {
                'hash': tx.hash,
                'type': tx.transaction_type,
                'user_id': tx.user_id,
                'bet_id': tx.bet_id,
                'data': json.loads(tx.data),
                'timestamp': tx.timestamp
            }
            tx_data.append(tx_info)
        
        block_info = {
            'index': block.index,
            'timestamp': block.timestamp,
            'previous_hash': block.previous_hash,
            'hash': block.hash,
            'nonce': block.nonce,
            'merkle_root': block.merkle_root,
            'transactions': tx_data
        }
        chain_data.append(block_info)
    
    return jsonify({
        'blockchain': chain_data,
        'valid': Blockchain.validate_chain(),
        'length': len(chain_data)
    })