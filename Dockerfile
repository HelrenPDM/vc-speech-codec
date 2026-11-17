FROM debian:13-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 ffmpeg libvo-amrwbenc0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY process.py /app/process.py
COPY tests /app/tests
WORKDIR /data
ENTRYPOINT ["python3", "/app/process.py"]
