variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used as a prefix for AWS resources."
  type        = string
  default     = "documind"
}

variable "environment" {
  description = "Deployment environment label (dev | staging | prod)."
  type        = string
  default     = "prod"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for uploaded documents. Must be globally unique."
  type        = string
  default     = "documind-uploads"
}

variable "lambda_memory_mb" {
  description = "Memory allocated to the Lambda function (MB)."
  type        = number
  default     = 512
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 30
}

variable "lambda_zip_path" {
  description = "Path to the prebuilt Lambda deployment package zip. If empty, Terraform builds one from ../backend."
  type        = string
  default     = ""
}

variable "cors_allow_origins" {
  description = "Allowed origins for the API Gateway CORS config. Use ['*'] for fully public."
  type        = list(string)
  default     = ["*"]
}

# --- Application secrets / env vars (passed to Lambda) ---------------------
# These map 1:1 to backend/app/config.py settings. Treat them as sensitive in
# CI/CD: prefer providing them via TF_VAR_* environment variables sourced from
# GitHub Actions secrets rather than committing values.

variable "openai_api_key" {
  description = "OpenAI API key."
  type        = string
  sensitive   = true
}

variable "embedding_model" {
  description = "OpenAI embedding model name."
  type        = string
  default     = "text-embedding-3-small"
}

variable "llm_model" {
  description = "OpenAI chat model name."
  type        = string
  default     = "gpt-4o-mini"
}

variable "pinecone_api_key" {
  description = "Pinecone API key."
  type        = string
  sensitive   = true
}

variable "pinecone_index_name" {
  description = "Pinecone index name (must already exist)."
  type        = string
  default     = "documind"
}

variable "pinecone_environment" {
  description = "Pinecone environment / region label."
  type        = string
  default     = "us-east-1-aws"
}

variable "max_file_size_mb" {
  description = "Max allowed upload size in MB."
  type        = number
  default     = 20
}

variable "chunk_size" {
  description = "Text chunk size used by the splitter."
  type        = number
  default     = 500
}

variable "chunk_overlap" {
  description = "Text chunk overlap used by the splitter."
  type        = number
  default     = 50
}

variable "top_k_results" {
  description = "Default number of vector matches returned by retrieval."
  type        = number
  default     = 5
}
