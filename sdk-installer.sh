#!/usr/bin/env bash

set -euo pipefail

cext_version=$(cat nexus_client_sdk/.extensions/cext_version)
arch=$(uname -m)
os=$(uname -s)

# Release assets use Go's naming (amd64/arm64), not uname's (x86_64/aarch64).
case "$arch" in
  x86_64 | amd64) arch="amd64" ;;
  aarch64 | arm64) arch="arm64" ;;
  *) echo "Unsupported architecture: $arch" >&2 && exit 1 ;;
esac

case "$os" in
  Darwin) suffix="darwin_$arch" ;;
  Linux) suffix="linux_$arch" ;;
  *) echo "Unsupported OS: $os" >&2 && exit 1 ;;
esac

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

curl -fsSL "https://github.com/SneaksAndData/nexus-sdk-go/releases/download/v$cext_version/nexus_sdk_$suffix.tar.gz" \
  -o "$workdir/nexus_sdk_$suffix.tar.gz"
tar -xzf "$workdir/nexus_sdk_$suffix.tar.gz" -C "$workdir"
mv "$workdir/dist/nexus_sdk_$suffix.so" nexus_client_sdk/.extensions/nexus_sdk.so

echo "Installed nexus_sdk.so ($suffix, v$cext_version)"
