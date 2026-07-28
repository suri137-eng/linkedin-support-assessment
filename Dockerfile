FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

RUN mkdir -p /app/data
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000

# Shell form so $PORT (injected by Render and most PaaS hosts) is honored,
# falling back to 8000 for plain `docker run`.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
