# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 5000 for Flask
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=app.py

# Hardcoded ENV (only for assignment purposes)
ENV FLASK_ENV=development
ENV SECRET_KEY=dev-secret-key
ENV DATABASE_URL=sqlite:///db.sqlite3

ENV MINIO_ENDPOINT=http://minio:9000
ENV MINIO_ACCESS_KEY=minioadmin
ENV MINIO_SECRET_KEY=minioadmin123
ENV MINIO_BUCKET=tk-image-storage

# Run the application with gunicorn
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:5000", "app:app"]
