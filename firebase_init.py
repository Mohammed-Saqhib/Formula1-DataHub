import firebase_admin
from firebase_admin import credentials, firestore

# Check if Firebase is already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-admin-sdk.json")  # Path to your Firebase Admin SDK JSON file
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()
