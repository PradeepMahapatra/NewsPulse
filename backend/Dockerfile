FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN sed '/^torch[<>=]/d' /app/backend/requirements.txt > /tmp/backend-requirements-no-torch.txt \
    && pip install --no-cache-dir -r /tmp/backend-requirements-no-torch.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu 'torch>=2.2,<3.0'

COPY backend /app/backend

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
