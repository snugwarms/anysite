FROM registry.access.redhat.com/ubi8/python-39:latest

# Create non-root user
RUN useradd -m -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py prompt.txt index.html robots.txt ./

# Create cache directory with proper permissions
RUN mkdir -p /cache && \
    chown appuser:appuser /cache && \
    chmod 755 /cache

# Set environment variables
ENV FLASK_APP=app.py \
    OPENROUTER_API_KEY=none \
    OPENROUTER_MODEL=google/gemini-2.0-flash-001 \
    PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Run with reduced privileges
CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0"]
