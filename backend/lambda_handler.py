"""AWS Lambda entrypoint.

Terraform configures the Lambda function with handler ``lambda_handler.handler``.
We re-export the Mangum-wrapped FastAPI app from ``app.main`` so all the
routing/config logic lives in one place.
"""

from app.main import handler  # noqa: F401  (re-exported for Lambda runtime)
