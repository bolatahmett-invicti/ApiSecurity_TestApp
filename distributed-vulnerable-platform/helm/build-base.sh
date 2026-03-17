#!/bin/bash
# Build the base Python image with all dependencies pre-installed
# and import it into K3s containerd.
#
# Usage (from WSL, as root):
#   cd /mnt/c/Users/AhmetBolat/Projects/PoC/Claude/ApiSecurity_TestApp/distributed-vulnerable-platform/helm
#   bash build-base.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE="dvp-base:latest"
TARBALL="/tmp/dvp-base.tar"

echo "=== Building ${IMAGE} ==="

# Use k3s's bundled buildkit/containerd to build
# First check if we can use nerdctl, otherwise use a manual approach
if command -v nerdctl &>/dev/null; then
    nerdctl build -t "${IMAGE}" "${SCRIPT_DIR}/base-image"
else
    echo "No nerdctl found. Using ctr + python base image approach..."

    # Pull base python image if not present
    k3s ctr images pull docker.io/library/python:3.12-slim 2>/dev/null || true

    # Create a temporary container to install deps
    CONTAINER_ID=$(k3s ctr containers create docker.io/library/python:3.12-slim dvp-builder 2>&1 | tail -1 || true)

    # Alternative: just use python:3.12-slim directly and install deps via init container
    echo ""
    echo "K3s does not have a native image builder."
    echo "Using python:3.12-slim as base with initContainer for dependency installation."
    echo ""
    echo "Pulling python:3.12-slim into K3s..."
    k3s ctr images pull docker.io/library/python:3.12-slim
    echo ""
    echo "=== Base image ready ==="
    echo "Services will use python:3.12-slim + initContainer to install deps."
fi
