# Stage 1: Builder
FROM ubuntu:22.04 as builder
LABEL stage="builder"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y python3-pip git wget libgl1-mesa-dev libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages into a directory
RUN python3 -m pip install --upgrade pip
RUN mkdir -p /install
RUN python3 -m pip install --target=/install \
    onnxruntime opencv-python-headless pillow pyyaml filterpy

# Clone repo and install additional requirements
WORKDIR /tmp/yolov7
RUN git clone https://github.com/GolfStripes/yolov7.git . && \
    git checkout jgrubb/dev

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

# Copy your app
WORKDIR /usr/src/yolov7
COPY --from=builder /tmp/yolov7 /usr/src/yolov7
COPY best.pt best.pt
COPY main.py main.py
COPY entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["python3", "main.py"]
#ENTRYPOINT ["./entrypoint.sh"]
