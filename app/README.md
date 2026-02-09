# Email Search Frontend

A web application for searching emails stored in MongoDB with vector (semantic) and keyword search capabilities.

## Features

- **Vector Search**: Semantic search using MongoDB Atlas auto-embeddings (Voyage-4 model)
- **Keyword Search**: Full-text search using MongoDB Atlas Search text index
- **Advanced Filtering**: Filter by date range and email tags/mailboxes
- **Thread View**: View email conversations grouped by subject and participants
- **Pagination**: Token-based pagination for text search, page-based for vector search (max 20 pages)
- **Authentication**: HTTP Basic Auth for secure access

## Setup

1. **Install dependencies** (from project root):
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables** in `.env` (in project root):
   ```
   MONGODB_URI=your_mongodb_connection_string
   API_USERNAME=your_username
   API_PASSWORD=your_password
   ```

3. **Ensure MongoDB Atlas Search indexes are configured**:
   - **Vector Search Index**: `default` on `email_embedding_source` view with `embedding_source` path
   - **Text Search Index**: `text` on `email_embedding_source` view with fields: subject, body, from, to

4. **Run the server** (from the app directory):
   ```bash
   cd app
   python run_server.py
   ```
   Or:
   ```bash
   cd app
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Open in browser**: Navigate to `http://localhost:8000`

## Usage

1. **Login** with your configured username and password
2. **Enter a search query** in the search bar
3. **Choose search type**:
   - **Vector (Semantic)**: Finds semantically similar emails using AI embeddings
   - **Keyword**: Traditional text search matching exact words/phrases
4. **Apply filters** (optional):
   - Select a tag/mailbox
   - Set date range
5. **View results**:
   - Click on subject to view full email
   - Click "Thread" to view related conversation
6. **Navigate pages** using Previous/Next buttons

## API Endpoints

- `GET /api/search` - Search emails with vector or text search
- `GET /api/emails/{id}` - Get full email details
- `GET /api/emails/{id}/thread?days=30` - Get email thread
- `GET /api/tags` - Get list of available tags

## Thread Matching

Email threads are matched based on:
- **Normalized subject** (strips "Re:", "RE:", "Re[2]:", etc. but keeps "Fwd:")
- **Bidirectional participants** (from/to matching in either direction)
- **Configurable date window** (7, 14, 30, 60, or 90 days)

## Security Notes

- Change default `API_USERNAME` and `API_PASSWORD` in production
- Use HTTPS when deploying to a server
- Consider adding rate limiting for production deployments
- Never commit `.env` file to version control

## Technology Stack

- **Backend**: FastAPI with Python 3.x
- **Database**: MongoDB with Atlas Search
- **Frontend**: Vanilla JavaScript with HTML/CSS
- **Authentication**: HTTP Basic Auth
- **Embeddings**: MongoDB Atlas auto-embedding (Voyage-4)
