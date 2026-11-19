locals {
  services = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "artifactregistry.googleapis.com",
  ]
  db_url = "postgresql+psycopg://imdh:${random_password.db.result}@/imdh?host=/cloudsql/${google_sql_database_instance.hub.connection_name}"
}

resource "google_project_service" "apis" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "imdh"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# Vendor drops land here (SFTP-to-GCS or vendor push). Object creation time is the arrival time the hub uses.
resource "google_storage_bucket" "drops" {
  name                        = "${var.project}-imdh-drops"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning {
    enabled = true
  }
  lifecycle_rule {
    condition {
      age = 400
    }
    action {
      type = "Delete"
    }
  }
}

# Publications: ordered per index so a correction never overtakes the close it corrects.
resource "google_pubsub_topic" "publications" {
  name       = "imdh-publications"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "dead_letter" {
  name = "imdh-publications-dead-letter"
}

resource "google_pubsub_subscription" "distribution" {
  name                    = "imdh-distribution"
  topic                   = google_pubsub_topic.publications.id
  enable_message_ordering = true
  ack_deadline_seconds    = 30
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 10
  }
}

resource "google_sql_database_instance" "hub" {
  name                = "imdh"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = true
  settings {
    tier              = "db-custom-1-3840"
    availability_type = "REGIONAL"
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "hub" {
  name     = "imdh"
  instance = google_sql_database_instance.hub.name
}

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "google_sql_user" "hub" {
  name     = "imdh"
  instance = google_sql_database_instance.hub.name
  password = random_password.db.result
}

resource "google_secret_manager_secret" "db_url" {
  secret_id = "imdh-database-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_url" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = local.db_url
}

# One service account per workload, each with only what it uses.
resource "google_service_account" "api" {
  account_id   = "imdh-api"
  display_name = "imdh read API"
}

resource "google_service_account" "job" {
  account_id   = "imdh-eod"
  display_name = "imdh end-of-day job"
}

resource "google_service_account" "scheduler" {
  account_id   = "imdh-scheduler"
  display_name = "imdh scheduler"
}

resource "google_project_iam_member" "sql_client" {
  for_each = { api = google_service_account.api.email, job = google_service_account.job.email }
  project  = var.project
  role     = "roles/cloudsql.client"
  member   = "serviceAccount:${each.value}"
}

resource "google_secret_manager_secret_iam_member" "db_url" {
  for_each  = { api = google_service_account.api.email, job = google_service_account.job.email }
  secret_id = google_secret_manager_secret.db_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}

resource "google_storage_bucket_iam_member" "job_reads_drops" {
  bucket = google_storage_bucket.drops.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.job.email}"
}

resource "google_pubsub_topic_iam_member" "job_publishes" {
  topic  = google_pubsub_topic.publications.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.job.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "imdh-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.api.email
    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.hub.connection_name]
      }
    }
    containers {
      image = var.image
      env {
        name = "IMDH_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      startup_probe {
        http_get {
          path = "/api/health"
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.db_url]
}

resource "google_cloud_run_v2_job" "eod" {
  name     = "imdh-eod"
  location = var.region
  template {
    template {
      service_account = google_service_account.job.email
      max_retries     = 2
      timeout         = "900s"
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.hub.connection_name]
        }
      }
      containers {
        image   = var.image
        command = ["python", "-m", "imdh.service.eod"]
        env {
          name  = "IMDH_DROPS"
          value = "gs://${google_storage_bucket.drops.name}"
        }
        env {
          name  = "IMDH_PUBSUB_TOPIC"
          value = google_pubsub_topic.publications.id
        }
        env {
          name = "IMDH_DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db_url.secret_id
              version = "latest"
            }
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.db_url]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_eod" {
  name     = google_cloud_run_v2_job.eod.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "eod" {
  for_each = {
    close   = var.close_schedule
    restate = var.restate_schedule
  }
  name      = "imdh-eod-${each.key}"
  schedule  = each.value
  time_zone = "Europe/Berlin"
  region    = var.region
  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project}/jobs/${google_cloud_run_v2_job.eod.name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}
