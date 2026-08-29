FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api ./apps/api
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "proofledger.main:app", "--host", "0.0.0.0", "--port", "8000"]
