#!/bin/bash
# Build all service Docker images and import into K3s
# Run from: distributed-vulnerable-platform/
# Usage: wsl -u root -- bash /mnt/c/.../build-and-import.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REGISTRY="dvp"
TAG="latest"

echo "=== Building DVP Docker images ==="
echo "Project dir: $PROJECT_DIR"

SERVICES=(
  "gateway"
  "auth-service"
  "user-service"
  "project-service"
  "billing-service"
  "payment-service"
  "notification-service"
  "reporting-service"
)

for svc in "${SERVICES[@]}"; do
  IMAGE="${REGISTRY}/${svc}:${TAG}"
  echo ""
  echo "--- Building ${IMAGE} ---"
  docker build -t "${IMAGE}" "${PROJECT_DIR}/${svc}"
  echo "--- Importing ${IMAGE} into K3s ---"
  docker save "${IMAGE}" | k3s ctr images import -
done

echo ""
echo "=== All images built and imported ==="
k3s ctr images list | grep "dvp/"
