# Testing Guide

## Running Tests

### Install Dependencies

First, install the test dependencies:

```bash
pip install -r requirements.txt
```

### Run All Tests

Run all tests with verbose output:

```bash
pytest app/test_api.py -v
```

### Run Specific Test Classes

```bash
# Test authentication only
pytest app/test_api.py::TestAuthentication -v

# Test search endpoint only
pytest app/test_api.py::TestSearchEndpoint -v

# Test utility functions
pytest app/test_api.py::TestUtilityFunctions -v
```

### Run Specific Tests

```bash
# Run a single test
pytest app/test_api.py::TestGetTags::test_get_tags_returns_sorted_list -v

# Run tests matching a pattern
pytest app/test_api.py -k "search" -v
```

### Test Coverage

To run tests with coverage report:

```bash
pip install pytest-cov
pytest app/test_api.py --cov=app --cov-report=html
```

View the coverage report by opening `htmlcov/index.html` in your browser.

## Test Structure

The test suite is organized into the following test classes:

### TestAuthentication
Tests for HTTP Basic Authentication:
- No authentication returns 401
- Wrong credentials return 401
- Correct credentials succeed

### TestGetTags
Tests for `GET /api/tags`:
- Returns sorted tag list
- Filters empty values
- Handles empty database
- Handles database errors

### TestGetEmail
Tests for `GET /api/emails/{email_id}`:
- Retrieve email by ID
- Body newline normalization
- Email not found (404)
- Invalid ID format handling

### TestGetEmailThread
Tests for `GET /api/emails/{email_id}/thread`:
- Basic thread retrieval
- Custom date window
- Invalid parameters
- Subject normalization
- Email not found
- Missing subject handling

### TestSearchEndpoint
Tests for `GET /api/search`:
- Vector search (basic, pagination, filters)
- Text search (basic, tokens, directions)
- Parameter validation
- Body truncation
- Error handling

### TestUtilityFunctions
Tests for helper functions:
- `normalize_subject()` - removes Re: prefixes
- `truncate_body()` - truncates long text
- `normalize_newlines()` - normalizes blank lines

### TestCORSMiddleware
Tests for CORS configuration:
- Allows all origins
- Handles preflight OPTIONS requests

### TestEdgeCases
Tests for edge cases:
- Invalid date formats
- Large page numbers
- Empty results

## Environment Variables

The tests use these environment variables:
- `MONGODB_URI` - MongoDB connection string (defaults to localhost)
- `API_USERNAME` - Set to 'testuser' for tests
- `API_PASSWORD` - Set to 'testpass' for tests

## Mocking

The tests use mocks for MongoDB operations to avoid requiring a live database connection. This makes tests:
- Fast and reliable
- Runnable in CI/CD pipelines
- Independent of external services

## Continuous Integration

Add these commands to your CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Install dependencies
  run: pip install -r requirements.txt

- name: Run tests
  run: pytest app/test_api.py -v --tb=short

- name: Generate coverage
  run: pytest app/test_api.py --cov=app --cov-report=xml
```

## Troubleshooting

### Import Errors
If you see import errors, make sure you're running pytest from the project root:
```bash
cd c:\Users\john\GitHub\process-mail
pytest app/test_api.py -v
```

### Mock Issues
The tests mock MongoDB collections. If you need to test against a real database, modify the fixtures to use actual database connections.

### Authentication Failures
The tests set `API_USERNAME` and `API_PASSWORD` environment variables. Make sure your `.env` file doesn't conflict with these test values.
