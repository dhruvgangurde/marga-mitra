FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY contracts ./contracts
COPY policy ./policy
COPY data ./data
COPY risk ./risk
COPY solver ./solver
COPY evals ./evals
COPY agents ./agents
COPY backend ./backend
COPY scripts ./scripts
COPY pyproject.toml ./
RUN mkdir -p /app/uploads
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
