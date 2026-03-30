default:
    @just --list

fresh: stop up

up: start-kind-cluster

start-kind-cluster:
    kind create cluster

stop:
    kind delete cluster

scylla:
    kubectl apply -f integration_tests/manifests/scylladb.yaml
    kubectl rollout status deployment/scylla --timeout=180s
