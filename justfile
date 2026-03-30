default:
    @just --list

fresh: stop up

up: start-kind-cluster scylla nesus-crd

start-kind-cluster:
    kind create cluster

stop:
    kind delete cluster

scylla:
    kubectl apply -f integration_tests/manifests/scylladb.yaml
    kubectl rollout status deployment/scylla --timeout=180s

nesus-crd:
    helm install oci://ghcr.io/sneaksanddata/helm/nexus-crd --version v1.0.0 --generate-name

shcards-kubeconfig:
    kind get kubeconfig \
      | yq -o=json \
      | kubectl create secret generic nexus-shards --from-file=kubeconfig=/dev/stdin --type=Opaque --dry-run=client -o yaml \
      | kubectl apply -f -

nexus:
    helm upgrade --install nexus oci://ghcr.io/sneaksanddata/helm/nexus --version v1.1.12  \
      --set scheduler.replicas=1 \
      --set scheduler.config.cqlStore.type=scylla \
      --set scheduler.config.cqlStore.secretRefEnabled=true \
      --set 'extraEnvFrom[0].secretRef.name=cassandra-credentials' \
      --set 'scheduler.config.s3Buffer.s3Credentials.secretRefEnabled=false' \
      --set scheduler.config.cqlStore.secretName="cassandra-credentials"


