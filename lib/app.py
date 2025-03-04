from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS  
from werkzeug.security import generate_password_hash, check_password_hash
from lib.models import User, Transaction, db
from datetime import datetime
from daraja import stk_push
import uuid  # Add this import
import random
import os

app = Flask(__name__)
CORS(app)  
api = Api(app)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)  

# User Registration
class Register(Resource):
    def post(self):
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        phone_number = data.get('phone_number')
        password = data.get('password')

        if not username or not email or not password:
            return {'message': 'Missing required fields'}, 400

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            return {'message': 'User already exists'}, 400

        hashed_password = generate_password_hash(password)
        account_number = str(random.randint(1000000000, 9999999999))  # Generate a random 10-digit account number
        new_user = User(username=username, email=email, phone_number=phone_number, password_hash=hashed_password, balance=0.0, account_number=account_number)

        db.session.add(new_user)
        db.session.commit()

        return new_user.to_dict(), 201

# User Login
class Login(Resource):
    def post(self):
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        user = User.query.filter_by(username=username).first()

        if not user:
            return {'message': 'User not found'}, 404

        if check_password_hash(user.password_hash, password):
            return user.to_dict(), 200

        return {'message': 'Invalid credentials'}, 401

# Transaction Handling
class TransactionAPI(Resource):
    def post(self):
        data = request.get_json()
        username = data.get('username')
        transaction_type = data.get('transaction_type')  
        amount = data.get('amount')
        identifier = data.get('identifier')  # Add identifier

        user = User.query.filter_by(username=username).first()
        if not user:
            return {'message': 'User not found'}, 404

        if transaction_type not in ['deposit', 'withdrawal', 'sent']:
            return {'message': 'Invalid transaction type'}, 400

        if transaction_type == 'sent':
            recipient = User.query.filter_by(account_number=identifier).first()
            if not recipient:
                return {'message': 'Recipient account not found'}, 404

        if transaction_type in ['withdrawal', 'sent'] and user.balance < amount:
            return {'message': 'Insufficient funds'}, 400

        if transaction_type == 'deposit':
            user.balance += amount
        elif transaction_type == 'withdrawal':
            user.balance -= amount
        elif transaction_type == 'sent':
            user.balance -= amount
            recipient.balance += amount  # Update recipient's balance
            amount = -amount  # Record the amount as a negative figure for the sender

        new_transaction = Transaction(
            user_id=user.id, 
            transaction_type=transaction_type, 
            amount=amount,
            timestamp=datetime.utcnow(),
            transaction_id=str(uuid.uuid4()),  # Generate a unique transaction ID
            recipient_id=recipient.id if transaction_type == 'sent' else None  # Set recipient_id if it's a sent transaction
        )
        db.session.add(new_transaction)

        if transaction_type == 'sent':
            recipient_transaction = Transaction(
                user_id=recipient.id,
                transaction_type='received',
                amount=-amount,  # Record the amount as a positive figure for the recipient
                timestamp=datetime.utcnow(),
                transaction_id=str(uuid.uuid4()),  # Generate a unique transaction ID
                sender_id=user.id  # Set sender_id
            )
            db.session.add(recipient_transaction)

        db.session.commit()

        return {'message': f'{transaction_type.capitalize()} successful', 'new_balance': user.balance}, 200

# User Details
class UserAPI(Resource):
    def get(self, identifier):
        user = User.query.filter((User.account_number == identifier) | (User.username == identifier)).first()
        if not user:
            return {'message': 'User not found'}, 404
        return user.to_dict(), 200

# Transaction Summary
class TransactionSummaryAPI(Resource):
    def get(self, username):
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'message': 'User not found'}, 404
            
        transactions = Transaction.query.filter_by(user_id=user.id).all()
        
        total_sent = sum(abs(t.amount) for t in transactions if t.transaction_type == 'withdrawal' or t.transaction_type == 'send')
        total_received = sum(abs(t.amount) for t in transactions if t.transaction_type == 'deposit' or t.transaction_type == 'receive')
        
        return {
            'success': True,
            'data': {
                'sent': total_sent,
                'received': total_received
            },
            'current_balance': user.balance
        }, 200

# Transaction History
class TransactionHistoryAPI(Resource):
    def get(self, username):
        user = User.query.filter_by(username=username).first()
        if not user:
            return {'message': 'User not found'}, 404
            
        transactions = Transaction.query.filter(
            (Transaction.user_id == user.id) |
            (Transaction.recipient_id == user.id) |
            (Transaction.sender_id == user.id)
        ).order_by(Transaction.timestamp.desc()).all()
        
        return {'transactions': [t.to_dict() for t in transactions]}, 200

# M-Pesa Callback
class MpesaCallback(Resource):
    def post(self):
        data = request.json  # Get the JSON response from Safaricom
        print("Received M-Pesa Callback:", data)  # Log it for debugging
        
        try:
            # Extract transaction result
            result_code = data["Body"]["stkCallback"]["ResultCode"]

            if result_code == 0:
                print("✅ Payment Successful")
                metadata = data["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
                
                amount = next(item["Value"] for item in metadata if item["Name"] == "Amount")
                phone = next(item["Value"] for item in metadata if item["Name"] == "PhoneNumber")
                transaction_id = next(item["Value"] for item in metadata if item["Name"] == "MpesaReceiptNumber")
                transaction_date = next(item["Value"] for item in metadata if item["Name"] == "TransactionDate")
                
                # Find the user by phone number
                user = User.query.filter_by(phone_number=phone).first()
                if not user:
                    return {"message": "User not found"}, 404

                # Update user balance
                user.balance += amount

                # Log the transaction into the database
                new_transaction = Transaction(
                    user_id=user.id,
                    transaction_type='deposit',
                    amount=amount,
                    timestamp=datetime.strptime(str(transaction_date), "%Y%m%d%H%M%S"),
                    transaction_id=transaction_id
                )
                db.session.add(new_transaction)
                db.session.commit()

                print(f"💰 Amount: {amount}, 📞 Phone: {phone}")

                return {
                    "message": "Payment Successful",
                    "amount": amount,
                    "phone": phone,
                    "transaction": new_transaction.to_dict()  # Include the new transaction in the response
                }, 200
            else:
                print("❌ Payment Failed")

                return {"message": "Payment Failed"}, 400

        except KeyError:
            print("⚠️ Error: Missing expected fields in callback data")
            return {"message": "Invalid callback data"}, 400

# M-Pesa STK Push
class MpesaStkPush(Resource):
    def post(self):
        data = request.get_json()
        phone_number = data.get('phone_number')
        amount = data.get('amount')

        if not phone_number or not amount:
            return {'message': 'Missing required fields'}, 400

        response = stk_push(phone_number, amount)
        if response.get("ResponseCode") == "0":
            return {'message': 'Payment Successful'}, 200
        else:
            return {'message': 'Payment Failed'}, 400

# Routes
api.add_resource(Register, '/register')
api.add_resource(Login, '/login')
api.add_resource(TransactionAPI, '/transaction')
api.add_resource(UserAPI, '/user/<string:identifier>')  # Update this line
api.add_resource(TransactionSummaryAPI, '/user/<string:username>/transaction-summary')
api.add_resource(TransactionHistoryAPI, '/user/<string:username>/transactions')
api.add_resource(MpesaCallback, '/mpesa/callback')
api.add_resource(MpesaStkPush, '/mpesa/stkpush')

if __name__ == '__main__':
    app.run(debug=True)
