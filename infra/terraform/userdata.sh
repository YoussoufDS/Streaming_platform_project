#!/bin/bash
set -e

# Installer Docker + Docker Compose
apt-get update -y
apt-get install -y docker.io docker-compose-plugin awscli git curl

# Activer Docker
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

# Login ECR
aws ecr get-login-password --region ${aws_region} | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.${aws_region}.amazonaws.com

# Cloner le repo (remplacer par ton URL GitHub)
git clone https://github.com/YOUR_USERNAME/iot-streaming-platform.git /app
cd /app

# Lancer la stack
docker compose up -d

# Log de démarrage
echo "IoT Platform démarrée — $(date)" | aws s3 cp - s3://${s3_bucket}/logs/startup.log
