from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class SerializeMixin:
    """Mixin to serialize model data into dictionaries"""
    def to_dict(self):
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            # Convert datetime objects to ISO format string
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

# User Model
class User(db.Model, SerializeMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    account_number = db.Column(db.String(10), unique=True, nullable=False)

    # Transactions where user is the sender
    sent_transactions = db.relationship(
        'Transaction',
        foreign_keys='Transaction.user_id',
        backref='sender',
        lazy=True
    )

    # Transactions where user is the recipient
    received_transactions = db.relationship(
        'Transaction',
        foreign_keys='Transaction.recipient_id',
        backref='recipient',
        lazy=True
    )

    def set_password(self, password):
        """Hash and set the password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the hashed password"""
        return check_password_hash(self.password_hash, password)

    def update_balance(self, amount):
        """Update user balance"""
        self.balance += amount
        db.session.commit()

    def can_withdraw(self, amount):
        """Check if user can withdraw the specified amount"""
        return self.balance >= amount

    def __repr__(self):
        return f"<User {self.username}>"

# Transaction Model
class Transaction(db.Model, SerializeMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    transaction_id = db.Column(db.String(50), nullable=False)  # Add this line

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'recipient_id': self.recipient_id,
            'sender_id': self.sender_id,
            'transaction_id': self.transaction_id  # Add this line
        }

    def process_transaction(self):
        """Process the transaction and update balances"""
        try:
            if self.transaction_type == 'deposit':
                self.user.update_balance(self.amount)
            elif self.transaction_type == 'withdrawal':
                if self.user.can_withdraw(self.amount):
                    self.user.update_balance(-self.amount)
                else:
                    raise ValueError("Insufficient funds")
            elif self.transaction_type == 'transfer':
                if self.user.can_withdraw(self.amount) and self.recipient_id:
                    recipient = User.query.get(self.recipient_id)
                    if recipient:
                        self.user.update_balance(-self.amount)
                        recipient.update_balance(self.amount)
                    else:
                        raise ValueError("Recipient not found")
                else:
                    raise ValueError("Invalid transfer")
                
            self.status = 'completed'
            db.session.commit()
            return True
        except Exception as e:
            self.status = 'failed'
            db.session.commit()
            raise e

    def __repr__(self):
        return f"<Transaction {self.transaction_type} - {self.amount}>"
