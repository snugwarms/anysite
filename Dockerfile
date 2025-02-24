FROM registry.access.redhat.com/ubi8/python-39:latest

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app.py .

# Create cache directory with proper permissions
RUN mkdir -p /app/cache && \
    chmod 777 /app/cache

ENV FLASK_APP=app.py
ENV OPENROUTER_API_KEY=none
ENV OPENROUTER_MODEL=google/gemini-2.0-flash-001
ENV PROMPT_TEMPLATE="Generate a webpage about \"{path}\". \nThe content should be informative and engaging.\nReturn only the HTML content for the body (no <html>, <head>, or <body> tags).\nUse semantic HTML elements and include proper headings."

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
