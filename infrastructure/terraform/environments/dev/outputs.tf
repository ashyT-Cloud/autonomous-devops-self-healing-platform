output "vpc_id" {
  description = "ID of the Project 8 VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "availability_zones" {
  description = "Availability Zones used by the public subnets"
  value       = aws_subnet.public[*].availability_zone
}
