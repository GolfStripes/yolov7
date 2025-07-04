docker build -t yolov7 .
docker run \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_PROFILE=golfstripes \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e INPUT=s3://dev-golfstripes-ferrule-data/v2/test/dan_ferrule.jpg \
  yolov7
