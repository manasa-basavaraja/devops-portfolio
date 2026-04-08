#!/bin/bash

APP_NAME=etl-app

kubectl argo rollouts undo rollout $APP_NAME

echo "Rollback triggered"