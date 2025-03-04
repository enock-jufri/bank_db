from app import app, db
from models import User, Transaction
from werkzeug.security import generate_password_hash
from faker import Faker
import random
from datetime import datetime, timedelta

def generate_phone_number():
    # Generate valid US phone number format
    area_code = random.randint(200, 999)
    prefix = random.randint(200, 999)
    line = random.randint(1000, 9999)
    return f"+1{area_code}{prefix}{line}"

def generate_transaction_id():
    # Generate a unique transaction ID
    return f"TX-{random.randint(100000, 999999)}"

def seed_data():
    fake = Faker()
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        # Create users
        users = []
        for _ in range(20):  # Generate 20 users for more interaction
            account_number = str(random.randint(1000000000, 9999999999))
            while User.query.filter_by(account_number=account_number).first():
                account_number = str(random.randint(1000000000, 9999999999))
            
            user = User(
                username=fake.user_name(),
                email=fake.email(),
                account_number=account_number,
                password_hash=generate_password_hash('password123'),
                phone_number=generate_phone_number(),
                balance=random.randint(5000, 50000)  # More realistic initial balance
            )
            users.append(user)
            db.session.add(user)
        db.session.commit()

        # Create transactions
        transactions = []
        start_date = datetime.now() - timedelta(days=90)  # Last 90 days

        for user in users:
            # Regular deposits and withdrawals
            for _ in range(8):
                transaction_type = random.choice(['deposit', 'withdrawal'])
                amount = random.randint(50, 2000)
                if transaction_type == 'withdrawal':
                    amount = -amount
                
                transaction = Transaction(
                    user_id=user.id,
                    transaction_type=transaction_type,
                    amount=amount,
                    timestamp=fake.date_time_between(start_date=start_date),
                    transaction_id=generate_transaction_id()  # Add transaction ID
                )
                transactions.append(transaction)

            # Transfers between users
            for _ in range(5):
                recipient = random.choice([u for u in users if u != user])
                amount = random.randint(100, 1000)
                
                # Debit transaction for sender
                transactions.append(Transaction(
                    user_id=user.id,
                    transaction_type='sent',
                    amount=-amount,
                    recipient_id=recipient.id,
                    timestamp=fake.date_time_between(start_date=start_date),
                    transaction_id=generate_transaction_id()  # Add transaction ID
                ))
                
                # Credit transaction for recipient
                transactions.append(Transaction(
                    user_id=recipient.id,
                    transaction_type='received',
                    amount=amount,
                    sender_id=user.id,
                    timestamp=fake.date_time_between(start_date=start_date),
                    transaction_id=generate_transaction_id()  # Add transaction ID
                ))

        db.session.bulk_save_objects(transactions)
        db.session.commit()

        print("Database seeded successfully!")

if __name__ == '__main__':
    seed_data()
