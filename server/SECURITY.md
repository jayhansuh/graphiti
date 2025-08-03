# Security Notes

## Secret Scanning False Positives

The `detect-secrets` tool may flag the following as potential secrets, but they are **false positives**:

### Test Files
- `tests/llm_client/test_anthropic_client.py` - Contains `env_api_key` and `test_api_key`
- `tests/llm_client/test_gemini_client.py` - Contains `test_api_key`

These are **placeholder values** used in unit tests and are not real API keys. They are used to:
1. Mock API key validation in tests
2. Ensure the configuration system works correctly
3. Test environment variable handling

### How to Verify

You can verify these are test files by:
1. Checking the file paths - they're in the `tests/` directory
2. Looking at the context - they're used with mocked clients
3. Seeing the values - generic names like `test_api_key` or `env_api_key`

## Running Tests

To run tests, ensure you have the test dependencies installed:

```bash
# If using uv
uv sync --extra dev

# If using pip
pip install pytest pytest-asyncio pytest-xdist

# Run tests
pytest
```

## Real Secrets Management

For production deployment:
1. Never commit real API keys to the repository
2. Use environment variables or `.env` files (which are gitignored)
3. Follow the deployment guide in `deployment/README.md` for secure configuration
4. Use strong, unique passwords for Neo4j and other services

## Reporting Security Issues

If you discover a real security vulnerability, please:
1. Do NOT open a public issue
2. Contact the maintainers directly
3. Allow time for the issue to be addressed before public disclosure