FROM registry.access.redhat.com/ubi8/python-39:latest

# Set working directory
WORKDIR /app

# Switch to root to create cache directory
USER 0

# Create cache directory with proper permissions
RUN mkdir -p /cache && \
    chgrp -R 0 /cache && \
    chmod -R g=u /cache

# Switch back to default non-root user
USER 1001

# Install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py prompt.txt index.html robots.txt ./

# Set environment variables
ENV FLASK_APP=app.py \
    OPENROUTER_API_KEY=none \
    OPENROUTER_MODEL=google/gemini-2.0-flash-001 \
    PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Run with reduced privileges
CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0"]
