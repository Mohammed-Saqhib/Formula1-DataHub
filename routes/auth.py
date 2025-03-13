from flask import Blueprint, request, jsonify, session, redirect
import firebase_admin
from firebase_admin import auth

auth_bp = Blueprint('auth_bp', __name__)

# 🔹 User Login
@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        id_token = request.json.get("idToken")
        if not id_token:
            return jsonify({"error": "Missing token"}), 401
        decoded_token = auth.verify_id_token(id_token)
        session["user"] = {"uid": decoded_token["uid"], "email": decoded_token["email"]}
        return jsonify({"message": "Login successful"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 🔹 User Logout
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"message": "Logged out"}), 200
