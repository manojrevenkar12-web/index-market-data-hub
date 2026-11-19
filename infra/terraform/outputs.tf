output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "drops_bucket" {
  value = google_storage_bucket.drops.name
}

output "publications_topic" {
  value = google_pubsub_topic.publications.id
}
