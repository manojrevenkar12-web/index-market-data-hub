# Running on Google Cloud

`infra/terraform` creates, in one region (default `europe-west3`, Frankfurt):

| Resource | Purpose |
|---|---|
| GCS bucket `<project>-imdh-drops` | vendor drops, reference, guideline and FX files; versioned; public access prevented |
| Cloud SQL PostgreSQL 16 (regional, point-in-time recovery) | the bitemporal golden source and the outbox |
| Secret Manager `imdh-database-url` | the connection URL, read by both workloads |
| Cloud Run job `imdh-eod` | `python -m imdh.service.eod`: land, replay, record, relay |
| Cloud Scheduler `imdh-eod-close`, `imdh-eod-restate` | 18:30 and 08:00 Europe/Berlin, weekdays |
| Pub/Sub `imdh-publications` + ordered subscription + dead-letter topic | index publications and corrections |
| Cloud Run service `imdh-api` | the read API, stream and dashboard |
| Artifact Registry `imdh` | the image |

```bash
docker build -t europe-west3-docker.pkg.dev/$PROJECT/imdh/hub:$SHA .
docker push europe-west3-docker.pkg.dev/$PROJECT/imdh/hub:$SHA
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply -var project=$PROJECT -var image=europe-west3-docker.pkg.dev/$PROJECT/imdh/hub:$SHA
```

CI checks `terraform fmt` and `terraform validate` and builds the image. Nothing in this repository has been applied
to a real project.
