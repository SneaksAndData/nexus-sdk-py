#!/usr/bin/env bash

# Wait for cqlsh to be ready by running 'describe keyspaces', retry max 30 times
echo "Waiting for ScyllaDB to be available via cqlsh..."
max_retries=30
attempt=1
until cqlsh localhost -e "DESCRIBE KEYSPACES;" >/dev/null 2>&1; do
  if (( attempt >= max_retries )); then
    echo "cqlsh did not become available after $max_retries attempts."
    exit 1
  fi
  sleep 1
  ((attempt++))
done
echo "cqlsh is available."

cqlsh localhost -e "CREATE KEYSPACE nexus WITH replication = { 'class': 'SimpleStrategy', 'replication_factor': 1 };"

echo 'Applying checkpoints table'

cqlsh localhost -f /opt/storage/checkpoints.cql

echo 'Checking table'

cqlsh localhost -e 'SELECT * FROM nexus.checkpoints'

echo 'Applying submission_buffer table'

cqlsh localhost -f /opt/storage/submission_buffer.cql

echo 'Checking table'

cqlsh localhost -e 'SELECT * FROM nexus.submission_buffer'
