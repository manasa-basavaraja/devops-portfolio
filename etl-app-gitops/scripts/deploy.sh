#!/bin/bash

ENV=$1

if [ -z "$ENV" ]; then
  echo "Usage: ./deploy.sh <dev|staging|prod>"
  exit 1
fi

git add .
git commit -m "Deploying to $ENV"
git push origin main

echo "Changes pushed. ArgoCD will sync automatically."