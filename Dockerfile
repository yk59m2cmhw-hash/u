FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Optional dependency for the Claude provider; the offline and Gemini providers need only the standard library.
RUN pip install --no-cache-dir "anthropic==2.8.0"

COPY okno/ okno/
RUN useradd --create-home okno && mkdir -p /app/data && chown okno /app/data
USER okno

EXPOSE 8080
CMD ["python", "-m", "okno.web", "--host", "0.0.0.0", "--port", "8080"]
