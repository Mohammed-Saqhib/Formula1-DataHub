import time
import requests
import os
from flask import Blueprint, request, jsonify, session, redirect, current_app
from firebase_admin import auth as firebase_auth
from functools import wraps

auth_bp = Blueprint("auth_bp", __name__)

# Firebase API key - get this from your Firebase project settings
# For security, use environment variable
FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "your_firebase_api_key")

# Helper functions
def is_logged_in():
    return "user" in session

# Login required decorator 
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect("/auth")
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        email = request.json.get("email")
        password = request.json.get("password")

        firebase_api_key = os.getenv("FIREBASE_API_KEY")
        firebase_auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
        
        response = requests.post(firebase_auth_url, json={
            "email": email, 
            "password": password, 
            "returnSecureToken": True
        })
        
        data = response.json()
        if "idToken" not in data:
            return jsonify({"error": data.get("error", {}).get("message", "Invalid credentials")}), 400

        session["user"] = {"email": email, "uid": data["localId"]}
        return jsonify({"message": "Login successful", "user": session["user"]}), 200

    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({"error": str(e)}), 400

@auth_bp.route("/google-login", methods=["POST"])
def google_login():
    try:
        # Your current code uses 'idToken', which is correct if frontend sends that
        id_token = request.json.get("idToken")
        
        # For additional safety, also check 'id_token' if the first is not found
        if not id_token:
            id_token = request.json.get("id_token")
            
        if not id_token:
            current_app.logger.warning(f"No ID token provided in request: {request.json}")
            return jsonify({"error": "No ID token provided"}), 400
        
        # Rest of your code is correct
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        email = decoded_token.get("email", "")
        display_name = decoded_token.get("name", email.split('@')[0])

        # Set session data
        session["user"] = {
            "email": email,
            "uid": uid,
            "display_name": display_name,
            "token": id_token
        }
        
        # Add session security info
        session["created_at"] = time.time()
        session["user_agent"] = request.headers.get("User-Agent")

        return jsonify({
            "message": "Google login successful", 
            "user": {
                "email": email,
                "uid": uid,
                "display_name": display_name
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Google login error: {str(e)}")
        return jsonify({"error": str(e)}), 400

@auth_bp.route("/logout")
def logout():
    try:
        session.clear()
        return jsonify({"message": "Logout successful"}), 200
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({"error": str(e)}), 400

# Token refresh endpoint
@auth_bp.route("/refresh-token", methods=["POST"]) 
@login_required
def refresh_token():
    try:
        uid = session.get("user", {}).get("uid")
        if not uid:
            return jsonify({"error": "Not authenticated"}), 401
            
        # Create a custom token
        custom_token = firebase_auth.create_custom_token(uid)
        
        # Exchange custom token for ID token via Firebase REST API
        auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}"
        
        response = requests.post(auth_url, json={
            "token": custom_token.decode('utf-8'),
            "returnSecureToken": True
        })
        
        data = response.json()
        if "error" in data:
            return jsonify({"error": data["error"]["message"]}), 400
            
        # Update session with new token
        session["user"]["token"] = data["idToken"]
        session["created_at"] = time.time()
        
        return jsonify({"message": "Token refreshed successfully"}), 200
        
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({"error": str(e)}), 400
