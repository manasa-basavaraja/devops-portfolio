#!/bin/bash

IMAGE_NAME=$1

if [ -z "$IMAGE_NAME" ]; then
  echo "Usage: ./build.sh <docker-username>"
  exit 1
fi

docker build -t $IMAGE_NAME/etl-app:latest .
docker push $IMAGE_NAME/etl-app:latest

echo "Image built and pushed"