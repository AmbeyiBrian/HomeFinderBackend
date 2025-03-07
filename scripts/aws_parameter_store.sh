#!/bin/bash
set -e

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

# Function to create/update parameter
create_parameter() {
    local name=$1
    local value=$2
    local description=$3

    echo "Setting parameter $name..."
    aws ssm put-parameter \
        --name "$name" \
        --value "$value" \
        --type "SecureString" \
        --description "$description" \
        --overwrite || {
            echo "Failed to set parameter $name"
            return 1
        }
}

# Prompt for values with defaults
read -p "Enter Django Secret Key [auto-generate]: " DJANGO_SECRET_KEY
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY:-$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")}

read -p "Enter AWS Storage Bucket Name [django-app-storage]: " AWS_STORAGE_BUCKET_NAME
AWS_STORAGE_BUCKET_NAME=${AWS_STORAGE_BUCKET_NAME:-django-app-storage}

read -p "Enter Database Name [homefinder]: " DB_NAME
DB_NAME=${DB_NAME:-homefinder}

read -p "Enter Database User [homefinder_user]: " DB_USER
DB_USER=${DB_USER:-homefinder_user}

read -p "Enter Database Password: " DB_PASSWORD
if [ -z "$DB_PASSWORD" ]; then
    echo "Database password is required"
    exit 1
fi

read -p "Enter AWS Access Key ID: " AWS_ACCESS_KEY_ID
if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "AWS Access Key ID is required"
    exit 1
fi

read -p "Enter AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "AWS Secret Access Key is required"
    exit 1
fi

# Create/update parameters
echo "Creating/updating AWS Parameter Store values..."

create_parameter "/homefinder/django_secret_key" "$DJANGO_SECRET_KEY" "Django secret key for HomeFinder application"
create_parameter "/homefinder/storage_bucket_name" "$AWS_STORAGE_BUCKET_NAME" "S3 bucket for file storage"
create_parameter "/homefinder/aws_access_key_id" "$AWS_ACCESS_KEY_ID" "AWS access key ID for HomeFinder"
create_parameter "/homefinder/aws_secret_access_key" "$AWS_SECRET_ACCESS_KEY" "AWS secret access key for HomeFinder"
create_parameter "/homefinder/db_name" "$DB_NAME" "PostgreSQL database name"
create_parameter "/homefinder/db_user" "$DB_USER" "PostgreSQL database user"
create_parameter "/homefinder/db_password" "$DB_PASSWORD" "PostgreSQL database password"

echo "Parameter Store setup completed successfully!"
echo "Remember to update your CodeBuild service role to allow access to these parameters."