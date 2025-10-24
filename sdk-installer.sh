#!/usr/bin/env sh

cext_version=$(cat nexus_client_sdk/.extensions/cext_version)
arch=$(uname -m)
os=$(uname -s)

if [[ "$os" == "Darwin" ]]; then
  suffix="darwin_$arch"
else
  suffix="linux_$arch"
fi

curl -L https://github.com/SneaksAndData/nexus-sdk-go/releases/download/v$cext_version/nexus_sdk_$suffix.tar.gz > nexus_sdk_$suffix.tar.gz
mkdir cext && tar -xvzf nexus_sdk_$suffix.tar.gz -C cext && mv cext/dist/nexus_sdk_$suffix.so nexus_client_sdk/.extensions/nexus_sdk.so
