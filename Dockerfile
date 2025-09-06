FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY DMBot.py .
COPY helpers/ ./helpers/
COPY handlers/ ./handlers/
COPY tools/ ./tools/

ENV PORT 8080
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 DMBot:app