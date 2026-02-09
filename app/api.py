"""
FastAPI backend for email search with vector and keyword search capabilities.
"""
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Literal
from bson import Binary
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Email Search API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP Basic Auth setup
security = HTTPBasic()

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
API_USERNAME = os.getenv('API_USERNAME', 'admin')
API_PASSWORD = os.getenv('API_PASSWORD', 'admin')

client = MongoClient(MONGODB_URI)
db = client['mbox']
emails_collection = db['emails']
embedding_view = db['email_embedding_source']


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify HTTP Basic Auth credentials."""
    is_username_correct = secrets.compare_digest(
        credentials.username.encode("utf8"), API_USERNAME.encode("utf8")
    )
    is_password_correct = secrets.compare_digest(
        credentials.password.encode("utf8"), API_PASSWORD.encode("utf8")
    )
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def uuid_to_string(doc):
    """Convert Binary UUID to string in a document."""
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    if doc and 'uuid' in doc and isinstance(doc['uuid'], Binary):
        doc['uuid'] = str(doc['uuid'])
    return doc


def normalize_newlines(text: str) -> str:
    """Replace multiple consecutive newlines with a single newline."""
    if not text:
        return text
    return re.sub(r'\n\s*\n+', '\n\n', text)


def normalize_subject(subject: str) -> str:
    """
    Normalize email subject by stripping reply prefixes.
    Handles: Re:, RE:, Re[N]:, RE , re:, etc.
    Preserves: Fwd:, FW:
    """
    if not subject:
        return ""
    # Strip leading/trailing whitespace
    normalized = subject.strip()
    # Remove reply prefixes (case-insensitive, handles various formats)
    # Pattern matches: Re:, RE:, Re , RE , Re[2]:, RE[3] :, etc.
    pattern = r'^(re|RE)(\s*\[\d+\])?\s*:?\s*'
    while re.match(pattern, normalized, re.IGNORECASE):
        normalized = re.sub(pattern, '', normalized, count=1, flags=re.IGNORECASE).strip()
    return normalized


def truncate_body(body: str, max_length: int = 200) -> str:
    """Truncate email body to specified length."""
    if not body:
        return ""
    body = normalize_newlines(body)
    if len(body) <= max_length:
        return body
    return body[:max_length] + "..."


@app.get("/api/tags")
async def get_tags(username: str = Depends(verify_credentials)):
    """Get list of unique email tags/mailboxes."""
    try:
        tags = emails_collection.distinct('tag')
        return {"tags": sorted([tag for tag in tags if tag])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/emails/{email_id}")
async def get_email(email_id: str, username: str = Depends(verify_credentials)):
    """Get full email details by ID."""
    try:
        from bson import ObjectId
        email = emails_collection.find_one({"_id": ObjectId(email_id)})
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        email = uuid_to_string(email)
        # Normalize body newlines
        if 'body' in email:
            email['body'] = normalize_newlines(email['body'])
        # Convert date to ISO string
        if 'date' in email and isinstance(email['date'], datetime):
            email['date'] = email['date'].isoformat()
        
        return email
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/emails/{email_id}/thread")
async def get_email_thread(
    email_id: str,
    days: int = Query(default=30, ge=1, le=365),
    username: str = Depends(verify_credentials)
):
    """
    Get email thread based on normalized subject and participants.
    Returns emails within ±days of the base email's date.
    """
    try:
        from bson import ObjectId
        
        # Get the base email
        base_email = emails_collection.find_one({"_id": ObjectId(email_id)})
        if not base_email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Normalize the subject
        normalized_subject = normalize_subject(base_email.get('subject', ''))
        base_date = base_email.get('date')
        base_from = base_email.get('from', '')
        base_to = base_email.get('to', '')
        
        if not base_date or not normalized_subject:
            return {
                "thread": [uuid_to_string(base_email)],
                "additionalCount": 0,
                "baseEmailId": email_id
            }
        
        # Calculate date range
        date_start = base_date - timedelta(days=days)
        date_end = base_date + timedelta(days=days)
        
        # Build query for thread emails
        # Match normalized subject and bidirectional from/to
        thread_query = {
            '$or': [
                # Base email is sender
                {'from': base_from, 'to': base_to},
                # Base email is recipient
                {'from': base_to, 'to': base_from},
                # Either direction with base_from
                {'from': base_from},
                {'to': base_from},
                # Either direction with base_to
                {'from': base_to},
                {'to': base_to}
            ],
            'date': {
                '$gte': date_start,
                '$lte': date_end
            }
        }
        
        # Get all matching emails and filter by normalized subject
        all_emails = list(emails_collection.find(thread_query).sort('date', 1))
        thread_emails = []
        for email in all_emails:
            email_subject = normalize_subject(email.get('subject', ''))
            if email_subject == normalized_subject:
                # Normalize body and convert date
                if 'body' in email:
                    email['body'] = normalize_newlines(email['body'])
                if 'date' in email and isinstance(email['date'], datetime):
                    email['date'] = email['date'].isoformat()
                thread_emails.append(uuid_to_string(email))
        
        # Count emails outside the date window
        count_query_outside = {
            '$or': [
                {'from': base_from, 'to': base_to},
                {'from': base_to, 'to': base_from},
                {'from': base_from},
                {'to': base_from},
                {'from': base_to},
                {'to': base_to}
            ],
            'date': {
                '$or': [
                    {'$lt': date_start},
                    {'$gt': date_end}
                ]
            }
        }
        
        # Count all emails outside window with matching subject
        all_outside = list(emails_collection.find(count_query_outside))
        additional_count = 0
        for email in all_outside:
            email_subject = normalize_subject(email.get('subject', ''))
            if email_subject == normalized_subject:
                additional_count += 1
        
        return {
            "thread": thread_emails,
            "additionalCount": additional_count,
            "baseEmailId": email_id,
            "dateWindow": days
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_emails(
    query: str = Query(..., description="Search query text"),
    search_type: Literal["vector", "text"] = Query(default="vector", description="Search type: vector or text"),
    page: Optional[int] = Query(default=1, ge=1, le=20, description="Page number for vector search (max 20)"),
    token: Optional[str] = Query(default=None, description="Pagination token for text search"),
    direction: Optional[Literal["after", "before"]] = Query(default="after", description="Token direction for text search"),
    page_size: int = Query(default=25, ge=1, le=100, description="Results per page"),
    tag: Optional[str] = Query(default=None, description="Filter by tag/mailbox"),
    date_start: Optional[str] = Query(default=None, description="Start date (ISO format)"),
    date_end: Optional[str] = Query(default=None, description="End date (ISO format)"),
    username: str = Depends(verify_credentials)
):
    """
    Unified search endpoint supporting both vector and text search.
    
    Vector search: Uses Atlas auto-embedding on email_embedding_source view with page-based pagination.
    Text search: Uses $search with token-based pagination.
    """
    try:
        # Parse date filters if provided
        date_filter = {}
        if date_start:
            date_filter['$gte'] = datetime.fromisoformat(date_start)
        if date_end:
            date_filter['$lte'] = datetime.fromisoformat(date_end)
        
        if search_type == "vector":
            # Vector search using $vectorSearch on embedding view
            offset = (page - 1) * page_size
            num_candidates = offset + (page_size * 3)
            vector_limit = offset + page_size
            
            # Build filter for vector search
            filter_conditions = []
            if tag:
                filter_conditions.append({'tag': tag})
            if date_filter:
                filter_conditions.append({'date': date_filter})
            
            vector_search_stage = {
                '$vectorSearch': {
                    'index': 'default',
                    'path': 'embedding_source',
                    'query': query,  # Atlas auto-embeds the query
                    'numCandidates': num_candidates,
                    'limit': vector_limit
                }
            }
            
            # Add filter if conditions exist
            if filter_conditions:
                if len(filter_conditions) == 1:
                    vector_search_stage['$vectorSearch']['filter'] = filter_conditions[0]
                else:
                    vector_search_stage['$vectorSearch']['filter'] = {'$and': filter_conditions}
            
            pipeline = [
                vector_search_stage,
                {'$skip': offset},
                {'$limit': page_size},
                {
                    '$project': {
                        '_id': 1,
                        'uuid': 1,
                        'subject': 1,
                        'from': 1,
                        'to': 1,
                        'date': 1,
                        'body': 1,
                        'tag': 1,
                        'score': {'$meta': 'vectorSearchScore'}
                    }
                }
            ]
            
            results = list(embedding_view.aggregate(pipeline))
            
            # Process results
            for result in results:
                result = uuid_to_string(result)
                if 'body' in result:
                    result['bodySnippet'] = truncate_body(result['body'])
                    del result['body']  # Don't send full body in search results
                if 'date' in result and isinstance(result['date'], datetime):
                    result['date'] = result['date'].isoformat()
            
            return {
                "results": results,
                "pagination": {
                    "searchType": "vector",
                    "pageSize": page_size,
                    "currentPage": page,
                    "hasMore": len(results) == page_size,
                    "nextPage": page + 1 if len(results) == page_size and page < 20 else None,
                    "prevPage": page - 1 if page > 1 else None
                }
            }
        
        else:  # text search
            # Text search using $search with token pagination
            # Build base search query
            text_query = {
                'query': query,
                'path': ['subject', 'body', 'from', 'to']
            }
            
            # Add compound query with filters if needed
            if tag or date_filter:
                compound_filter = []
                
                if tag:
                    compound_filter.append({'text': {'query': tag, 'path': 'tag'}})
                if date_filter:
                    compound_filter.append({'range': {'path': 'date', **{k.replace('$', ''): v for k, v in date_filter.items()}}})
                
                search_stage = {
                    '$search': {
                        'index': 'text',
                        'compound': {
                            'must': [{'text': text_query}],
                            'filter': compound_filter
                        }
                    }
                }
            else:
                search_stage = {
                    '$search': {
                        'index': 'text',
                        'text': text_query
                    }
                }
            
            # Add token if provided (must be at top level of $search)
            if token:
                if direction == "before":
                    search_stage['$search']['searchBefore'] = token
                else:
                    search_stage['$search']['searchAfter'] = token
            
            # Sort by _id for consistent pagination
            search_stage['$search']['sort'] = {'_id': 1}
            
            pipeline = [
                search_stage,
                {'$limit': page_size},
                {
                    '$project': {
                        '_id': 1,
                        'uuid': 1,
                        'subject': 1,
                        'from': 1,
                        'to': 1,
                        'date': 1,
                        'body': 1,
                        'tag': 1,
                        'paginationToken': {'$meta': 'searchSequenceToken'},
                        'score': {'$meta': 'searchScore'}
                    }
                }
            ]
            
            results = list(embedding_view.aggregate(pipeline))
            
            # Reverse results if searching before
            if direction == "before":
                results = list(reversed(results))
            
            # Process results and extract tokens
            next_token = None
            prev_token = None
            processed_results = []
            
            for result in results:
                pagination_token = result.pop('paginationToken', None)
                result = uuid_to_string(result)
                
                if 'body' in result:
                    result['bodySnippet'] = truncate_body(result['body'])
                    del result['body']
                if 'date' in result and isinstance(result['date'], datetime):
                    result['date'] = result['date'].isoformat()
                
                processed_results.append(result)
                
                # Store tokens from first and last results
                if pagination_token:
                    if not prev_token:
                        prev_token = pagination_token
                    next_token = pagination_token
            
            return {
                "results": processed_results,
                "pagination": {
                    "searchType": "text",
                    "pageSize": page_size,
                    "hasMore": len(results) == page_size,
                    "nextToken": next_token,
                    "prevToken": prev_token
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
