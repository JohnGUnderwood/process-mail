"""
Simple script to run the Email Search API server.
"""
import uvicorn

if __name__ == "__main__":
    print("Starting Email Search API server...")
    print("Open http://localhost:8000 in your browser")
    print("Press Ctrl+C to stop the server")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
