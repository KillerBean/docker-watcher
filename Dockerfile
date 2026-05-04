FROM python:3.12-slim

RUN pip install --no-cache-dir docker==7.1.0 requests==2.32.3

WORKDIR /app
COPY watcher.py .

CMD ["python", "-u", "watcher.py"]
