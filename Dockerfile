FROM registry.access.redhat.com/ubi8/python-39:latest

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app.py prompt.txt ./

# Create cache directory with proper permissions
RUN mkdir -p /app/cache && \
    chmod 777 /app/cache

ENV FLASK_APP=app.py
ENV OPENROUTER_API_KEY=none
ENV OPENROUTER_MODEL=google/gemini-2.0-flash-001

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
