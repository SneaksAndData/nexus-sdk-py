default:
    @just --list

fresh: stop up

up: start-kind-cluster \
    install-ingress-controller \
    create-ingress \
    scylla \
    dbschema \
    shards-kubeconfig \
    crd \
    algorithm \
    scheduler \
    receiver \
    supervisor \
    minio \
    wait-for-services

stop:
    kind delete cluster

start-kind-cluster:
    kind create cluster --config=integration_tests/kind.yaml

install-ingress-controller:
    kubectl apply -f https://kind.sigs.k8s.io/examples/ingress/deploy-ingress-nginx.yaml
    kubectl rollout status deployment/ingress-nginx-controller -n ingress-nginx --timeout=180s

create-ingress:
    # Create ingress rules for services
    for i in $(seq 1 30); do \
      kubectl apply -f ./integration_tests/manifests/ingress.yaml && break || \
      (echo "Retry $i/30: failed to apply ingress, retrying in 1s..." && sleep 1); \
    done; \
    if [ $i -eq 30 ]; then \
      echo "Failed to apply ingress after 30 attempts."; \
      exit 1; \
    fi

scylla:
    kubectl apply -f integration_tests/manifests/scylladb.yaml
    kubectl rollout status deployment/scylla --timeout=180s

minio:
    kubectl apply -f integration_tests/manifests/minio.yaml
    kubectl rollout status deployment/minio --timeout=180s

crd:
    helm upgrade --install nexus-crd  oci://ghcr.io/sneaksanddata/helm/nexus-crd --version v1.0.0

algorithm:
    kubectl apply -f integration_tests/manifests/hello-world-algorithm.yaml
    kubectl apply -f integration_tests/manifests/hello-world-workgroup.yaml
    kubectl apply -f integration_tests/manifests/nexus-algorithm-sa.yaml

shards-kubeconfig:
    kind get kubeconfig \
      | yq -o=json '.clusters[].cluster.server = "https://kubernetes.default.svc.cluster.local"' \
      | kubectl create secret generic nexus-shards --from-file=kind-nexus-shard-0.kubeconfig=/dev/stdin --type=Opaque --dry-run=client -o yaml \
      | kubectl apply -f -

scheduler:
    helm upgrade --install nexus oci://ghcr.io/sneaksanddata/helm/nexus --version v1.1.12  \
      --set scheduler.replicas=1 \
      --set scheduler.config.cqlStore.type=scylla \
      --set scheduler.config.cqlStore.secretRefEnabled=true \
      --set 'extraEnvFrom[0].secretRef.name=cassandra-credentials' \
      --set 'scheduler.config.cqlStore.secretName=cassandra-credentials' \
      --set 'scheduler.config.s3Buffer.s3Credentials.secretRefEnabled=true' \
      --set 'scheduler.config.s3Buffer.s3Credentials.secretName=minio-credentials' \
      --set 'scheduler.config.s3Buffer.processing.payloadStoragePath=s3a://nexus'


receiver:
    helm upgrade --install nexus-receiver oci://ghcr.io/sneaksanddata/helm/nexus-receiver --version v1.1.4  \
      --set receiver.replicas=1 \
      --set receiver.config.cqlStore.type=scylla \
      --set receiver.config.cqlStore.secretRefEnabled=true \
      --set 'extraEnvFrom[0].secretRef.name=cassandra-credentials' \
      --set receiver.config.cqlStore.secretName="cassandra-credentials"

supervisor:
    helm upgrade --install nexus-supervisor oci://ghcr.io/sneaksanddata/helm/nexus-supervisor --version v0.1.6  \
      --set 'extraEnvFrom[0].secretRef.name=cassandra-credentials' \
      --set 'supervisor.replicas=1' \
      --set 'supervisor.config.cqlStore.type=scylla' \
      --set 'supervisor.config.cqlStore.secretRefEnabled=true' \
      --set 'supervisor.config.cqlStore.secretName=cassandra-credentials' \
      --set 'supervisor.config.resourceNamespace=default'

wait-for-services:
    kubectl rollout status deployment/nexus --timeout=180s
    kubectl rollout status deployment/nexus-receiver --timeout=180s
    kubectl rollout status deployment/nexus-supervisor --timeout=180s

dbschema:
  docker run --rm -v $(pwd)/integration_tests/storage:/opt/storage --network=host --entrypoint /opt/storage/prepare-scylla.sh scylladb/scylla:5.0.1