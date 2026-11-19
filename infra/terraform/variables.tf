variable "project" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Cloud SQL and the bucket"
  type        = string
  default     = "europe-west3" # Frankfurt
}

variable "image" {
  description = "Container image built from the Dockerfile, e.g. europe-west3-docker.pkg.dev/<project>/imdh/hub:<sha>"
  type        = string
}

variable "close_schedule" {
  description = "When the end-of-day job publishes the close (cron, Europe/Berlin)"
  type        = string
  default     = "30 18 * * 1-5"
}

variable "restate_schedule" {
  description = "When the job runs again to restate yesterday from late files (cron, Europe/Berlin)"
  type        = string
  default     = "0 8 * * 1-5"
}
