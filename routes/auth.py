import os
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user
from models import db, User
from blockchain import Blockchain

auth = Blueprint('auth', __name__)

DEFAULT_SIGNUP_PASSWORD = os.environ.get('DEFAULT_SIGNUP_PASSWORD')

@auth.route('/access', methods=['GET', 'POST'])
def access_page():
    if session.get('has_passed_gate') or current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        access_password = request.form.get('access_password')
        if not DEFAULT_SIGNUP_PASSWORD:
            flash('Site access password is not configured on the server.', 'danger')
            return render_template('access_page.html')

        if access_password == DEFAULT_SIGNUP_PASSWORD:
            session['has_passed_gate'] = True
            flash('Access granted.', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Incorrect access password.', 'danger')
    return render_template('access_page.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        signup_password = request.form.get('signup_password')

        if not DEFAULT_SIGNUP_PASSWORD:
            flash('Sign-up password is not configured on the server.', 'danger')
            return redirect(url_for('auth.register'))

        if signup_password != DEFAULT_SIGNUP_PASSWORD:
            flash('Invalid sign-up password.', 'danger')
            return redirect(url_for('auth.register'))

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email address already registered.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(name=name, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        # Add blockchain transaction for user registration
        user_data = {
            'name': name,
            'email': email,
            'registration_time': datetime.datetime.now().isoformat()
        }
        Blockchain.add_transaction('user_registration', user_id=new_user.id, data=user_data)
        
        session.pop('has_passed_gate', None) # Clear gate pass after registration
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            session.pop('has_passed_gate', None) # Clear gate pass after successful login
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html')

@auth.route('/logout')
def logout():
    logout_user()
    session.pop('has_passed_gate', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login')) # Redirect to login, which will then check gate or auth