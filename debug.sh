docker build -t yolov7 .
docker run \
  -v ~/.aws:/root/.aws \
  -e AWS_PROFILE=golfstripes \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e DATA_BUCKET=dev-golfstripes-ferrule-data \
  -e ORDER_ID=1369 \
  yolov7
