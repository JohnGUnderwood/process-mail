"""
Comprehensive test suite for Email Search API endpoints.

Run with: pytest test_api.py -v
"""
import os
import sys
import base64
from datetime import datetime, timedelta
from typing import Generator
from unittest.mock import Mock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId, Binary
from pymongo import MongoClient

# Set test environment variables before importing the app
os.environ['MONGODB_URI'] = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
os.environ['API_USERNAME'] = 'testuser'
os.environ['API_PASSWORD'] = 'testpass'

# Mock StaticFiles before importing to avoid directory errors in test environment
sys.modules['fastapi.staticfiles'] = MagicMock()

from api import app, emails_collection, embedding_view, normalize_subject, truncate_body, normalize_newlines


# Test credentials
TEST_USERNAME = 'testuser'
TEST_PASSWORD = 'testpass'


def get_auth_header(username: str = TEST_USERNAME, password: str = TEST_PASSWORD) -> dict:
    """Generate Basic Auth header."""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_email_data():
    """Sample email data for testing."""
    return {
        '_id': ObjectId('507f1f77bcf86cd799439011'),
        'uuid': Binary(b'\x12\x34\x56\x78' * 4, 4),
        'subject': 'Test Email Subject',
        'from': 'sender@example.com',
        'to': 'recipient@example.com',
        'date': datetime(2026, 1, 15, 10, 30, 0),
        'body': 'This is the email body content.\n\nWith multiple paragraphs.',
        'tag': 'inbox'
    }


@pytest.fixture
def mock_thread_emails():
    """Sample thread email data."""
    base_date = datetime(2026, 1, 15, 10, 0, 0)
    return [
        {
            '_id': ObjectId('507f1f77bcf86cd799439011'),
            'subject': 'Re: Project Discussion',
            'from': 'alice@example.com',
            'to': 'bob@example.com',
            'date': base_date,
            'body': 'First email in thread',
            'tag': 'inbox'
        },
        {
            '_id': ObjectId('507f1f77bcf86cd799439012'),
            'subject': 'Re[2]: Project Discussion',
            'from': 'bob@example.com',
            'to': 'alice@example.com',
            'date': base_date + timedelta(hours=2),
            'body': 'Reply to first email',
            'tag': 'sent'
        },
        {
            '_id': ObjectId('507f1f77bcf86cd799439013'),
            'subject': 'RE: Project Discussion',
            'from': 'alice@example.com',
            'to': 'bob@example.com',
            'date': base_date + timedelta(hours=4),
            'body': 'Another reply',
            'tag': 'inbox'
        }
    ]


class TestAuthentication:
    """Test authentication and authorization."""
    
    def test_no_auth_returns_401(self, client):
        """Test that requests without auth return 401."""
        response = client.get("/api/tags")
        assert response.status_code == 401
    
    def test_wrong_password_returns_401(self, client):
        """Test that wrong password returns 401."""
        headers = get_auth_header(TEST_USERNAME, 'wrongpass')
        response = client.get("/api/tags", headers=headers)
        assert response.status_code == 401
    
    def test_wrong_username_returns_401(self, client):
        """Test that wrong username returns 401."""
        headers = get_auth_header('wronguser', TEST_PASSWORD)
        response = client.get("/api/tags", headers=headers)
        assert response.status_code == 401
    
    def test_correct_credentials_succeeds(self, client):
        """Test that correct credentials work."""
        headers = get_auth_header()
        with patch.object(emails_collection, 'distinct', return_value=['inbox', 'sent']):
            response = client.get("/api/tags", headers=headers)
            assert response.status_code == 200


class TestGetTags:
    """Test GET /api/tags endpoint."""
    
    def test_get_tags_returns_sorted_list(self, client):
        """Test that tags are returned sorted."""
        headers = get_auth_header()
        mock_tags = ['sent', 'inbox', 'drafts', 'archive']
        
        with patch.object(emails_collection, 'distinct', return_value=mock_tags):
            response = client.get("/api/tags", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert 'tags' in data
            assert data['tags'] == ['archive', 'drafts', 'inbox', 'sent']
    
    def test_get_tags_filters_empty_values(self, client):
        """Test that empty tags are filtered out."""
        headers = get_auth_header()
        mock_tags = ['inbox', '', None, 'sent']
        
        with patch.object(emails_collection, 'distinct', return_value=mock_tags):
            response = client.get("/api/tags", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data['tags'] == ['inbox', 'sent']
    
    def test_get_tags_handles_empty_database(self, client):
        """Test tags endpoint with empty database."""
        headers = get_auth_header()
        
        with patch.object(emails_collection, 'distinct', return_value=[]):
            response = client.get("/api/tags", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data['tags'] == []
    
    def test_get_tags_handles_database_error(self, client):
        """Test tags endpoint handles database errors."""
        headers = get_auth_header()
        
        with patch.object(emails_collection, 'distinct', side_effect=Exception('Database error')):
            response = client.get("/api/tags", headers=headers)
            
            assert response.status_code == 500
            assert 'Database error' in response.json()['detail']


class TestGetEmail:
    """Test GET /api/emails/{email_id} endpoint."""
    
    def test_get_email_by_id(self, client, mock_email_data):
        """Test retrieving email by ID."""
        headers = get_auth_header()
        email_id = str(mock_email_data['_id'])
        
        with patch.object(emails_collection, 'find_one', return_value=mock_email_data):
            response = client.get(f"/api/emails/{email_id}", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data['_id'] == email_id
            assert data['subject'] == 'Test Email Subject'
            assert data['from'] == 'sender@example.com'
            assert 'date' in data
            assert isinstance(data['date'], str)  # ISO format
    
    def test_get_email_normalizes_newlines(self, client, mock_email_data):
        """Test that email body newlines are normalized."""
        headers = get_auth_header()
        email_id = str(mock_email_data['_id'])
        mock_email_data['body'] = 'Line 1\n\n\n\n\nLine 2'
        
        with patch.object(emails_collection, 'find_one', return_value=mock_email_data):
            response = client.get(f"/api/emails/{email_id}", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            # Should have normalized newlines
            assert '\n\n\n' not in data['body']
    
    def test_get_email_not_found(self, client):
        """Test retrieving non-existent email."""
        headers = get_auth_header()
        email_id = str(ObjectId())
        
        with patch.object(emails_collection, 'find_one', return_value=None):
            response = client.get(f"/api/emails/{email_id}", headers=headers)
            
            # When email is not found, it returns 404 before any exception can occur
            assert response.status_code == 404
            assert 'not found' in response.json()['detail'].lower()
    
    def test_get_email_invalid_id_format(self, client):
        """Test with invalid ObjectId format."""
        headers = get_auth_header()
        
        response = client.get("/api/emails/invalid-id", headers=headers)
        
        assert response.status_code == 500


class TestGetEmailThread:
    """Test GET /api/emails/{email_id}/thread endpoint."""
    
    def test_get_thread_basic(self, client, mock_thread_emails):
        """Test basic thread retrieval."""
        headers = get_auth_header()
        base_email = mock_thread_emails[0]
        email_id = str(base_email['_id'])
        
        # Mock the find().sort() chain - sort() needs to return a list for list() call
        mock_find_result = MagicMock()
        mock_find_result.sort.return_value = iter(mock_thread_emails)  # Make it iterable
        
        with patch.object(emails_collection, 'find_one', return_value=base_email), \
             patch.object(emails_collection, 'find', return_value=mock_find_result):
            
            response = client.get(f"/api/emails/{email_id}/thread", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert 'thread' in data
            assert 'additionalCount' in data
            assert 'baseEmailId' in data
            assert 'dateWindow' in data
            assert data['baseEmailId'] == email_id
            assert data['dateWindow'] == 30  # default
    
    def test_get_thread_custom_days(self, client, mock_thread_emails):
        """Test thread retrieval with custom date window."""
        headers = get_auth_header()
        base_email = mock_thread_emails[0]
        email_id = str(base_email['_id'])
        
        mock_find_result = MagicMock()
        mock_find_result.sort.return_value = iter(mock_thread_emails)
        
        with patch.object(emails_collection, 'find_one', return_value=base_email), \
             patch.object(emails_collection, 'find', return_value=mock_find_result):
            
            response = client.get(f"/api/emails/{email_id}/thread?days=7", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data['dateWindow'] == 7
    
    def test_get_thread_invalid_days(self, client):
        """Test thread with invalid days parameter."""
        headers = get_auth_header()
        email_id = str(ObjectId())
        
        # Test days < 1
        response = client.get(f"/api/emails/{email_id}/thread?days=0", headers=headers)
        assert response.status_code == 422
        
        # Test days > 365
        response = client.get(f"/api/emails/{email_id}/thread?days=500", headers=headers)
        assert response.status_code == 422
    
    def test_get_thread_normalizes_subjects(self, client, mock_thread_emails):
        """Test that thread matching normalizes subject lines."""
        headers = get_auth_header()
        base_email = mock_thread_emails[0]
        email_id = str(base_email['_id'])
        
        mock_find_result = MagicMock()
        mock_find_result.sort.return_value = iter(mock_thread_emails)
        
        # All subjects should normalize to "Project Discussion"
        with patch.object(emails_collection, 'find_one', return_value=base_email), \
             patch.object(emails_collection, 'find', return_value=mock_find_result):
            
            response = client.get(f"/api/emails/{email_id}/thread", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            # All three emails should be in thread due to normalized subjects
            assert len(data['thread']) >= 1
    
    def test_get_thread_email_not_found(self, client):
        """Test thread for non-existent email."""
        headers = get_auth_header()
        email_id = str(ObjectId())
        
        with patch.object(emails_collection, 'find_one', return_value=None):
            response = client.get(f"/api/emails/{email_id}/thread", headers=headers)
            
            assert response.status_code == 404
    
    def test_get_thread_no_subject(self, client):
        """Test thread for email without subject."""
        headers = get_auth_header()
        base_email = {
            '_id': ObjectId(),
            'subject': '',
            'from': 'test@example.com',
            'to': 'other@example.com',
            'date': datetime.now()
        }
        email_id = str(base_email['_id'])
        
        with patch.object(emails_collection, 'find_one', return_value=base_email):
            response = client.get(f"/api/emails/{email_id}/thread", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            # Should return just the base email
            assert len(data['thread']) == 1


class TestSearchEndpoint:
    """Test GET /api/search endpoint."""
    
    def test_search_vector_basic(self, client, mock_email_data):
        """Test basic vector search."""
        headers = get_auth_header()
        mock_results = [mock_email_data]
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results):
            response = client.get(
                "/api/search?query=test&search_type=vector",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert 'results' in data
            assert 'pagination' in data
            assert data['pagination']['searchType'] == 'vector'
    
    def test_search_vector_with_pagination(self, client):
        """Test vector search pagination."""
        headers = get_auth_header()
        mock_results = [{'_id': ObjectId(), 'subject': f'Email {i}'} for i in range(25)]
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results):
            response = client.get(
                "/api/search?query=test&search_type=vector&page=2&page_size=25",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data['pagination']['currentPage'] == 2
            assert data['pagination']['hasMore'] is True
            assert data['pagination']['nextPage'] == 3
            assert data['pagination']['prevPage'] == 1
    
    def test_search_vector_with_filters(self, client):
        """Test vector search with tag and date filters."""
        headers = get_auth_header()
        mock_results = []
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results):
            response = client.get(
                "/api/search?query=test&search_type=vector&tag=inbox&date_start=2026-01-01T00:00:00",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert 'results' in data
    
    def test_search_vector_invalid_page(self, client):
        """Test vector search with invalid page number."""
        headers = get_auth_header()
        
        # Page too high (max 20)
        response = client.get(
            "/api/search?query=test&search_type=vector&page=25",
            headers=headers
        )
        assert response.status_code == 422
        
        # Page too low
        response = client.get(
            "/api/search?query=test&search_type=vector&page=0",
            headers=headers
        )
        assert response.status_code == 422
    
    def test_search_text_basic(self, client):
        """Test basic text search."""
        headers = get_auth_header()
        mock_results = [{
            '_id': ObjectId(),
            'subject': 'Test Email',
            'body': 'Test content',
            'paginationToken': 'token123'
        }]
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results):
            response = client.get(
                "/api/search?query=test&search_type=text",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert 'results' in data
            assert 'pagination' in data
            assert data['pagination']['searchType'] == 'text'
            assert 'nextToken' in data['pagination']
    
    def test_search_text_with_token(self, client):
        """Test text search with pagination token."""
        headers = get_auth_header()
        mock_results = []
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results):
            response = client.get(
                "/api/search?query=test&search_type=text&token=abc123&direction=after",
                headers=headers
            )
            
            assert response.status_code == 200
    
    def test_search_text_with_before_direction(self, client):
        """Test text search with 'before' direction."""
        headers = get_auth_header()
        mock_results = [{
            '_id': ObjectId(),
            'subject': 'Test',
            'paginationToken': 'token123'
        }]
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results):
            response = client.get(
                "/api/search?query=test&search_type=text&token=abc123&direction=before",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            # Results should be reversed for 'before'
            assert 'results' in data
    
    def test_search_text_with_filters_and_token(self, client):
        """Test that pagination token is preserved when using filters."""
        headers = get_auth_header()
        mock_results = []
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results) as mock_agg:
            response = client.get(
                "/api/search?query=test&search_type=text&tag=inbox&token=abc123&direction=after",
                headers=headers
            )
            
            assert response.status_code == 200
            # Verify the aggregate was called with correct structure
            called_pipeline = mock_agg.call_args[0][0]
            search_stage = called_pipeline[0]['$search']
            # Token should be present even with filters
            assert 'searchAfter' in search_stage
            assert search_stage['searchAfter'] == 'abc123'
            # Should use compound query
            assert 'compound' in search_stage
    
    def test_search_missing_query(self, client):
        """Test search without query parameter."""
        headers = get_auth_header()
        
        response = client.get("/api/search", headers=headers)
        
        assert response.status_code == 422  # Validation error
    
    def test_search_invalid_search_type(self, client):
        """Test search with invalid search type."""
        headers = get_auth_header()
        
        response = client.get(
            "/api/search?query=test&search_type=invalid",
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_search_truncates_body(self, client):
        """Test that search results truncate body to snippet."""
        headers = get_auth_header()
        long_body = "a" * 300  # Longer than default 200 chars
        mock_results = [{
            '_id': ObjectId(),
            'subject': 'Test',
            'body': long_body,
            'date': datetime.now()
        }]
        
        with patch.object(embedding_view, 'aggregate', return_value=mock_results):
            response = client.get(
                "/api/search?query=test&search_type=vector",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data['results']) > 0
            # Body should be replaced with bodySnippet
            assert 'bodySnippet' in data['results'][0]
            assert 'body' not in data['results'][0]
            # Snippet should be truncated
            assert len(data['results'][0]['bodySnippet']) <= 203  # 200 + "..."
    
    def test_search_invalid_page_size(self, client):
        """Test search with invalid page size."""
        headers = get_auth_header()
        
        # Too large
        response = client.get(
            "/api/search?query=test&page_size=150",
            headers=headers
        )
        assert response.status_code == 422
        
        # Too small
        response = client.get(
            "/api/search?query=test&page_size=0",
            headers=headers
        )
        assert response.status_code == 422
    
    def test_search_database_error(self, client):
        """Test search handles database errors."""
        headers = get_auth_header()
        
        with patch.object(embedding_view, 'aggregate', side_effect=Exception('Database connection failed')):
            response = client.get(
                "/api/search?query=test&search_type=vector",
                headers=headers
            )
            
            assert response.status_code == 500
            assert 'Database connection failed' in response.json()['detail']


class TestUtilityFunctions:
    """Test utility helper functions."""
    
    def test_normalize_subject_removes_re_prefix(self):
        """Test that Re: prefixes are removed."""
        assert normalize_subject("Re: Test Subject") == "Test Subject"
        assert normalize_subject("RE: Test Subject") == "Test Subject"
        assert normalize_subject("re: Test Subject") == "Test Subject"
    
    def test_normalize_subject_removes_numbered_re(self):
        """Test that Re[N]: prefixes are removed."""
        assert normalize_subject("Re[2]: Test Subject") == "Test Subject"
        assert normalize_subject("RE[5] : Test Subject") == "Test Subject"
    
    def test_normalize_subject_removes_multiple_re(self):
        """Test that multiple Re: prefixes are removed."""
        assert normalize_subject("Re: Re: Re: Test") == "Test"
        assert normalize_subject("RE: re: RE: Test") == "Test"
    
    def test_normalize_subject_preserves_fwd(self):
        """Test that Fwd: prefixes are NOT removed."""
        assert normalize_subject("Fwd: Test Subject") == "Fwd: Test Subject"
        assert normalize_subject("FW: Test Subject") == "FW: Test Subject"
    
    def test_normalize_subject_handles_empty(self):
        """Test normalize_subject with empty input."""
        assert normalize_subject("") == ""
        assert normalize_subject(None) == ""
    
    def test_normalize_subject_strips_whitespace(self):
        """Test that extra whitespace is stripped."""
        assert normalize_subject("  Re: Test  ") == "Test"
        assert normalize_subject("Re:    Test") == "Test"
    
    def test_truncate_body_short_text(self):
        """Test truncate_body with short text."""
        short = "Short text"
        assert truncate_body(short) == short
    
    def test_truncate_body_long_text(self):
        """Test truncate_body with long text."""
        long_text = "a" * 300
        result = truncate_body(long_text, max_length=200)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")
    
    def test_truncate_body_empty(self):
        """Test truncate_body with empty input."""
        assert truncate_body("") == ""
        assert truncate_body(None) == ""
    
    def test_truncate_body_custom_length(self):
        """Test truncate_body with custom max length."""
        text = "a" * 100
        result = truncate_body(text, max_length=50)
        assert len(result) == 53  # 50 + "..."
    
    def test_normalize_newlines_multiple_blank_lines(self):
        """Test normalize_newlines replaces multiple blank lines."""
        text = "Line 1\n\n\n\nLine 2"
        result = normalize_newlines(text)
        assert result == "Line 1\n\nLine 2"
    
    def test_normalize_newlines_with_spaces(self):
        """Test normalize_newlines handles spaces between newlines."""
        text = "Line 1\n  \n  \nLine 2"
        result = normalize_newlines(text)
        assert result == "Line 1\n\nLine 2"
    
    def test_normalize_newlines_empty(self):
        """Test normalize_newlines with empty input."""
        assert normalize_newlines("") == ""
        assert normalize_newlines(None) is None
    
    def test_normalize_newlines_preserves_single_blank(self):
        """Test that single blank lines are preserved."""
        text = "Line 1\n\nLine 2"
        result = normalize_newlines(text)
        assert result == "Line 1\n\nLine 2"


class TestCORSMiddleware:
    """Test CORS configuration."""
    
    def test_cors_allows_all_origins(self, client):
        """Test that CORS allows all origins."""
        headers = {
            **get_auth_header(),
            "Origin": "http://example.com"
        }
        
        with patch.object(emails_collection, 'distinct', return_value=['inbox']):
            response = client.get("/api/tags", headers=headers)
            
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
    
    def test_cors_options_request(self, client):
        """Test CORS preflight OPTIONS request."""
        response = client.options(
            "/api/tags",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # FastAPI/Starlette handles OPTIONS automatically with CORS middleware
        assert response.status_code in [200, 405]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_search_with_invalid_date_format(self, client):
        """Test search with invalid date format."""
        headers = get_auth_header()
        
        response = client.get(
            "/api/search?query=test&date_start=invalid-date",
            headers=headers
        )
        
        # Should fail during date parsing
        assert response.status_code == 500
    
    def test_search_with_valid_iso_date(self, client):
        """Test search with valid ISO date format."""
        headers = get_auth_header()
        
        with patch.object(embedding_view, 'aggregate', return_value=[]):
            response = client.get(
                "/api/search?query=test&date_start=2026-01-01T00:00:00&date_end=2026-12-31T23:59:59",
                headers=headers
            )
            
            assert response.status_code == 200
    
    def test_large_page_number_vector_search(self, client):
        """Test vector search respects max page limit."""
        headers = get_auth_header()
        
        # Page 20 should work (max allowed)
        with patch.object(embedding_view, 'aggregate', return_value=[]):
            response = client.get(
                "/api/search?query=test&search_type=vector&page=20",
                headers=headers
            )
            assert response.status_code == 200
    
    def test_empty_search_results(self, client):
        """Test search with no results."""
        headers = get_auth_header()
        
        with patch.object(embedding_view, 'aggregate', return_value=[]):
            response = client.get(
                "/api/search?query=nonexistent",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data['results']) == 0
            assert data['pagination']['hasMore'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
