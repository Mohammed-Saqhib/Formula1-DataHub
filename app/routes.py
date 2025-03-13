from flask import Blueprint, request, jsonify, session, current_app
from app.database import get_drivers, add_driver, get_driver, update_driver, delete_driver
from app.auth import login_required

routes_bp = Blueprint("routes_bp", __name__)

@routes_bp.route("/drivers", methods=["GET"])
@login_required
def list_drivers():
    try:
        limit = min(int(request.args.get("limit", 10)), 50)
        start_after = request.args.get("start_after")
        
        filters = {}
        if request.args.get("team_id"):
            filters["team_id"] = request.args.get("team_id")
        if request.args.get("min_wins"):
            try:
                filters["min_wins"] = int(request.args.get("min_wins"))
            except ValueError:
                return jsonify({"error": "min_wins must be an integer"}), 400
        if request.args.get("nationality"):
            filters["nationality"] = request.args.get("nationality")
        if "active" in request.args:
            filters["active"] = request.args.get("active").lower() == "true"
        
        drivers, last_doc = get_drivers(limit, start_after, filters)
        
        return jsonify({
            "drivers": drivers,
            "pagination": {
                "count": len(drivers),
                "limit": limit,
                "has_more": len(drivers) == limit,
                "next_cursor": last_doc if len(drivers) == limit else None
            },
            "filters": filters
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error in list_drivers: {str(e)}")
        return jsonify({"error": f"Failed to retrieve drivers: {str(e)}"}), 500

@routes_bp.route("/drivers/<driver_id>", methods=["GET"])
@login_required
def get_single_driver(driver_id):
    try:
        driver = get_driver(driver_id)
        if not driver:
            return jsonify({"error": "Driver not found"}), 404
        return jsonify(driver), 200
    except Exception as e:
        current_app.logger.error(f"Error retrieving driver {driver_id}: {str(e)}")
        return jsonify({"error": f"Failed to retrieve driver: {str(e)}"}), 500

@routes_bp.route("/drivers", methods=["POST"])
@login_required
def create_driver():
    try:
        data = request.json
        user_id = session.get("user", {}).get("uid", "unknown")
        
        required_fields = ["name", "team_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        if len(data.get("name", "")) < 2:
            return jsonify({"error": "Name must be at least 2 characters"}), 400
            
        driver_id = add_driver(data, user_id)
        current_app.logger.info(f"Driver '{data.get('name')}' created by {user_id}")
        
        return jsonify({"message": "Driver added successfully", "id": driver_id}), 201
    except Exception as e:
        current_app.logger.error(f"Error creating driver: {str(e)}")
        return jsonify({"error": f"Failed to create driver: {str(e)}"}), 500

@routes_bp.route("/drivers/<driver_id>", methods=["PUT", "PATCH"])
@login_required
def update_single_driver(driver_id):
    try:
        data = request.json
        user_id = session.get("user", {}).get("uid", "unknown")
        
        existing_driver = get_driver(driver_id)
        if not existing_driver:
            return jsonify({"error": "Driver not found"}), 404
        
        update_driver(driver_id, data, user_id)
        current_app.logger.info(f"Driver {driver_id} updated by {user_id}")
        
        return jsonify({"message": "Driver updated successfully", "id": driver_id}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating driver {driver_id}: {str(e)}")
        return jsonify({"error": f"Failed to update driver: {str(e)}"}), 500

@routes_bp.route("/drivers/<driver_id>", methods=["DELETE"])
@login_required
def delete_single_driver(driver_id):
    try:
        user_id = session.get("user", {}).get("uid", "unknown")
        existing_driver = get_driver(driver_id)
        if not existing_driver:
            return jsonify({"error": "Driver not found"}), 404
            
        if existing_driver.get("created_by") and existing_driver["created_by"] != user_id:
            is_admin = session.get("user", {}).get("is_admin", False)
            if not is_admin:
                current_app.logger.warning(f"User {user_id} attempted to delete driver {driver_id} created by {existing_driver['created_by']}")
                return jsonify({"error": "You don't have permission to delete this driver"}), 403
        
        delete_driver(driver_id)
        current_app.logger.info(f"Driver {driver_id} deleted by {user_id}")
        
        return jsonify({"message": "Driver deleted successfully", "id": driver_id}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting driver {driver_id}: {str(e)}")
        return jsonify({"error": f"Failed to delete driver: {str(e)}"}), 500

@routes_bp.route("/drivers/search", methods=["GET"])
@login_required
def search_drivers():
    try:
        query = request.args.get("q", "").strip().lower()
        limit = min(int(request.args.get("limit", 10)), 50)
        
        if not query or len(query) < 2:
            return jsonify({"error": "Search query must be at least 2 characters"}), 400
            
        drivers, _ = get_drivers(limit=100)
        filtered_drivers = [
            driver for driver in drivers 
            if query in driver.get("name", "").lower() or 
               query in driver.get("team_name", "").lower() or
               query in driver.get("nationality", "").lower()
        ]
        
        filtered_drivers = filtered_drivers[:limit]
        
        return jsonify({"drivers": filtered_drivers, "count": len(filtered_drivers), "query": query}), 200
    except Exception as e:
        current_app.logger.error(f"Error searching drivers: {str(e)}")
        return jsonify({"error": f"Failed to search drivers: {str(e)}"}), 500
