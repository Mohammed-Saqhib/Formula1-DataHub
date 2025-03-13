from flask import Blueprint, request, jsonify
from firebase_init import db

drivers_bp = Blueprint('drivers_bp', __name__)

# 🔹 Get Drivers
@drivers_bp.route("/", methods=["GET"])
def get_drivers():
    try:
        drivers = db.collection('drivers').stream()
        driver_list = [{"id": doc.id, **doc.to_dict()} for doc in drivers]
        return jsonify(driver_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 🔹 Add Driver
@drivers_bp.route("/add", methods=["POST"])
def add_driver():
    try:
        driver_data = request.json
        db.collection('drivers').add(driver_data)
        return jsonify({"message": "Driver added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
