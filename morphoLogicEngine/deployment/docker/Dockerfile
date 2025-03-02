# Use Python 3.12+ as base image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code
COPY . .

# Expose ports (modify as needed)
# EXPOSE 8080 9090

# Run the server
CMD ["python", "-m", "morphologic_server"]
