# Stage 1: Builder
FROM ubuntu:22.04 AS builder
LABEL stage="builder"

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /tmp/yolov7

# Copy the large, stable file first for better caching
COPY best.pt best.pt

RUN apt-get update && \
    apt-get install -y python3-pip git wget libgl1-mesa-dev libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages into a directory
RUN python3 -m pip install --upgrade pip
RUN mkdir -p /install
RUN python3 -m pip install --target=/install \
    onnxruntime opencv-python-headless pillow pyyaml filterpy

# Clone repo into a subdir (avoid conflict with best.pt)
WORKDIR /tmp
RUN git clone https://github.com/GolfStripes/yolov7.git yolov7-repo && \
    cd yolov7-repo && git checkout jgrubb/dev

# Copy code from cloned repo into working directory
RUN cp -r /tmp/yolov7-repo/* /tmp/yolov7/

# Install requirements from the repo
WORKDIR /tmp/yolov7
RUN python3 -m pip install --target=/install -r requirements.txt

# Stage 2: Runtime
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y python3 wget libgl1-mesa-dev libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local/lib/python3.10/dist-packages

# Copy full app directory
WORKDIR /usr/src/yolov7
COPY --from=builder /tmp/yolov7 /usr/src/yolov7

# Add entrypoint
COPY main.py main.py
COPY entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["python3", "main.py"]
