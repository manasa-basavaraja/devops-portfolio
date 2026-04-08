#!/bin/bash

URL=$1

if [ -z "$URL" ]; then
  echo "Usage: ./load-test.sh <url>"
  exit 1
fi

for i in {1..100}; do
  curl -s $URL > /dev/null &
done

echo "Load test triggered"