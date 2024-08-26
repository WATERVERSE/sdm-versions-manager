# Contains functions to connect to MongoDB, create the database, and perform CRUD operations.

from pymongo import MongoClient
import os


# Load MongoDB connection details from environment variables or configuration
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')
COLLECTION_NAME = os.getenv('COLLECTION_NAME')


def document_exists(data):
    """Check if a document exists in the database based on subject, dataModel, and version.

    Args:
        data (dict): A dictionary containing the document data to check.

    Returns:
        bool: True if the document exists, False otherwise.
    """
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    filter = {
        "subject": data["subject"],
        "dataModel": data["dataModel"],
        "version": data["version"]
    }

    existing_document = collection.find_one(filter)
    client.close()

    return existing_document is not None


def insert_data_to_mongo(data):
    """Insert parsed data into MongoDB if it doesn't already exist."""

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    inserted_count = 0
    for document in data:
        if not document_exists(document):
            try:
                collection.insert_one(document)
                inserted_count += 1
            except Exception as e:
                print(f"An error occurred while inserting data into MongoDB: {e}")
    
    client.close()
    print(f"Inserted {inserted_count} unique documents into MongoDB.")


def get_existing_versions(subject, data_model):
    """Retrieve the existing version of a data model from the database.

    Args:
        subject (str): The subject of the data model.
        data_model (str): The name of the data model.

    Returns:
        dict: The existing version document, or None if not found.
    """
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    filter = {
        "subject": subject,
        "dataModel": data_model
    }

    existing_document = collection.find_one(filter)
    client.close()

    return existing_document