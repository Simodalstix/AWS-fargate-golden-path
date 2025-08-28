# Contributing to ECS Fargate Golden Path

## Development Setup

1. **Prerequisites**
   ```bash
   # Install Node.js 18+ and Python 3.8+
   npm install -g aws-cdk
   ```

2. **Local Development**
   ```bash
   git clone https://github.com/Simodalstix/AWS-ecs-fargate-golden-path.git
   cd AWS-ecs-fargate-golden-path
   python -m venv .venv && source .venv/bin/activate
   pip install -r infra/requirements.txt
   ```

3. **Testing**
   ```bash
   cd infra && python -m pytest tests/ -v
   ```

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `pytest tests/`
5. Ensure CDK synth works: `cdk synth --all`
6. Submit a pull request

## Code Standards

- Follow PEP 8 for Python code
- Add type hints where appropriate
- Include docstrings for public methods
- Write tests for new functionality
- Keep commits atomic and well-described

## Architecture Changes

For significant architectural changes:
1. Open an issue first to discuss the approach
2. Update relevant documentation
3. Add/update tests
4. Consider backward compatibility

## Questions?

Open an issue for questions or join discussions in existing issues.