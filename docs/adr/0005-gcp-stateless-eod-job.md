# 5. GCP: a stateless end-of-day job next to a read API

Status: accepted

The posting's platform is Google Cloud. Vendor drops land in a GCS bucket (object creation time is the arrival
time). A Cloud Run job, started by Cloud Scheduler at 18:30 and again at 08:00 Frankfurt time, replays the quarter
from the landed files, records closes and restatements not yet stored in Cloud SQL (PostgreSQL 16) and relays the
outbox to Pub/Sub. Replaying keeps the job stateless and its output a function of the files and the desk's
answers. The read API and dashboard run as a Cloud Run service. One image serves both, configured only through the
environment; each workload has its own service account with only the roles it uses.
