#!/bin/sh

# Simple script to set up MinIO bucket and user
# Based on example from MinIO issues

# Format bucket name to ensure compatibility
BUCKET_NAME=$(echo "${S3_BUCKET_NAME}" | tr '[:upper:]' '[:lower:]' | tr '_' '-')

# Configure MinIO client
mc alias set myminio http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}

# Remove bucket if it exists (for clean setup)
mc rm -r --force myminio/${BUCKET_NAME} || true

# Create bucket
mc mb myminio/${BUCKET_NAME}

# Set bucket policy to allow downloads
mc anonymous set download myminio/${BUCKET_NAME}

# Create user with access and secret keys
mc admin user add myminio ${S3_ACCESS_KEY} ${S3_SECRET_KEY} || echo "User already exists"

# Create policy for the bucket
echo '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:*"],"Resource":["arn:aws:s3:::'${BUCKET_NAME}'/*","arn:aws:s3:::'${BUCKET_NAME}'"]}]}' > /tmp/policy.json

# Apply policy
mc admin policy create myminio gitingest-policy /tmp/policy.json || echo "Policy already exists"
mc admin policy attach myminio gitingest-policy --user ${S3_ACCESS_KEY}

echo "MinIO setup completed successfully"
echo "Bucket: ${BUCKET_NAME}"
echo "Access via console: http://localhost:9001"
