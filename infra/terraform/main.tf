# ╔══════════════════════════════════════════════════════════╗
# ║   Terraform — AWS DevOps Infrastructure                  ║
# ║   ECR (images Docker) + EC2 (déploiement) + S3 (logs)   ║
# ╚══════════════════════════════════════════════════════════╝

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "YOUR-TERRAFORM-STATE-BUCKET"
    key    = "iot-platform/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ────────────────────────────────────────────────
variable "aws_region"    { default = "us-east-1" }
variable "project_name"  { default = "iot-streaming" }
variable "ec2_key_pair"  { description = "Nom de ta clé SSH AWS" }

locals {
  tags = {
    Project     = var.project_name
    Environment = "student"
    ManagedBy   = "terraform"
  }
}

# ── ECR Repositories ─────────────────────────────────────────
resource "aws_ecr_repository" "services" {
  for_each             = toset(["data-generator", "kafka-producer", "spark-processor"])
  name                 = "${var.project_name}/${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration { scan_on_push = true }

  lifecycle_policy {
    policy = jsonencode({
      rules = [{
        rulePriority = 1
        description  = "Garder les 5 dernières images"
        selection     = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
        action        = { type = "expire" }
      }]
    })
  }

  tags = local.tags
}

# ── S3 Bucket (logs + artefacts CI/CD) ───────────────────────
resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-artifacts-${data.aws_caller_identity.current.account_id}"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    id     = "expire-old-logs"
    status = "Enabled"
    expiration { days = 30 }
  }
}

# ── IAM Role EC2 ──────────────────────────────────────────────
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "ec2_ecr_s3" {
  name   = "ecr-s3-access"
  role   = aws_iam_role.ec2_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken", "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-profile"
  role = aws_iam_role.ec2_role.name
}

# ── Security Group ────────────────────────────────────────────
resource "aws_security_group" "iot_platform" {
  name        = "${var.project_name}-sg"
  description = "IoT Platform — ports applicatifs"
  tags        = local.tags

  ingress {
    description = "SSH"
    from_port = 22; to_port = 22; protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  dynamic "ingress" {
    for_each = [8080, 8081, 8085, 8090, 9090, 3000, 5000]
    content {
      description = "App port ${ingress.value}"
      from_port = ingress.value; to_port = ingress.value; protocol = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }
  egress {
    from_port = 0; to_port = 0; protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── EC2 Instance ──────────────────────────────────────────────
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter { name = "name";          values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"] }
  filter { name = "virtualization-type"; values = ["hvm"] }
}

data "aws_caller_identity" "current" {}

resource "aws_instance" "iot_platform" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.large"   # 2 vCPU, 8 GB RAM — suffisant pour la stack
  key_name               = var.ec2_key_pair
  vpc_security_group_ids = [aws_security_group.iot_platform.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  root_block_device { volume_size = 30; volume_type = "gp3" }

  user_data = templatefile("${path.module}/userdata.sh", {
    aws_region   = var.aws_region
    project_name = var.project_name
    s3_bucket    = aws_s3_bucket.artifacts.id
  })

  tags = merge(local.tags, { Name = "${var.project_name}-server" })
}

# ── Outputs ───────────────────────────────────────────────────
output "ec2_public_ip"    { value = aws_instance.iot_platform.public_ip }
output "ec2_public_dns"   { value = aws_instance.iot_platform.public_dns }
output "s3_bucket"        { value = aws_s3_bucket.artifacts.id }
output "ecr_repositories" {
  value = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}
output "ssh_command" {
  value = "ssh -i ~/.ssh/${var.ec2_key_pair}.pem ubuntu@${aws_instance.iot_platform.public_ip}"
}
