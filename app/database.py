from firebase_admin import firestore
from flask import current_app
import time
from functools import wraps

db = firestore.client()

# Performance monitoring decorator
def measure_time(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Log if query is slow (more than 500ms)
        if execution_time > 0.5:
            current_app.logger.warning(
                f"Slow database operation: {f.__name__} took {execution_time:.2f}s with args: {args}, kwargs: {kwargs}"
            )
        return result
    return decorated_function

# Implement pagination for drivers collection
@measure_time
def get_drivers(limit=10, start_after=None, filters=None):
    """
    Get drivers with pagination and optional filtering
    
    Args:
        limit (int): Maximum number of drivers to retrieve
        start_after (str): Document ID to start after (for pagination)
        filters (dict): Optional filters like {'team_id': 'team123', 'min_wins': 5}
    
    Returns:
        tuple: (List of drivers, Last document for pagination)
    """
    query = db.collection("drivers")
    
    # Apply filters if provided
    if filters:
        if 'team_id' in filters and filters['team_id']:
            query = query.where('team_id', '==', filters['team_id'])
            
        if 'min_wins' in filters and filters['min_wins']:
            query = query.where('race_wins', '>=', int(filters['min_wins']))
            
        if 'nationality' in filters and filters['nationality']:
            query = query.where('nationality', '==', filters['nationality'])
            
        if 'active' in filters:
            query = query.where('active', '==', filters['active'])
    
    # Apply default sort (by name)
    query = query.order_by('name')
    
    # Apply pagination
    if start_after:
        start_doc = db.collection("drivers").document(start_after).get()
        if start_doc.exists:
            query = query.start_after(start_doc)
    
    # Limit results
    query = query.limit(limit)
    
    # Execute query
    drivers_docs = query.stream()
    
    # Convert to list and get last doc for pagination
    drivers = []
    last_doc = None
    
    for doc in drivers_docs:
        drivers.append({"id": doc.id, **doc.to_dict()})
        last_doc = doc.id
    
    return drivers, last_doc

# Get driver by ID with caching considerations
@measure_time
def get_driver(driver_id):
    """Get a single driver by ID"""
    doc = db.collection("drivers").document(driver_id).get()
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None

# Add a driver with proper validation
@measure_time
def add_driver(data, user_id):
    """
    Add a new driver with validation and user tracking
    
    Args:
        data (dict): Driver data
        user_id (str): ID of the user creating the driver
    """
    # Add metadata
    data['created_at'] = firestore.SERVER_TIMESTAMP
    data['created_by'] = user_id
    data['updated_at'] = firestore.SERVER_TIMESTAMP
    
    # Set defaults for missing fields
    data.setdefault('race_wins', 0)
    data.setdefault('pole_positions', 0)
    data.setdefault('fastest_laps', 0)
    data.setdefault('active', True)
    
    # Add document and return reference
    doc_ref = db.collection("drivers").add(data)
    return doc_ref[1].id  # Return the document ID

# Update a driver
@measure_time
def update_driver(driver_id, data, user_id):
    """Update an existing driver"""
    # Don't allow changing creation metadata
    if 'created_at' in data:
        del data['created_at']
    if 'created_by' in data:
        del data['created_by']
        
    # Add update metadata
    data['updated_at'] = firestore.SERVER_TIMESTAMP
    data['updated_by'] = user_id
    
    # Update document
    db.collection("drivers").document(driver_id).update(data)
    return driver_id

# Delete a driver
@measure_time
def delete_driver(driver_id):
    """Delete a driver by ID"""
    db.collection("drivers").document(driver_id).delete()
    return driver_id

# Get all teams (usually a small collection, so pagination might not be needed)
@measure_time
def get_teams():
    """Get all teams"""
    teams = db.collection("teams").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in teams]

# Stats and aggregation (efficient with batched reads)
@measure_time
def get_driver_stats():
    """Get aggregated driver statistics"""
    stats = {}
    
    # Use batched reads for efficiency
    batch_size = 10
    drivers_ref = db.collection("drivers").limit(batch_size)
    
    # Calculate totals
    total_drivers = 0
    total_wins = 0
    drivers_by_team = {}
    
    # Process in batches to avoid memory issues
    docs = drivers_ref.stream()
    batch = list(docs)
    
    while batch:
        for doc in batch:
            data = doc.to_dict()
            total_drivers += 1
            total_wins += data.get('race_wins', 0)
            
            # Count drivers by team
            team_id = data.get('team_id')
            if team_id:
                if team_id not in drivers_by_team:
                    drivers_by_team[team_id] = 0
                drivers_by_team[team_id] += 1
        
        # Get next batch
        last = batch[-1]
        docs = drivers_ref.start_after(last).stream()
        batch = list(docs)
    
    stats['total_drivers'] = total_drivers
    stats['total_wins'] = total_wins
    stats['drivers_by_team'] = drivers_by_team
    
    return stats
