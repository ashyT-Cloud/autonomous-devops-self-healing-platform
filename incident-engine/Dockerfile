FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --system --uid 10001 --create-home appuser

WORKDIR /app
COPY src/controller.py /app/controller.py

USER 10001:10001

EXPOSE 8081

CMD ["python", "/app/controller.py", "--webhook"]
