#!/bin/bash

set -Eeuo pipefail

trap fail ERR

fail() {
    echo "Failed"
}

docker buildx use multiarch
docker buildx build --platform linux/arm/v7 --platform linux/amd64 . -t d3v01d/sawnee-reader:latest --push
