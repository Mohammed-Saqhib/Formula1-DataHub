# filepath: e:\Intership's Memories\f1_database_project\app.py
from flask import Flask
from routes.auth import auth_bp
from routes.drivers import drivers_bp
from routes.teams import teams_bp
from utils.logging import log_info, log_error

app = Flask(__name__)
app.config.from_object('config')  # Load configurations

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(drivers_bp, url_prefix='/drivers')
app.register_blueprint(teams_bp, url_prefix='/teams')

# Log server startup
try:
    log_info("Server is starting...")
    log_info(f"Registered blueprints: auth, drivers, teams")
    log_info(f"Debug mode: {app.debug}")
except Exception as e:
    log_error(f"Error starting server: {e}")

if __name__ == '__main__':
    app.run(debug=True)
