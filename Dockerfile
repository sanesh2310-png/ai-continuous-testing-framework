FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shop ./shop
ENV DB_PATH=/data/app.db PORT=5000
RUN mkdir -p /data
EXPOSE 5000
CMD ["sh", "-c", "gunicorn --workers 2 --threads 4 -b 0.0.0.0:${PORT} 'shop.app:create_app()'"]
