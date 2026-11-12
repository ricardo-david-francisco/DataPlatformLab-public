# Deploy: Docker and Kubernetes

The pipeline is one image (`Dockerfile`: multi-stage, non-root) whose entry point is `./run.sh`. On Kubernetes, a
**CronJob** runs it every business day at 02:00 UTC (no overlapping runs, two retries), and a **Job** runs it
once on demand.

```bash
docker build -f deploy/Dockerfile -t dataplatformlab:latest .
kind create cluster --name dpl && kind load docker-image dataplatformlab:latest --name dpl
kubectl apply -k deploy/k8s
kubectl -n post-trade logs job/post-trade-once -f
```

For Snowflake, the key would come from a Kubernetes Secret mounted as a file, and the account settings from a
ConfigMap; the image is the same.
