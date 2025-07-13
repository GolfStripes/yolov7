aws --profile golfstripes ecs register-task-definition \
  --family gs-yolov7-task \
  --execution-role-arn arn:aws:iam::842676010442:role/gs-yolov7-execution-role \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu "256" \
  --memory "512" \
  --container-definitions '[
    {
      "name": "gs-yolov7",
      "image": "842676010442.dkr.ecr.us-east-1.amazonaws.com/gs-yolov7:latest",
      "essential": true,
      "environment": [
        {
          "name": "INPUT",
          "value": "s3://dev-golfstripes-ferrule-data/orders/example_order_id_12345/user_image.jpg"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/gs-yolov7",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]'

