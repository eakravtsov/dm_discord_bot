FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY DMBot.py .
COPY helpers/ ./helpers/
COPY handlers/ ./handlers/

CMD ["python", "DMBot.py"]