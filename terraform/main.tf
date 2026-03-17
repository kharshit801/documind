################################################################################
# DocuMind — AWS infra
#
# Provisions:
#   * S3 bucket for raw uploads (documind-uploads by default)
#   * IAM role + policy for Lambda (S3 read/write + CloudWatch logs)
#   * Lambda function (backend/ FastAPI via Mangum)
#   * API Gateway HTTP API with ANY /{proxy+} -> Lambda integration
#
# Notes:
#   * The Pinecone index is NOT managed here (Terraform-managed Pinecone is
#     out of scope for this stack). Create it once via the Pinecone console
#     or their API: serverless, dimension 1536, metric cosine.
#   * The Lambda zip is built from ../backend if `lambda_zip_path` is not set.
#     CI/CD typically prebuilds the zip and passes its path explicitly.
################################################################################

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  lambda_env_vars = {
    OPENAI_API_KEY       = var.openai_api_key
    EMBEDDING_MODEL      = var.embedding_model
    LLM_MODEL            = var.llm_model
    PINECONE_API_KEY     = var.pinecone_api_key
    PINECONE_INDEX_NAME  = var.pinecone_index_name
    PINECONE_ENVIRONMENT = var.pinecone_environment
    APP_ENV              = "production"
    MAX_FILE_SIZE_MB     = tostring(var.max_file_size_mb)
    CHUNK_SIZE           = tostring(var.chunk_size)
    CHUNK_OVERLAP        = tostring(var.chunk_overlap)
    TOP_K_RESULTS        = tostring(var.top_k_results)
    AWS_S3_BUCKET_NAME   = var.s3_bucket_name
    CORS_ALLOW_ORIGINS   = join(",", var.cors_allow_origins)
  }
}

################################################################################
# S3 — uploads bucket
################################################################################

resource "aws_s3_bucket" "uploads" {
  bucket = var.s3_bucket_name
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

################################################################################
# IAM — Lambda execution role
################################################################################

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${local.name_prefix}-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_s3" {
  statement {
    sid    = "S3ObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.uploads.arn,
      "${aws_s3_bucket.uploads.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_s3" {
  name   = "${local.name_prefix}-lambda-s3"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_s3.json
}

################################################################################
# Lambda deployment package
################################################################################

# If the caller didn't pass a prebuilt zip path, archive ../backend on the fly.
# In CI/CD we typically pass `lambda_zip_path` because we need to `pip install`
# dependencies into the package first.
data "archive_file" "lambda_zip" {
  count       = var.lambda_zip_path == "" ? 1 : 0
  type        = "zip"
  source_dir  = "${path.module}/../backend"
  output_path = "${path.module}/.terraform-build/lambda_package.zip"
  excludes = [
    "tests",
    "Dockerfile",
    ".pytest_cache",
    "__pycache__",
    ".flake8",
  ]
}

locals {
  lambda_zip_resolved = (
    var.lambda_zip_path != ""
    ? var.lambda_zip_path
    : data.archive_file.lambda_zip[0].output_path
  )
  lambda_zip_hash = (
    var.lambda_zip_path != ""
    ? filebase64sha256(var.lambda_zip_path)
    : data.archive_file.lambda_zip[0].output_base64sha256
  )
}

################################################################################
# Lambda function
################################################################################

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_lambda_function" "api" {
  function_name    = local.name_prefix
  role             = aws_iam_role.lambda_exec.arn
  handler          = "lambda_handler.handler"
  runtime          = "python3.11"
  memory_size      = var.lambda_memory_mb
  timeout          = var.lambda_timeout_seconds
  filename         = local.lambda_zip_resolved
  source_code_hash = local.lambda_zip_hash

  environment {
    variables = local.lambda_env_vars
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_cloudwatch_log_group.lambda,
  ]

  tags = local.common_tags
}

################################################################################
# API Gateway (HTTP API)
################################################################################

resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name_prefix}-http-api"
  protocol_type = "HTTP"
  description   = "DocuMind public HTTP API"

  cors_configuration {
    allow_origins = var.cors_allow_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 3600
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "root" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  tags        = local.common_tags
}

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
