FROM debian:13-slim
# libopencore-amrwb0: AMR-WB-Decoder für decode_amr() in process.py.
# FFmpegs nativer amrwb-Decoder verwirft SID-Frames und ist dafür ungeeignet.
RUN apt-get update && apt-get install -y --no-install-recommends python3 ffmpeg libvo-amrwbenc0 libopencore-amrwb0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY process.py /app/process.py
COPY tests /app/tests
WORKDIR /data
ENTRYPOINT ["python3", "/app/process.py"]
