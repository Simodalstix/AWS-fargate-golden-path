import os
import json
import time
import uuid
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

import boto3
import structlog
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from aws_xray_sdk.fastapi import XRayMiddleware

# Patch AWS SDK calls for X-Ray tracing
patch_all()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Golden Path Sample Application",
    description="Sample FastAPI application for ECS Fargate Golden Path",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add X-Ray middleware
app.add_middleware(XRayMiddleware, name="golden-path-app")

# Global variables
db_connection = None
ssm_client = boto3.client("ssm")
secrets_client = boto3.client("secretsmanager")

# Configuration
DB_SECRET_ARN = os.getenv("DB_SECRET_ARN", "")
PARAM_FAILURE_MODE = os.getenv("PARAM_FAILURE_MODE", "/golden/failure_mode")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


class FailureMode:
    """Manages application failure modes for break/fix lab"""

    @staticmethod
    def get_current_mode() -> str:
        """Get current failure mode from SSM Parameter Store"""
        try:
            if not PARAM_FAILURE_MODE:
                return "none"

            response = ssm_client.get_parameter(Name=PARAM_FAILURE_MODE)
            return response["Parameter"]["Value"]
        except Exception as e:
            logger.warning("Failed to get failure mode parameter", error=str(e))
            return "none"

    @staticmethod
    def should_return_500() -> bool:
        """Check if should return 500 status code"""
        return FailureMode.get_current_mode() == "return_500"

    @staticmethod
    def should_leak_connections() -> bool:
        """Check if should leak database connections"""
        return FailureMode.get_current_mode() == "connection_leak"


class DatabaseManager:
    """Manages database connections and operations"""

    @staticmethod
    def get_db_credentials() -> Dict[str, str]:
        """Get database credentials from Secrets Manager"""
        try:
            if not DB_SECRET_ARN:
                return {
                    "host": "localhost",
                    "username": "test",
                    "password": "test",
                    "database": "test",
                }

            response = secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
            secret = json.loads(response["SecretString"])
            return secret
        except Exception as e:
            logger.error("Failed to get database credentials", error=str(e))
            raise HTTPException(status_code=500, detail="Database configuration error")

    @staticmethod
    def get_connection():
        """Get database connection (simplified for demo)"""
        global db_connection

        if db_connection is None:
            credentials = DatabaseManager.get_db_credentials()
            # In a real application, you would establish actual database connection here
            # For demo purposes, we'll simulate it
            db_connection = {
                "host": credentials.get("host", "localhost"),
                "connected": True,
                "connection_time": datetime.utcnow().isoformat(),
            }

        return db_connection

    @staticmethod
    def execute_query(query: str) -> Dict[str, Any]:
        """Execute database query (simplified for demo)"""
        connection = DatabaseManager.get_connection()

        # Simulate query execution
        result = {
            "query": query,
            "result": "Query executed successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "connection_info": connection,
        }

        # Don't close connection if in connection leak mode
        if not FailureMode.should_leak_connections():
            # In real app, you would properly close connections here
            pass

        return result


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Middleware for structured logging"""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Add request ID to X-Ray subsegment
    subsegment = xray_recorder.current_subsegment()
    if subsegment:
        subsegment.put_annotation("requestId", request_id)

    response = await call_next(request)

    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)

    # Log request details
    log_data = {
        "requestId": request_id,
        "method": request.method,
        "path": str(request.url.path),
        "status": response.status_code,
        "latencyMs": latency_ms,
        "userAgent": request.headers.get("user-agent", ""),
        "remoteAddr": request.client.host if request.client else "",
    }

    # Add error type if status >= 400
    if response.status_code >= 400:
        if response.status_code >= 500:
            log_data["errorType"] = "server_error"
        else:
            log_data["errorType"] = "client_error"

    logger.info("Request processed", **log_data)

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    return response


@app.get("/")
async def root():
    """Root endpoint returning application information"""

    # Check failure mode
    if FailureMode.should_return_500():
        logger.error("Returning 500 due to failure mode", failure_mode="return_500")
        raise HTTPException(status_code=500, detail="Simulated server error")

    return {
        "message": "Golden Path Sample Application",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "region": AWS_REGION,
        "failure_mode": FailureMode.get_current_mode(),
    }


@app.get("/healthz")
async def health_check():
    """Health check endpoint for ALB target group"""

    # Check failure mode - if return_500, make health check fail
    if FailureMode.should_return_500():
        logger.error(
            "Health check failing due to failure mode", failure_mode="return_500"
        )
        raise HTTPException(status_code=500, detail="Health check failed")

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "ok",  # In real app, check actual database connectivity
            "memory": "ok",
            "disk": "ok",
        },
    }


@app.get("/work")
async def simulate_work(
    ms: int = Query(default=100, description="Milliseconds of CPU work to simulate")
):
    """Simulate CPU-intensive work for load testing and autoscaling"""

    # Check failure mode
    if FailureMode.should_return_500():
        logger.error("Returning 500 due to failure mode", failure_mode="return_500")
        raise HTTPException(status_code=500, detail="Simulated server error")

    # Limit work to prevent abuse
    ms = min(ms, 5000)  # Max 5 seconds

    start_time = time.time()

    # Simulate CPU work
    end_time = start_time + (ms / 1000.0)
    while time.time() < end_time:
        # Busy wait to consume CPU
        pass

    actual_ms = int((time.time() - start_time) * 1000)

    logger.info("CPU work completed", requested_ms=ms, actual_ms=actual_ms)

    return {
        "message": "Work completed",
        "requested_ms": ms,
        "actual_ms": actual_ms,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/db")
async def database_query():
    """Perform a simple database query"""

    # Check failure mode
    if FailureMode.should_return_500():
        logger.error("Returning 500 due to failure mode", failure_mode="return_500")
        raise HTTPException(status_code=500, detail="Simulated server error")

    try:
        # Execute a simple query
        result = DatabaseManager.execute_query("SELECT 1 as test_column")

        logger.info("Database query executed successfully")

        return {
            "message": "Database query successful",
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
            "failure_mode": FailureMode.get_current_mode(),
        }

    except Exception as e:
        logger.error("Database query failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Return application metrics"""

    # Check failure mode
    if FailureMode.should_return_500():
        logger.error("Returning 500 due to failure mode", failure_mode="return_500")
        raise HTTPException(status_code=500, detail="Simulated server error")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "failure_mode": FailureMode.get_current_mode(),
        "database_connection": DatabaseManager.get_connection(),
        "environment": {
            "region": AWS_REGION,
            "db_secret_arn": (
                DB_SECRET_ARN[:20] + "..." if DB_SECRET_ARN else "not_configured"
            ),
            "failure_mode_param": PARAM_FAILURE_MODE,
        },
    }


@app.get("/admin/failure-mode")
async def get_failure_mode():
    """Get current failure mode (admin endpoint)"""
    return {
        "failure_mode": FailureMode.get_current_mode(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/admin/failure-mode/{mode}")
async def set_failure_mode(mode: str):
    """Set failure mode (admin endpoint)"""
    try:
        if not PARAM_FAILURE_MODE:
            raise HTTPException(
                status_code=500, detail="Failure mode parameter not configured"
            )

        # Update SSM parameter
        ssm_client.put_parameter(
            Name=PARAM_FAILURE_MODE, Value=mode, Type="String", Overwrite=True
        )

        logger.info("Failure mode updated", new_mode=mode)

        return {
            "message": f"Failure mode set to: {mode}",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("Failed to set failure mode", error=str(e), mode=mode)
        raise HTTPException(
            status_code=500, detail=f"Failed to set failure mode: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
