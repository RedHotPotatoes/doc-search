FROM python:3.11.9-slim

WORKDIR /app

COPY . /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir -r requirements.txt

CMD ["fastapi", "dev", "app.py", "--reload", "--host", "0.0.0.0"]
