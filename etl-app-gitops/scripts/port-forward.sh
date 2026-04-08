#!/bin/bash

kubectl port-forward svc/etl-app 8080:80

echo "App running at http://localhost:8080"