from flask import Flask
from flask_caching import Cache
from flask_limiter import Limiter
from dotenv import load_dotenv
import os
from datetime import timedelta

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
    app.permanent_session_lifetime = timedelta(hours=2)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-secret")

    # Setup Caching (Redis)
    cache = Cache(app, config={"CACHE_TYPE": "redis", "CACHE_REDIS_URL": "redis://localhost:6379/0"})

    # Setup Rate Limiting
    limiter = Limiter(app, default_limits=["100 per hour", "10 per minute"])

    # Register blueprints
    from app.auth import auth_bp
    from app.routes import routes_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(routes_bp, url_prefix="/api")

    # More blueprints can be registered here
    
    @app.before_request
    def make_session_permanent():
        from flask import session, request, redirect
        import time
        
        session.permanent = True
        
        if 'last_activity' in session and 'user' in session:
            last_active = session['last_activity']
            current_time = time.time()
            
            # If inactive for too long, clear session (2 hours)
            if current_time - last_active > 7200:  # 2 hours in seconds
                session.clear()
                
                # Only redirect if not already heading to auth page
                if not request.path.startswith('/auth') and not request.path.startswith('/api/auth'):
                    return redirect('/auth')
        
        session['last_activity'] = time.time()
    
    return app
