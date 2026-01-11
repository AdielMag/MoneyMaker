# Cloud Scheduler configuration for MoneyMaker workflows
# Terraform configuration for GCP Cloud Scheduler

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "orchestrator_url" {
  description = "URL of the orchestrator Cloud Run service"
  type        = string
}

variable "discovery_cron_fake" {
  description = "Cron schedule for fake money discovery workflow"
  type        = string
  default     = "*/30 * * * *"  # Every 30 minutes
}

variable "discovery_cron_real" {
  description = "Cron schedule for real money discovery workflow"
  type        = string
  default     = "0 */2 * * *"  # Every 2 hours
}

variable "monitor_cron" {
  description = "Cron schedule for position monitoring"
  type        = string
  default     = "*/5 * * * *"  # Every 5 minutes
}

# Service account for Cloud Scheduler
resource "google_service_account" "scheduler" {
  account_id   = "moneymaker-scheduler"
  display_name = "MoneyMaker Cloud Scheduler"
  project      = var.project_id
}

# Grant invoker role to scheduler service account
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  location = var.region
  project  = var.project_id
  service  = "moneymaker-orchestrator"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Discovery workflow - Fake Money
resource "google_cloud_scheduler_job" "discovery_fake" {
  name        = "moneymaker-discovery-fake"
  description = "Trigger discovery workflow for fake money trading"
  schedule    = var.discovery_cron_fake
  project     = var.project_id
  region      = var.region
  time_zone   = "UTC"

  retry_config {
    retry_count          = 3
    min_backoff_duration = "5s"
    max_backoff_duration = "60s"
  }

  http_target {
    http_method = "POST"
    uri         = "${var.orchestrator_url}/workflow/discover"
    body        = base64encode(jsonencode({
      mode = "fake"
    }))
    headers = {
      "Content-Type" = "application/json"
    }
    
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = var.orchestrator_url
    }
  }
}

# Discovery workflow - Real Money (disabled by default)
resource "google_cloud_scheduler_job" "discovery_real" {
  name        = "moneymaker-discovery-real"
  description = "Trigger discovery workflow for real money trading"
  schedule    = var.discovery_cron_real
  project     = var.project_id
  region      = var.region
  time_zone   = "UTC"
  paused      = true  # Disabled by default

  retry_config {
    retry_count          = 3
    min_backoff_duration = "10s"
    max_backoff_duration = "120s"
  }

  http_target {
    http_method = "POST"
    uri         = "${var.orchestrator_url}/workflow/discover"
    body        = base64encode(jsonencode({
      mode = "real"
    }))
    headers = {
      "Content-Type" = "application/json"
    }
    
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = var.orchestrator_url
    }
  }
}

# Monitor workflow - Fake Money
resource "google_cloud_scheduler_job" "monitor_fake" {
  name        = "moneymaker-monitor-fake"
  description = "Trigger position monitoring for fake money"
  schedule    = var.monitor_cron
  project     = var.project_id
  region      = var.region
  time_zone   = "UTC"

  retry_config {
    retry_count          = 2
    min_backoff_duration = "5s"
    max_backoff_duration = "30s"
  }

  http_target {
    http_method = "POST"
    uri         = "${var.orchestrator_url}/workflow/monitor"
    body        = base64encode(jsonencode({
      mode = "fake"
    }))
    headers = {
      "Content-Type" = "application/json"
    }
    
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = var.orchestrator_url
    }
  }
}

# Monitor workflow - Real Money (disabled by default)
resource "google_cloud_scheduler_job" "monitor_real" {
  name        = "moneymaker-monitor-real"
  description = "Trigger position monitoring for real money"
  schedule    = var.monitor_cron
  project     = var.project_id
  region      = var.region
  time_zone   = "UTC"
  paused      = true  # Disabled by default

  retry_config {
    retry_count          = 2
    min_backoff_duration = "5s"
    max_backoff_duration = "30s"
  }

  http_target {
    http_method = "POST"
    uri         = "${var.orchestrator_url}/workflow/monitor"
    body        = base64encode(jsonencode({
      mode = "real"
    }))
    headers = {
      "Content-Type" = "application/json"
    }
    
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = var.orchestrator_url
    }
  }
}

output "scheduler_service_account" {
  value = google_service_account.scheduler.email
}

output "discovery_fake_job" {
  value = google_cloud_scheduler_job.discovery_fake.name
}

output "monitor_fake_job" {
  value = google_cloud_scheduler_job.monitor_fake.name
}
