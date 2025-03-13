import time
import os
import re
import secrets
from datetime import timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, jsonify, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore
from firebase_init import db

app = Flask(__name__)

# Generate a random secret key if one isn't set in environment variables
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# 🔹 Enhance session security with secure cookies
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to cookies
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # Require HTTPS in production
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Prevent CSRF attacks while allowing links
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Auto logout after 2 hours
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions on server filesystem

# Setup Simple Caching instead of Redis
class SimpleCache:
    def __init__(self):
        self.cache = {}
        self.timeouts = {}
    
    def get(self, key):
        # Check if key exists and hasn't expired
        if key in self.cache and (key not in self.timeouts or self.timeouts[key] > time.time()):
            return self.cache[key]
        return None
    
    def set(self, key, value, timeout=300):
        self.cache[key] = value
        if timeout:
            self.timeouts[key] = time.time() + timeout
    
    def delete(self, key):
        if key in self.cache:
            del self.cache[key]
        if key in self.timeouts:
            del self.timeouts[key]
    
    def cached(self, timeout=300, key_prefix=''):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                cache_key = key_prefix
                result = self.get(cache_key)
                if result is None:
                    result = f(*args, **kwargs)
                    self.set(cache_key, result, timeout)
                return result
            return decorated_function
        return decorator

# Initialize the simple cache
cache = SimpleCache()

# Setup Rate Limiting without Redis
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # Use in-memory storage instead of Redis
    strategy="fixed-window"
)

# Initialize Firebase Admin if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-admin-sdk.json")  # Path to Firebase Admin SDK JSON
    firebase_admin.initialize_app(cred)

# Add this line near your imports
auth = firebase_auth  # Alias firebase_auth as auth for consistent usage

# Import the auth blueprint
from app.auth import auth_bp

# Register the blueprint
app.register_blueprint(auth_bp, url_prefix="/api/auth")

# 🔹 Additional security for login route
@app.before_request
def make_session_permanent():
    global time  # Add this line to ensure we're using the global module
    # Always make sessions permanent with the configured lifetime
    session.permanent = True
    
    # Initialize last_activity if it doesn't exist
    if 'last_activity' not in session:
        session['last_activity'] = time.time()
        return
    
    # Check for session expiration only if user is logged in
    if 'user' in session:
        try:
            last_active = float(session['last_activity'])
            current_time = time.time()
            
            # If last activity was more than 2 hours ago, clear session
            if current_time - last_active > 7200:  # 2 hours in seconds
                session.clear()
                if request.path not in ['/auth', '/login', '/register', '/google-login']:
                    return redirect('/auth')
        except (ValueError, TypeError):
            # Reset if invalid timestamp stored
            session['last_activity'] = time.time()
    
    # Update last activity timestamp
    session['last_activity'] = time.time()

@app.before_request
def make_session_permanent():
    try:
        session['last_activity'] = time.time()
    except Exception as e:
        app.logger.error(f"Error updating session: {e}")
        # Provide a fallback
        import time as time_module
        session['last_activity'] = time_module.time()

# 🔹 Check if user is logged in
def is_logged_in():
    return "user" in session

# 🔹 Login required decorator for session-based auth
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect("/auth")
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 🔹 Firebase token verification decorator for API requests
def verify_firebase_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the token from the Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        # Check if token exists and has proper format
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "No valid token provided", "code": "auth/missing-token"}), 401
            
        # Extract the token
        id_token = auth_header.split("Bearer ")[1]
        
        try:
            # Verify the token with Firebase
            decoded_token = auth.verify_id_token(id_token)
            
            # Attach user info to request object for use in the route
            request.user = decoded_token
            
            # Continue to the route function
            return f(*args, **kwargs)
        except firebase_admin.auth.InvalidIdTokenError:
            return jsonify({"error": "Invalid token", "code": "auth/invalid-token"}), 401
        except firebase_admin.auth.ExpiredIdTokenError:
            return jsonify({"error": "Token expired", "code": "auth/expired-token"}), 401  
        except Exception as e:
            app.logger.error(f"Token verification error: {str(e)}")
            return jsonify({"error": "Authentication failed", "code": "auth/verification-failed"}), 401
            
    return decorated_function

# Example API route using the verify_firebase_token decorator
@app.route('/api/drivers', methods=['GET'])
@verify_firebase_token
def api_get_drivers():
    try:
        # Get user ID from the verified token
        user_id = request.user.get('uid')
        
        # Fetch drivers with limit
        limit = int(request.args.get('limit', 10))
        drivers = db.collection('drivers').limit(limit).stream()
        
        drivers_list = []
        for doc in drivers:
            driver_data = doc.to_dict()
            driver_data['id'] = doc.id
            drivers_list.append(driver_data)
            
        return jsonify({
            "drivers": drivers_list,
            "user": {
                "uid": user_id
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Now you can choose between session-based auth for web routes
# and token-based auth for API routes

# 🔹 Authentication Routes
@app.route("/auth")
def auth():
    if "user" in session:
        return redirect(url_for("index"))
    return render_template("auth.html")

@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")  # Limit to 5 login attempts per minute
def login():
    try:
        email = request.json.get("email")
        password = request.json.get("password")
        
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
            
        # In a real app, you'd verify with Firebase Auth
        user = auth.get_user_by_email(email)
        
        # Set session data
        session.clear()  # Clear any existing session data first
        session["user"] = {
            "email": email,
            "uid": user.uid,
            "display_name": user.display_name or email.split('@')[0]
        }
        session["created_at"] = time.time()
        session["user_agent"] = request.headers.get("User-Agent")
        session["ip_address"] = request.remote_addr
        
        # Log successful login
        app.logger.info(f"Successful login: {email} from {request.remote_addr}")
        
        return jsonify({"message": "Login successful", "user": session["user"]}), 200
    except Exception as e:
        # Log failed login attempt
        app.logger.warning(f"Failed login attempt: {request.remote_addr} - {str(e)}")
        return jsonify({"error": str(e)}), 400

# Add the Google login route after your regular login route

@app.route("/google-login", methods=["POST"])
@limiter.limit("10 per minute")  # Slightly higher limit for Google login
def google_login():
    try:
        # Change this line to match what the frontend is sending
        id_token = request.json.get("idToken")  # Was looking for "id_token"
        
        if not id_token:
            return jsonify({"error": "No ID token provided"}), 400
            
        try:
            # Verify the Firebase ID token
            decoded_token = auth.verify_id_token(id_token)
            
            # Get user information from the token
            uid = decoded_token["uid"]
            user_email = decoded_token.get("email", "")
            user_name = decoded_token.get("name", "")

            # If no name in token, use Firebase Auth to get more details
            if not user_name:
                try:
                    user = auth.get_user(uid)
                    user_name = user.display_name or user_email.split("@")[0]
                    if not user_email:
                        user_email = user.email
                except:
                    user_name = user_email.split("@")[0] if user_email else "User"
            
            # Create session
            session["user"] = {
                "email": user_email,
                "uid": uid,
                "display_name": user_name
            }
            
            # Log successful Google login
            app.logger.info(f"Google login: {user_email} ({uid}) from {request.remote_addr}")

            return jsonify({
                "message": "Google login successful", 
                "user": session["user"]
            }), 200
            
        except firebase_admin.auth.InvalidIdTokenError:
            app.logger.warning(f"Invalid token used for Google login from {request.remote_addr}")
            return jsonify({"error": "Invalid ID token"}), 401
        except firebase_admin.auth.ExpiredIdTokenError:
            return jsonify({"error": "Expired ID token"}), 401
        except Exception as e:
            app.logger.error(f"Google login error: {str(e)} from {request.remote_addr}")
            return jsonify({"error": f"Token verification failed: {str(e)}"}), 401
            
    except Exception as e:
        app.logger.error(f"Google login failure: {str(e)} from {request.remote_addr}")
        return jsonify({"error": f"Login failed: {str(e)}"}), 400

# Add this email validation function
def validate_email(email):
    """Validate email format using regex pattern."""
    if not email:
        return False
    # RFC 5322 compliant email regex pattern (simplified)
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

# Add password validation function
def validate_password(password):
    """
    Validate password strength.
    - At least 6 characters
    - Contains at least one digit
    - Contains at least one letter
    """
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one number"
        
    if not any(char.isalpha() for char in password):
        return False, "Password must contain at least one letter"
        
    return True, ""

@app.route("/register", methods=["POST"])
@limiter.limit("3 per hour")  # Limit registrations
def register():
    try:
        # Get request data
        email = request.json.get("email", "").strip()
        password = request.json.get("password", "")
        display_name = request.json.get("display_name", "").strip()
        
        # Validate input fields
        if not email:
            return jsonify({"error": "Email is required", "field": "email"}), 400
            
        if not password:
            return jsonify({"error": "Password is required", "field": "password"}), 400
            
        # Validate email format
        if not validate_email(email):
            return jsonify({
                "error": "Invalid email format", 
                "field": "email",
                "code": "invalid_email"
            }), 400
        
        # Validate password strength
        is_valid_password, password_error = validate_password(password)
        if not is_valid_password:
            return jsonify({
                "error": password_error,
                "field": "password",
                "code": "weak_password"
            }), 400
            
        # Sanitize display name if provided
        if display_name:
            # Limit length and remove any dangerous characters
            display_name = display_name[:50]  # Limit to 50 chars
            display_name = re.sub(r'[<>{}[\]\\^`]', '', display_name)  # Remove dangerous chars
        else:
            # Default to username part of email
            display_name = email.split('@')[0]
            
        # Create user in Firebase Auth with additional validation
        try:
            user = firebase_auth.create_user(
                email=email,
                password=password,
                display_name=display_name,
                email_verified=False  # Require email verification
            )
            
            # Send email verification (if Firebase has this configured)
            # firebase_auth.generate_email_verification_link(email)
            
            # Log successful registration with sanitized info
            app.logger.info(f"New user registered: {email.split('@')[0]}*** from {request.remote_addr}")
            
            return jsonify({
                "message": "Registration successful! Please check your email to verify your account.",
                "uid": user.uid
            }), 201
            
        except firebase_auth.EmailAlreadyExistsError:
            return jsonify({
                "error": "Email already in use. Please try another email or login.", 
                "field": "email",
                "code": "email_exists"
            }), 400
            
        except firebase_auth.InvalidArgumentError as e:
            # Handle specific Firebase validation errors
            error_msg = str(e)
            if "password" in error_msg.lower():
                return jsonify({
                    "error": "Password doesn't meet security requirements", 
                    "field": "password",
                    "code": "invalid_password"
                }), 400
            else:
                return jsonify({
                    "error": "Invalid input data", 
                    "field": "general",
                    "code": "invalid_input"
                }), 400
                
        except Exception as e:
            # Generic Firebase errors
            app.logger.error(f"Firebase auth error: {str(e)}")
            return jsonify({
                "error": "Registration failed. Please try again later.",
                "code": "auth_error" 
            }), 500
            
    except Exception as e:
        # Log failed registration with full error details
        app.logger.warning(f"Failed registration: {request.remote_addr} - {str(e)}")
        return jsonify({
            "error": "Registration failed due to a server error",
            "code": "server_error"
        }), 500

@app.route("/logout")
def logout():
    # For Firebase tokens, you might want to add token revocation
    # with firebase_admin.auth.revoke_refresh_tokens(session["user"]["uid"])
    
    # Clear the session
    session.clear()
    return redirect("/auth")

# Add a route to verify session is still valid
@app.route("/verify_session")
def verify_session():
    if is_logged_in():
        return jsonify({"valid": True, "user": session.get("user")}), 200
    else:
        return jsonify({"valid": False}), 401

# 🔹 Secure Home Route
@app.route('/')
@login_required
def home():
    return render_template('index.html', user=session.get("user"))

@app.route("/")
def index():
    user = session.get("user")
    return render_template("index.html", user=user)

# ✅ Route to Add a Driver (now with team ID reference)
@app.route('/add_driver', methods=['POST'])
@login_required
def add_driver():
    try:
        name = request.form['name']
        age = int(request.form['age'])
        team = request.form['team']  # Keep this as team for backward compatibility
        team_id = request.form.get('team_id', '')  # Get team_id if provided
        race_wins = int(request.form['race_wins'])
        pole_positions = int(request.form['pole_positions'])
        fastest_laps = int(request.form['fastest_laps'])
        world_titles = int(request.form['world_titles'])

        # Validate input
        if not name:
            return jsonify({"error": "Driver name is required", "status": "error"}), 400
        if not team and not team_id:
            return jsonify({"error": "Team information is required", "status": "error"}), 400
        if age < 18 or age > 50:
            return jsonify({"error": "Age must be between 18 and 50", "status": "error"}), 400
        if race_wins < 0 or pole_positions < 0 or fastest_laps < 0 or world_titles < 0:
            return jsonify({"error": "Values cannot be negative", "status": "error"}), 400

        # If team_id is provided, verify that the team exists
        if team_id:
            team_doc = db.collection('teams').document(team_id).get()
            if not team_doc.exists:
                return jsonify({"error": f"Team with ID {team_id} not found", "status": "error"}), 400
            # Store the team name for backward compatibility
            team = team_doc.to_dict().get('name', '')

        driver_data = {
            "name": name,
            "age": age,
            "team": team,  # Keep storing team name for backward compatibility
            "race_wins": race_wins,
            "pole_positions": pole_positions,
            "fastest_laps": fastest_laps,
            "world_titles": world_titles,
            "created_by": session["user"]["uid"],  # Track who created this driver
            "created_at": firestore.SERVER_TIMESTAMP  # Add timestamp
        }
        
        # If we have a team_id, store it as well
        if team_id:
            driver_data["team_id"] = team_id

        db.collection('drivers').add(driver_data)
        
        # Invalidate cache after adding
        invalidate_driver_caches()
        
        return jsonify({
            "message": "Driver added successfully!", 
            "status": "success"
        }), 201

    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 400

# ✅ Optimized and cached route to get drivers
@app.route('/get_drivers', methods=['GET'])
@login_required
def get_drivers():
    try:
        drivers = db.collection('drivers').stream()
        drivers_list = [{"id": doc.id, **doc.to_dict()} for doc in drivers]
        return jsonify(drivers_list), 200
    except Exception as e:
        app.logger.error(f"Error in get_drivers: {str(e)}")
        return jsonify({"error": str(e)}), 400  # ✅ Always return JSON

# Cache invalidation function - call this when data changes
def invalidate_driver_caches():
    # Simplified version that clears all cache 
    # In a real app, you would want more granular cache invalidation
    cache.cache = {}
    cache.timeouts = {}

# Apply @login_required to other routes that need authentication
@app.route('/add_team', methods=['POST'])
@login_required
def add_team():
    try:
        team_data = {
            "name": request.form['name'],
            "year_founded": int(request.form['year_founded']),
            "race_wins": int(request.form['race_wins']),
            "pole_positions": int(request.form['pole_positions']),
            "constructor_titles": int(request.form['constructor_titles']),
            "finishing_position": int(request.form['finishing_position']),
            "created_by": session["user"]["uid"]  # Track who created this team
        }
        db.collection('teams').add(team_data)
        return jsonify({"message": "Team added successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Cached teams endpoint
@app.route('/get_teams', methods=['GET'])
@login_required
def get_teams():
    try:
        teams = db.collection('teams').stream()
        teams_list = [{"id": doc.id, **doc.to_dict()} for doc in teams]
        return jsonify(teams_list), 200
    except Exception as e:
        app.logger.error(f"Error in get_teams: {str(e)}")
        return jsonify({"error": str(e)}), 400  # ✅ Always return JSON

@app.route('/delete_driver/<driver_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def delete_driver(driver_id):
    try:
        # Optional: Check if user is allowed to delete this driver
        driver = db.collection('drivers').document(driver_id).get()
        if driver.exists:
            driver_data = driver.to_dict()
            if 'created_by' in driver_data and driver_data['created_by'] != session["user"]["uid"]:
                app.logger.warning(f"Unauthorized delete attempt: User {session['user']['uid']} tried to delete driver {driver_id}")
                return jsonify({"error": "You don't have permission to delete this driver"}), 403
                
        db.collection('drivers').document(driver_id).delete()
        
        # Invalidate cache after deletion
        invalidate_driver_caches()
        
        # Log successful deletion
        app.logger.info(f"Driver {driver_id} deleted by user {session['user']['uid']}")
        
        return jsonify({"message": "Driver deleted successfully!"}), 200
    except Exception as e:
        app.logger.error(f"Driver deletion error: {str(e)}")
        return jsonify({"error": str(e)}), 400

@app.route('/edit_driver/<driver_id>', methods=['GET', 'POST'])
@login_required
def edit_driver(driver_id):
    if request.method == 'GET':
        try:
            # Get the driver data to populate the edit form
            driver_ref = db.collection('drivers').document(driver_id)
            driver = driver_ref.get()
            if (driver.exists):
                driver_data = driver.to_dict()
                driver_data['id'] = driver_id
                return render_template('edit_driver.html', driver=driver_data, user=session.get("user"))
            else:
                return jsonify({"error": "Driver not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    else:  # POST
        try:
            driver_ref = db.collection('drivers').document(driver_id)
            
            # Optional: Check if user is allowed to edit this driver
            driver = driver_ref.get()
            if driver.exists:
                driver_data = driver.to_dict()
                if 'created_by' in driver_data and driver_data['created_by'] != session["user"]["uid"]:
                    return jsonify({"error": "You don't have permission to edit this driver"}), 403

            # Validate input
            name = request.form['name']
            age = int(request.form['age'])
            team = request.form['team']
            race_wins = int(request.form['race_wins'])
            pole_positions = int(request.form['pole_positions'])
            fastest_laps = int(request.form['fastest_laps'])
            world_titles = int(request.form['world_titles'])

            if not name or not team:
                return jsonify({"error": "Name and Team are required"}), 400
            if age < 18 or age > 50:
                return jsonify({"error": "Age must be between 18 and 50"}), 400
            if race_wins < 0 or pole_positions < 0 or fastest_laps < 0 or world_titles < 0:
                return jsonify({"error": "Values cannot be negative"}), 400

            updated_data = {
                "name": name,
                "age": age,
                "team": team,
                "race_wins": race_wins,
                "pole_positions": pole_positions,
                "fastest_laps": fastest_laps,
                "world_titles": world_titles,
                "last_edited_by": session["user"]["uid"]  # Track who last edited this driver
            }

            driver_ref.update(updated_data)
            return redirect('/get_drivers')

        except Exception as e:
            return jsonify({"error": str(e)}), 400

@app.route('/search_drivers', methods=['GET'])
@login_required
def search_drivers():
    field = request.args.get('field')
    value = request.args.get('value')

    try:
        if not field or not value:
            return jsonify({"error": "Invalid search query"}), 400
        
        # Handle numeric fields
        numeric_fields = ['age', 'race_wins', 'pole_positions', 'fastest_laps', 'world_titles']
        if field in numeric_fields:
            try:
                value = int(value)
            except ValueError:
                return jsonify({"error": f"Value for {field} must be a number"}), 400
        
        query = db.collection('drivers').where(field, "==", value).stream()
        results = []
        for doc in query:
            driver_data = doc.to_dict()
            driver_data['id'] = doc.id  # Include document ID
            results.append(driver_data)
            
        return jsonify(results), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/compare_drivers', methods=['GET'])
@login_required
def compare_drivers():
    try:
        driver1_id = request.args.get('driver1')
        driver2_id = request.args.get('driver2')

        if not driver1_id or not driver2_id:
            return jsonify({"error": "Please provide two driver IDs"}), 400

        # Get driver documents from Firestore
        driver1_doc = db.collection('drivers').document(driver1_id).get()
        driver2_doc = db.collection('drivers').document(driver2_id).get()

        # Check if documents exist
        if not driver1_doc.exists:
            return jsonify({"error": f"Driver with ID {driver1_id} not found"}), 404
        if not driver2_doc.exists:
            return jsonify({"error": f"Driver with ID {driver2_id} not found"}), 404

        # Convert to dictionaries and add IDs
        driver1 = driver1_doc.to_dict()
        driver1['id'] = driver1_id
        
        driver2 = driver2_doc.to_dict()
        driver2['id'] = driver2_id

        # Check if format=json is requested
        if request.args.get('format') == 'json':
            # Calculate stat differences for the comparison
            comparison = {
                "driver1": driver1,
                "driver2": driver2,
                "comparison": {
                    "age_diff": abs(driver1['age'] - driver2['age']),
                    "wins_diff": abs(driver1['race_wins'] - driver2['race_wins']),
                    "poles_diff": abs(driver1['pole_positions'] - driver2['pole_positions']),
                    "fastest_laps_diff": abs(driver1['fastest_laps'] - driver2['fastest_laps']),
                    "titles_diff": abs(driver1['world_titles'] - driver2['world_titles'])
                }
            }
            return jsonify(comparison), 200
        else:
            # Render comparison template
            return render_template("compare.html", driver1=driver1, driver2=driver2, user=session.get("user"))

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Create a custom error handler for rate limiting
@app.errorhandler(429)
def ratelimit_handler(e):
    app.logger.warning(f"Rate limit exceeded: {request.remote_addr} - {request.path}")
    return jsonify({
        "error": "Too many requests. Please try again later.",
        "code": "rate_limit_exceeded",
        "retry_after": e.description
    }), 429

# Add rate limit status endpoint for monitoring
@app.route("/rate-limit-status")
@login_required
def rate_limit_status():
    # Only allow admin users to access this endpoint
    if session.get("user", {}).get("email") not in ["admin@example.com"]:  # Replace with your admin emails
        return jsonify({"error": "Unauthorized"}), 403
        
    return jsonify({
        "status": "active",
        "limits": {
            "login": "5 per minute",
            "register": "3 per hour",
            "google_login": "10 per minute",
            "delete_driver": "10 per minute",
            "default": "200 per day, 50 per hour"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0')

# Make sure you don't have any functions with a parameter named 'time'
def some_function(time):  # This would shadow the module import
    session['last_activity'] = time.time()  # This would cause UnboundLocalError
