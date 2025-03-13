# Formula 1 Database Project Report

## 1. Project Overview

The **Formula 1 Database Project** is a robust web application designed to manage Formula 1 driver and team data using **Flask** and **Firebase/Firestore**. This project provides users with the ability to store, view, and manage data about F1 teams and drivers, featuring a secure authentication system that restricts data modifications to authorized users, while offering read-only access to the public. The application architecture follows modern web standards with distinct frontend and backend components for an optimized user experience.

## 2. System Architecture

### 2.1 Technology Stack

- **Backend**: Python Flask
- **Database**: Firebase Firestore (NoSQL)
- **Authentication**: Firebase Authentication
- **Frontend**: HTML, CSS (Bootstrap), JavaScript
- **Templating**: Jinja2

### 2.2 Project Structure

```
f1_database_project/
├── app/
│   ├── __init__.py
│   ├── routes.py
│   ├── database.py
│   ├── auth.py
│   └── db_utils.py
├── templates/
│   ├── index.html
│   ├── drivers.html
│   ├── edit_driver.html
│   └── ...
├── static/
│   └── css/
│       └── styles.css
├── public/
│   └── index.html
├── firebase-admin-sdk.json
├── main.py
└── app.py
```

## 3. Implementation Details

### 3.1 Authentication System

Leveraging **Firebase Authentication**, the application ensures secure user access. Routes are protected with a decorator to verify user sessions before granting access to restricted resources.

```python
@login_required
def add_driver():
    # Only authenticated users can add new drivers
```

To avoid abuse, user registration is rate-limited:

```python
@app.route("/register", methods=["POST"])
@limiter.limit("3 per hour")  # Restrict registration attempts
def register():
    # Registration logic with security features
    # - Email validation
    # - Password strength enforcement
```

### 3.2 Database Structure

The database comprises two key Firestore collections:

#### Drivers Collection
- Name
- Age
- Team (reference)
- Race wins
- Pole positions
- Fastest laps
- World titles
- Metadata (timestamp, user ID)

#### Teams Collection
- Name
- Year founded
- Race wins
- Constructor titles
- Previous season performance
- Metadata

### 3.3 Data Access Layer

Dedicated functions handle database operations, integrating performance monitoring to ensure efficiency:

```python
@measure_time
def get_drivers(limit=10, start_after=None, filters=None):
    """
    Retrieves drivers with optional filters and pagination
    """
    query = db.collection("drivers")
    # Filter and pagination logic
```

## 4. Key Features

### 4.1 Driver Management

The application allows full CRUD operations for driver profiles with validation to maintain data integrity:
- Name validation
- Age constraints (18-50 years)
- Non-negative statistics (e.g., race wins)

### 4.2 Team Management

Similar functionality is provided for managing team data with validations to ensure:
- Team name uniqueness
- Accurate performance data

### 4.3 Search and Filtering

Powerful search and filter options allow users to query drivers and teams based on:
- Team name
- Race wins
- World titles

```python
@app.route('/search_drivers', methods=['GET'])
@login_required
def search_drivers():
    # Apply filters and return results
```

### 4.4 Driver Comparison

Users can compare two drivers side by side, highlighting differences in their statistics, enabling easy comparison of their achievements.

```html
<table class="table table-dark table-striped">
    <thead>
        <tr>
            <th>${d1.name}</th>
            <th>Statistic</th>
            <th>${d2.name}</th>
            <th>Diff</th>
        </tr>
    </thead>
    <tbody>
        <!-- Compare stats like age, race wins, etc. -->
    </tbody>
</table>
```

### 4.5 Performance Optimization

Techniques for performance enhancement include:
- **Client-side caching** to reduce server load
- **Pagination** to handle large datasets efficiently
- **Query Monitoring** for optimization
- **Rate Limiting** to avoid overloading the system

```javascript
// Global variables and cache setup
let nextPageToken = null;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
```

## 5. Security Measures

### 5.1 Authentication & Authorization

The app ensures secure operations:
- Login is required for all modification actions.
- Secure session handling with expiry.
- Rate limiting for sensitive operations.

### 5.2 Input Validation

User inputs are rigorously validated both on the client and server side to ensure proper data integrity:

```python
if age < 18 or age > 50:
    return jsonify({"error": "Age must be between 18 and 50", "status": "error"}), 400
```

### 5.3 Data Sanitization

User inputs are sanitized to prevent security risks like injection attacks:

```python
# Sanitize display names
if display_name:
    display_name = re.sub(r'[<>{}[\]\\^`]', '', display_name)  # Remove dangerous chars
```

## 6. User Interface

Built with **Bootstrap**, the UI is responsive and user-friendly:
- **Navigation bar** for login/logout controls
- **Validation feedback** for forms
- **Sortable tables** for data organization
- **Driver comparison tool** for side-by-side analysis
- Mobile-first design for accessibility

```html
<table class="table table-striped table-hover">
    <thead>
        <tr>
            <th onclick="sortTable(0)" class="sortable">Name</th>
            <th onclick="sortTable(1)" class="sortable">Age</th>
            <!-- Other columns -->
        </tr>
    </thead>
</table>
```

## 7. Function Documentation

### 7.1 Database Functions

#### `get_drivers(limit=10, start_after=None, filters=None)`
This function retrieves a paginated list of drivers, with optional filters.

#### `add_driver(data, user_id)`
Creates a new driver record with proper validation and metadata.

#### `update_driver(driver_id, data, user_id)`
Updates an existing driver’s information, maintaining original metadata.

#### `delete_driver(driver_id)`
Deletes a driver record from the database.

#### `get_driver_stats()`
Aggregates driver statistics efficiently to reduce memory consumption.

### 7.2 Authentication Functions

#### `login_required`
A decorator that restricts access to authenticated users.

#### `register()`
Handles the user registration process, ensuring input validation and security.

### 7.3 Utility Functions

#### `measure_time`
Tracks the execution time of database operations for optimization purposes.

#### `batch_get(doc_refs)`
Efficiently retrieves multiple documents in batches.

## 8. Challenges and Solutions

### 8.1 NoSQL Query Limitations
**Challenge**: Firestore's query limitations required workaround solutions.

**Solution**: Implemented structured data with denormalization and client-side filtering.

### 8.2 Performance with Large Datasets
**Challenge**: Handling large datasets caused performance issues.

**Solution**: Pagination, client-side caching, and batch operations were introduced.

### 8.3 User Experience
**Challenge**: Designing a UI suitable for both casual and power users.

**Solution**: Introduced progressive disclosure, sortable tables, and comparison features.

## 9. Conclusion

The **Formula 1 Database Project** provides a secure, efficient, and user-friendly platform for managing Formula 1 driver and team data. It incorporates best practices in web development, focusing on security, performance optimization, and data handling. This project offers a comprehensive solution for Formula 1 data management, from user authentication to advanced data filtering and comparison.