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
RUN echo 1
WORKDIR /usr/src
RUN git clone https://github.com/GolfStripes/yolov7.git
WORKDIR /usr/src/yolov7
RUN git checkout jgrubb/dev
RUN pip install -r requirements.txt
COPY best.pt best.pt
COPY main.py main.py
#CMD ["python3", "main.py"]
COPY entrypoint.sh /usr/src/yolov7/entrypoint.sh
ENTRYPOINT ["/usr/src/yolov7/entrypoint.sh"]
