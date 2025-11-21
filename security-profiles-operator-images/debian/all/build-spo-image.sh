#!/bin/sh
#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

IMAGE=$1
IMAGE_TAG=$2
BUILD_TAG=dev-debian-stable-build
export CONTAINER_TOOL=docker

echo "=============== build script ================"
echo image: "${IMAGE}"
echo image_tag: "${IMAGE_TAG}"
pwd

if [ -z "${IMAGE_TAG}" ]; then
    echo "Image tag must be specified. build ${IMAGE} Aborting..." >&2
    exit 1
fi

build_spo_image() {
    export SPO_IMAGE="security-profiles-operator"

    echo "Building SPO image: ${SPO_IMAGE}"
    docker build -t ${SPO_IMAGE}:${BUILD_TAG} -f Dockerfile .
    if [ $? -ne 0 ]; then
        echo "SPO image build failed"
        exit 1
    fi

    docker tag ${SPO_IMAGE}:${BUILD_TAG} ${IMAGE_TAG}
    docker rmi ${SPO_IMAGE}:${BUILD_TAG}

    echo "SPO image build done"
    return 0
}

build_spo_image
