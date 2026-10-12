variable "aws_region" {
  description = "AWS region for Project 8 infrastructure"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project  identifier used for resource tagging"
  type        = string
  default     = "project-8-self-healing"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR range for the Project 8 VPC"
  type        = string
  default     = "10.80.0.0/16"
}

