FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini /app/
COPY alembic /app/alembic
COPY platform_core /app/platform_core
COPY scripts /app/scripts
RUN useradd --system --create-home appuser
USER appuser
EXPOSE 8080
CMD ["uvicorn", "platform_core.server:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
