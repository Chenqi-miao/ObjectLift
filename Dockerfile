FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements-image.txt requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt
COPY services ./services
COPY ui ./ui
COPY app.py schemas.py ./
ENV OBJECTLIFT_HOST=0.0.0.0 GRADIO_ANALYTICS_ENABLED=False
EXPOSE 7860
CMD ["python", "app.py"]
