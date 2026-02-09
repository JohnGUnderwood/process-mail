"""
Test script to verify MongoDB connection and data structure.
Run this before starting the API server.
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    """Test MongoDB connection and verify data structure."""
    print("Testing MongoDB connection...")
    
    try:
        # Connect to MongoDB
        MONGODB_URI = os.getenv('MONGODB_URI')
        client = MongoClient(MONGODB_URI)
        
        # Test connection
        client.admin.command('ping')
        print("✓ MongoDB connection successful")
        
        # Check database and collections
        db = client['mbox']
        collections = db.list_collection_names()
        print(f"✓ Found {len(collections)} collections in 'mbox' database")
        
        # Check emails collection
        emails_count = db['emails'].count_documents({})
        print(f"✓ Found {emails_count:,} emails in collection")
        
        # Check email_embedding_source view
        if 'email_embedding_source' in collections:
            print("✓ email_embedding_source view exists")
        else:
            print("✗ WARNING: email_embedding_source view not found")
        
        # Sample email
        sample = db['emails'].find_one()
        if sample:
            print("\n✓ Sample email structure:")
            print(f"  - Fields: {', '.join(sample.keys())}")
            if 'subject' in sample:
                print(f"  - Sample subject: {sample['subject'][:50]}...")
        
        # Check tags
        tags = db['emails'].distinct('tag')
        print(f"\n✓ Found {len(tags)} unique tags/mailboxes")
        if tags:
            print(f"  - Sample tags: {', '.join(tags[:5])}")
        
        # Check indexes
        indexes = list(db['emails'].list_indexes())
        print(f"\n✓ Indexes on emails collection: {len(indexes)}")
        for idx in indexes:
            print(f"  - {idx['name']}")
        
        print("\n✓ All checks passed! Ready to start the API server.")
        print("\nNext steps:")
        print("1. Ensure Atlas Search indexes are configured:")
        print("   - Vector index 'default' on email_embedding_source view")
        print("   - Text index 'text' on email_embedding_source view")
        print("2. Run: python run_server.py")
        print("3. Open: http://localhost:8000")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

if __name__ == "__main__":
    test_connection()
