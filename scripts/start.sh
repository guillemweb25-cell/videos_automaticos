#!/bin/bash

# Fix for "client version 1.53 is too new. Maximum supported API version is 1.41"
export DOCKER_API_VERSION=1.41

echo "Starting Docker services with DOCKER_API_VERSION=1.41..."
#docker compose up -d --build
docker compose up -d
