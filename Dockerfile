FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy application files first
COPY requirements.txt .
COPY app.py prompt.txt index.html robots.txt ./

# Create non-root user and set up permissions
RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser && \
    mkdir -p /cache && \
    touch /cache/requests && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /cache && \
    chmod 777 /cache && \
    chmod 666 /cache/requests && \
    ls -la /cache

# Install dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER appuser

# Set environment variables
ENV FLASK_APP=app.py \
    OPENROUTER_API_KEY=none \
    OPENROUTER_MODEL=google/gemini-2.0-flash-001 \
    PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Run with reduced privileges
CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0"]
