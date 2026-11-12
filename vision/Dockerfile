FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 YOLO_CONFIG_DIR=/tmp/yolo
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libxcb1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install ultralytics opencv-python-headless httpx
# Weights are baked into the image so the worker needs no internet at runtime.
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
COPY backend/app/ai_operations/geometry.py backend/app/ai_operations/occupancy.py backend/app/ai_operations/fusion.py backend/app/ai_operations/dishes.py /app/app/ai_operations/
RUN touch /app/app/__init__.py /app/app/ai_operations/__init__.py
COPY vision/worker.py /app/worker.py
RUN useradd --uid 10001 vision && chown -R vision /app
USER vision
ENV VISION_MODEL=/app/yolov8n.pt
CMD ["python", "worker.py"]
