#!/bin/bash
# Build script for testum application

echo "Building testum-app Docker image..."

# Disable BuildKit for compatibility
export DOCKER_BUILDKIT=0

# Build the image
docker build -t testum-app:latest .

if [ $? -eq 0 ]; then
    echo "✓ Image built successfully: testum-app:latest"
    echo "You can now deploy the stack in Portainer"
else
    echo "✗ Build failed"
    exit 1
fi
