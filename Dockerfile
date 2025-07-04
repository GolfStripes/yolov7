FROM ubuntu:22.04
USER root

LABEL version="1.0"
LABEL description="yolov7-onnx"

RUN apt-get update
RUN apt-get -y install pip
RUN apt-get -y install libgl1-mesa-dev && apt-get -y install libglib2.0-0 git
RUN apt update && apt install -y wget python3-pip
RUN pip install -U pip
RUN pip install onnxruntime opencv-python-headless pillow pyyaml filterpy
WORKDIR /usr/src
RUN git clone https://github.com/GolfStripes/yolov7.git
RUN git checkout jgrubb/dev
WORKDIR /usr/src/yolov7
RUN pip install -r requirements.txt
COPY entrypoint.sh /entrypoint.sh
COPY models/experimental.py models/experimental.py
COPY data/golfstripes.yaml data/golfstripes.yaml
COPY cfg/training/yolov7-gs.yaml cfg/training/yolov7-gs.yaml
COPY utils/datasets.py utils/datasets.py
COPY utils/loss.py utils/loss.py
COPY utils/general.py utils/general.py
COPY train.py train.py

CMD ["python3", "main.py"]