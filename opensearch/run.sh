#!/bin/bash

# Remove existing container if it exists
docker rm -f opensearch-instance 2>/dev/null || true

# Build the OpenSearch Docker image
docker build -t opensearch-custom:latest .

# Run the OpenSearch container
docker run -d \
    --name opensearch-instance \
    -p 9200:9200 \
    -p 9600:9600 \
    opensearch-custom:latest
