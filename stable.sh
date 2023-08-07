#!/bin/bash

set -Eeuo pipefail

trap fail ERR

fail() {
    echo "Failed"
}

docker buildx use multiarch
docker buildx build . --platform linux/arm/v7 --platform linux/amd64 --tag d3v01d/sawnee-reader:stable --push
