import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path
from email.utils import parsedate_to_datetime
from bson.binary import Binary, UuidRepresentation
import uuid

# Load environment variables from .env file
load_dotenv()

# Get MongoDB connection string from environment variable
MONGODB_URI = os.getenv('MONGODB_URI')

if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable not found. Please set it in your .env file")

# Connect to MongoDB
print(f"Connecting to MongoDB...")
client = MongoClient(MONGODB_URI)

# Access database and collection
db = client['mbox']
collection = db['emails']

print(f"Connected to database: mbox, collection: emails")

# Find all JSONL files in the processed_mail directory
processed_mail_dir = Path('C:/Users/john/processed_mail')

if not processed_mail_dir.exists():
    print("Error: 'processed_mail' directory not found")
    exit(1)

jsonl_files = list(processed_mail_dir.rglob('*.jsonl'))

if not jsonl_files:
    print("No JSONL files found in processed_mail directory")
    exit(1)

print(f"Found {len(jsonl_files)} JSONL file(s) to process")

total_loaded = 0

# Process each JSONL file
for jsonl_file in jsonl_files:
    print(f"\nProcessing: {jsonl_file}")
    
    # Get the tag (inbox name) from the parent directory name
    tag = jsonl_file.parent.name
    
    documents = []
    
    # Read JSONL file line by line
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                doc = json.loads(line)
                
                # Convert UUID string to BSON Binary UUID
                if 'uuid' in doc and doc['uuid']:
                    try:
                        uuid_obj = uuid.UUID(doc['uuid'])
                        doc['uuid'] = Binary.from_uuid(uuid_obj)
                    except (ValueError, AttributeError) as e:
                        print(f"  Warning: Failed to parse UUID on line {line_num}: {e}")
                
                # Convert date string to datetime object
                if 'date' in doc and doc['date']:
                    try:
                        # Try parsing RFC 2822 date format (standard email date format)
                        doc['date'] = parsedate_to_datetime(doc['date'])
                    except (TypeError, ValueError) as e:
                        # Keep as string if parsing fails
                        print(f"  Warning: Failed to parse date on line {line_num}: {e}")
                
                # Add tag field with inbox directory name
                doc['tag'] = tag
                
                documents.append(doc)
            except json.JSONDecodeError as e:
                print(f"  Warning: Failed to parse line {line_num}: {e}")
                continue
    
    # Insert documents into MongoDB
    if documents:
        try:
            # Use insert_many with ordered=False to continue on duplicate key errors
            result = collection.insert_many(documents, ordered=False)
            inserted_count = len(result.inserted_ids)
            total_loaded += inserted_count
            print(f"  Inserted {inserted_count} document(s)")
        except Exception as e:
            # Handle duplicate key errors (documents with same _id)
            if hasattr(e, 'details') and 'writeErrors' in e.details:
                inserted_count = e.details.get('nInserted', 0)
                total_loaded += inserted_count
                duplicate_count = len(e.details['writeErrors'])
                print(f"  Inserted {inserted_count} document(s), skipped {duplicate_count} duplicate(s)")
            else:
                print(f"  Error inserting documents: {e}")
    else:
        print(f"  No valid documents found in file")

print(f"\n{'='*60}")
print(f"Total documents loaded: {total_loaded}")
print(f"Database: mbox")
print(f"Collection: emails")
print(f"{'='*60}")

# Close connection
client.close()
