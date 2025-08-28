# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- AWS Fault Injection Simulator (FIS) integration for professional chaos engineering
- Comprehensive CI/CD pipeline with security scanning
- Professional documentation structure

### Changed
- Replaced SSM parameter-based chaos with FIS experiments
- Enhanced observability stack with critical alarm exposure

### Removed
- Amateur SSM parameter failure injection logic

## [0.1.0] - 2024-01-XX

### Added
- Initial release of ECS Fargate Golden Path
- Multi-AZ ECS Fargate service with Aurora Serverless v2
- Comprehensive observability with CloudWatch dashboards and alarms
- Blue/green deployments with CodeDeploy
- WAF protection and security best practices
- Break/fix lab scenarios and runbooks
- X-Ray distributed tracing
- Cost-optimized architecture (single NAT Gateway)

### Features
- Production-ready ECS Fargate patterns
- Automated rollback on alarm breach
- Structured JSON logging
- Game day scenarios for incident response training