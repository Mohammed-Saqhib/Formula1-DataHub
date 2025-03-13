import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

SECRET_KEY = os.getenv("SECRET_KEY")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
