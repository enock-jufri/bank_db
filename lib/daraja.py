import base64
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
from flask import Flask, request, jsonify



BUSINESS_SHORTCODE = "174379"  # Use your PayBill/Till number
PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919" 
CALLBACK_URL = "https://4a1d-41-90-68-99.ngrok-free.app/mpesa/callback"  # Use your server URL
CONSUMER_KEY = "9pq9aT7AkzSSUEkXT0A5TU1p6xaqkJzjcUm4pSVUmzGsImlo"
CONSUMER_SECRET = "DVb8u8KoAGTwW88EVcSAw8HAJnGGBAx1OHkWdJh4bjk7qo4Ub2bPjQY9c9LekCSi"
SECURITY_CREDENTIAL="b5SrQ2MCWXsi1/Ek6A7qKm1mfhFCHEQkScTgYMGrVZbrIvfHLijDzcCFVy7sgDorIbScXYZy/y7OrK/sIzwkZ3RIJ9KPamj1g+DhHY1NGlnDCWLtpXP68eeXjIAJazwmoqHBiGjV4mkCNiW5Qo8a4jwPLQe3256lSVoeYNcStsGJ956ZRFA2UUk6VccpExdkJUmMenHIRcEk7zAHc1qS19Lyu7vHRwVs9G/6UwT56S1BKf/xmHHCWhrwNIOtE+Adie7l9f9bNJzl3vsvTdsGbaCCwojePbRgzBHUA2eW0rbQV5OJvdeDdbfCE5BDzt5L2opJ3JqYqyA3Jcf4oMsbJw=="

def get_access_token():
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url, auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET))
    access_token = response.json().get("access_token")
    return access_token

def generate_password():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{BUSINESS_SHORTCODE}{PASSKEY}{timestamp}".encode()).decode()
    return password, timestamp

def stk_push(phone_number, amount):
    access_token = get_access_token()
    
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    password, timestamp = generate_password()

    payload = {
        "BusinessShortCode": BUSINESS_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": BUSINESS_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "Modern Bank",
        "TransactionDesc": "Deposit money"
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()

