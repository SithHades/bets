import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Service, ServiceTransaction
from blockchain import Blockchain

services = Blueprint('services', __name__)

@services.route('/services')
def marketplace():
    """Display all available services"""
    available_services = Service.query.filter_by(status='available').order_by(Service.created_at.desc()).all()
    return render_template('services.html', services=available_services)

@services.route('/create_service', methods=['GET', 'POST'])
@login_required
def create_service():
    """Create a new service offering"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        block_cost = request.form.get('block_cost', type=int)

        if not all([title, block_cost]):
            flash('Title and block cost are required.', 'danger')
            return redirect(url_for('services.create_service'))

        if block_cost < 1:
            flash('Block cost must be at least 1.', 'danger')
            return redirect(url_for('services.create_service'))

        new_service = Service(
            title=title,
            description=description,
            block_cost=block_cost,
            provider_id=current_user.id
        )
        db.session.add(new_service)
        db.session.commit()
        
        # Add blockchain transaction for service creation
        service_data = {
            'title': title,
            'description': description,
            'block_cost': block_cost,
            'provider_id': current_user.id,
            'creation_time': datetime.datetime.now().isoformat()
        }
        Blockchain.add_transaction('service_creation', user_id=current_user.id, data=service_data)
        
        flash('Service created successfully!', 'success')
        return redirect(url_for('services.marketplace'))
    
    return render_template('create_service.html')

@services.route('/purchase_service/<int:service_id>', methods=['POST'])
@login_required
def purchase_service(service_id):
    """Purchase a service with blocks"""
    service = Service.query.get_or_404(service_id)
    
    if service.status != 'available':
        flash('This service is no longer available.', 'warning')
        return redirect(url_for('services.marketplace'))
    
    if service.provider_id == current_user.id:
        flash('You cannot purchase your own service.', 'warning')
        return redirect(url_for('services.marketplace'))
    
    if current_user.block_balance < service.block_cost:
        flash(f'Insufficient blocks. You need {service.block_cost} blocks but only have {current_user.block_balance}.', 'danger')
        return redirect(url_for('services.marketplace'))
    
    # Check if user already has a pending transaction for this service
    existing_transaction = ServiceTransaction.query.filter_by(
        service_id=service_id, 
        buyer_id=current_user.id, 
        status='pending'
    ).first()
    
    if existing_transaction:
        flash('You already have a pending transaction for this service.', 'warning')
        return redirect(url_for('services.marketplace'))
    
    # Deduct blocks from buyer
    current_user.block_balance -= service.block_cost
    
    # Create transaction
    transaction = ServiceTransaction(
        service_id=service_id,
        buyer_id=current_user.id,
        blocks_spent=service.block_cost
    )
    db.session.add(transaction)
    
    # Update service status
    service.status = 'pending'
    
    db.session.commit()
    
    # Add blockchain transaction
    purchase_data = {
        'service_id': service_id,
        'service_title': service.title,
        'buyer_id': current_user.id,
        'provider_id': service.provider_id,
        'blocks_spent': service.block_cost,
        'purchase_time': datetime.datetime.now().isoformat()
    }
    Blockchain.add_transaction('service_purchase', user_id=current_user.id, data=purchase_data)
    
    flash(f'Successfully purchased "{service.title}" for {service.block_cost} blocks!', 'success')
    return redirect(url_for('services.my_transactions'))

@services.route('/complete_service/<int:transaction_id>', methods=['POST'])
@login_required
def complete_service(transaction_id):
    """Mark a service as completed"""
    transaction = ServiceTransaction.query.get_or_404(transaction_id)
    
    if transaction.status != 'pending':
        flash('This transaction is not in pending status.', 'warning')
        return redirect(url_for('services.my_transactions'))
    
    # Only buyer or provider can mark as complete
    if current_user.id not in [transaction.buyer_id, transaction.service.provider_id]:
        flash('You are not authorized to complete this transaction.', 'danger')
        return redirect(url_for('services.my_transactions'))
    
    # Transfer blocks to provider
    provider = User.query.get(transaction.service.provider_id)
    provider.block_balance += transaction.blocks_spent
    
    # Update transaction and service status
    transaction.status = 'completed'
    transaction.completed_at = datetime.datetime.now()
    transaction.service.status = 'completed'
    
    db.session.commit()
    
    # Add blockchain transaction for completion
    completion_data = {
        'transaction_id': transaction_id,
        'service_title': transaction.service.title,
        'buyer_id': transaction.buyer_id,
        'provider_id': transaction.service.provider_id,
        'blocks_transferred': transaction.blocks_spent,
        'completed_by': current_user.id,
        'completion_time': datetime.datetime.now().isoformat()
    }
    Blockchain.add_transaction('service_completion', user_id=current_user.id, data=completion_data)
    
    flash('Service marked as completed!', 'success')
    return redirect(url_for('services.my_transactions'))

@services.route('/cancel_service/<int:transaction_id>', methods=['POST'])
@login_required
def cancel_service(transaction_id):
    """Cancel a service transaction"""
    transaction = ServiceTransaction.query.get_or_404(transaction_id)
    
    if transaction.status != 'pending':
        flash('This transaction is not in pending status.', 'warning')
        return redirect(url_for('services.my_transactions'))
    
    # Only buyer or provider can cancel
    if current_user.id not in [transaction.buyer_id, transaction.service.provider_id]:
        flash('You are not authorized to cancel this transaction.', 'danger')
        return redirect(url_for('services.my_transactions'))
    
    # Refund blocks to buyer
    buyer = User.query.get(transaction.buyer_id)
    buyer.block_balance += transaction.blocks_spent
    
    # Update transaction and service status
    transaction.status = 'cancelled'
    transaction.service.status = 'available'
    
    db.session.commit()
    
    # Add blockchain transaction for cancellation
    cancellation_data = {
        'transaction_id': transaction_id,
        'service_title': transaction.service.title,
        'buyer_id': transaction.buyer_id,
        'provider_id': transaction.service.provider_id,
        'blocks_refunded': transaction.blocks_spent,
        'cancelled_by': current_user.id,
        'cancellation_time': datetime.datetime.now().isoformat()
    }
    Blockchain.add_transaction('service_cancellation', user_id=current_user.id, data=cancellation_data)
    
    flash('Service transaction cancelled and blocks refunded.', 'info')
    return redirect(url_for('services.my_transactions'))

@services.route('/my_services')
@login_required
def my_services():
    """Display user's offered services"""
    user_services = Service.query.filter_by(provider_id=current_user.id).order_by(Service.created_at.desc()).all()
    return render_template('my_services.html', services=user_services)

@services.route('/my_transactions')
@login_required
def my_transactions():
    """Display user's service transactions"""
    purchases = ServiceTransaction.query.filter_by(buyer_id=current_user.id).order_by(ServiceTransaction.created_at.desc()).all()
    sales = ServiceTransaction.query.join(Service).filter(Service.provider_id == current_user.id).order_by(ServiceTransaction.created_at.desc()).all()
    
    return render_template('my_transactions.html', purchases=purchases, sales=sales)