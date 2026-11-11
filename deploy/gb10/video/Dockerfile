# Build on GB10, or explicitly select --platform linux/arm64.
ARG BASE_IMAGE=nvcr.io/nvidia/pytorch:25.11-py3@sha256:4a85d8cf6fb3a943280960b8948cf4e9b6eca77b4414c68c9b2c7bb863f79b70
FROM ${BASE_IMAGE}
USER root
ARG APT_MIRROR
RUN if [ -n "$APT_MIRROR" ]; then sed -i "s|http://ports.ubuntu.com/ubuntu-ports|$APT_MIRROR|g" /etc/apt/sources.list.d/ubuntu.sources; fi
RUN test "$(uname -m)" = aarch64 \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/duix-video-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/duix-video-requirements.txt
WORKDIR /opt/duix/video
COPY *.py *.json ./
ENV PYTHONPATH=/opt/duix/video PYTHONUNBUFFERED=1 \
    NVIDIA_TF32_OVERRIDE=0 TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=0 \
    OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_MAX_THREADS=4 NUMEXPR_NUM_THREADS=4
EXPOSE 8383
HEALTHCHECK --start-period=90s --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8383/health',timeout=5)"
CMD ["python", "full_service.py", "--root", "/models/video", "--full-root", "/models/video", "--data-root", "/data"]
