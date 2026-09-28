FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system orion && adduser --system --ingroup orion orion

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=orion:orion . .

USER orion
EXPOSE 8000

CMD ["uvicorn", "orion_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
