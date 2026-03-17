output "api_url" {
  description = "Public URL of the deployed HTTP API."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "lambda_function_name" {
  description = "Name of the deployed Lambda function (use this for CI updates)."
  value       = aws_lambda_function.api.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function."
  value       = aws_lambda_function.api.arn
}

output "s3_uploads_bucket" {
  description = "Name of the S3 bucket for raw document uploads."
  value       = aws_s3_bucket.uploads.bucket
}

output "lambda_log_group" {
  description = "CloudWatch log group for the Lambda function."
  value       = aws_cloudwatch_log_group.lambda.name
}
