# Use Python base image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080
EXPOSE 8080

# Command to run the app
CMD ["gunicorn", "-b", ":8080", "app:app"]
