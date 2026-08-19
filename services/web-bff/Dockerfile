FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src ./src

RUN pip install --no-cache-dir .

CMD ["uvicorn", "housepricing_web_bff.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]