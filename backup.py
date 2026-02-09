# This script backs up the MongoDB set up using mongodump. It assumes that mongodump is installed and available in the system's PATH.
# It backs up the auto-embeddings and the view created for the auto-embedding search index.
# Data: mbox.emails
# Index definitions: __mdb_internal_search.indexCatalog
# Embeddings: __mdb_internal_search.<indexId>
import json
import os
import subprocess
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()
# Get MongoDB connection string from environment variable
MONGODB_URI = os.getenv('MONGODB_URI')
if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable not found. Please set it in your .env file") 
# Define backup directory
backup_dir = 'mongodb_backup'
# Create backup directory if it doesn't exist
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)
# Define mongodump command
mongodump_cmd = [
    'mongodump',
    '--uri', MONGODB_URI,
    '--out', backup_dir,
    '--db', 'mbox',
    '--gzip'
]

mongodump_internal_cmd = [
    'mongodump',
    '--uri', MONGODB_URI,
    '--out', backup_dir,
    '--gzip',
    '--db', '__mdb_internal_search',
]
# Get the index catalog to find the indexId for the auto-embedding search index
print("Getting index catalog to find search index...")
get_index_catalog_cmd = [
    'mongoexport',
    '--uri', MONGODB_URI,
    '--quiet',
    '--collection', 'indexCatalog',
    '--db', '__mdb_internal_search',
    '--query', '{"definition.database":"mbox","definition.lastObservedCollectionName":"emails"}'
]
try:
    result = subprocess.run(get_index_catalog_cmd, check=True, capture_output=True, text=True)
    print(result)
    search_index = json.loads(result.stdout)
    if not search_index:
        print("Search index not found in index catalog.")
        exit(1)
    index_id = str(search_index['indexId']['$oid'])
    print(f"Found search index with indexId: {index_id}")
    # Add the specific collection for the auto-embedding search index to the mongodump command
    mongodump_internal_cmd.extend(['--collection', index_id])
except subprocess.CalledProcessError as e:
    print(f"Error getting index catalog: {e}")
    exit(1)

# Run mongodump command
print(f"Running mongodump to back up MongoDB to {backup_dir}...")
try:
    subprocess.run(mongodump_cmd, check=True)
    print("Backup completed successfully.")
    subprocess.run(mongodump_internal_cmd, check=True)
    print("Backup of internal embeddings completed successfully.")
    mongodump_internal_cmd.extend(['--collection', 'indexCatalog'])
    subprocess.run(mongodump_internal_cmd, check=True)
    print("Backup of index catalog completed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Error during backup: {e}")

