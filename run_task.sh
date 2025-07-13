aws --profile golfstripes ecs run-task \
  --cluster dev-disco-cluster \
  --launch-type FARGATE \
  --task-definition gs-yolov7-task \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0ee1f5e1774db3596,subnet-0447d60384ef1ce0c],securityGroups=[sg-0fa64bf14d84b48f4],assignPublicIp=ENABLED}"
