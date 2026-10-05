FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY data ./data
COPY samples ./samples
RUN useradd --create-home appuser && mkdir /app/var && chown appuser:appuser /app/var
USER appuser
ENV MODEL_PROVIDER=demo APP_STORAGE=/app/var
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
