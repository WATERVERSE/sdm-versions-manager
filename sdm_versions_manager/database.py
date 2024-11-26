#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##
# Copyright 2024 FIWARE Foundation, e.V.
#
# This file is part of SDM Version Manager service
#
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
##

# Contains functions to connect to MongoDB, create the database, and perform CRUD operations.

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from os import getenv


# Load MongoDB connection details from environment variables or configuration
MONGO_URI = getenv('MONGO_URI')
DB_NAME = getenv('DB_NAME')
COLLECTION_NAME = getenv('COLLECTION_NAME')


def document_exists(data):
    """Check if a document exists in the database based on subject, dataModel, and version.

    Args:
        data (dict): A dictionary containing the document data to check.

    Returns:
        bool: True if the document exists, False otherwise.

    Raises:
        ConnectionError: If there's an issue connecting to the database.
    """
    client = None
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        filter = {
            "subject": data["subject"],
            "dataModel": data["dataModel"],
            "version": data["version"]
        }

        existing_document = collection.find_one(filter)
        return existing_document is not None

    except ConnectionFailure as e:
        # Handle connection errors
        raise ConnectionError(f"Failed to connect to the database: {str(e)}")

    finally:
        # Ensure the client is closed even if an exception occurs
        if client:
            client.close()


def insert_data_to_mongo(data):
    """Insert parsed data into MongoDB if it doesn't already exist.
    
    Args:
        data (list): A list of dictionaries, where each dictionary represents a document
                     to be inserted into the MongoDB collection.

    Returns:
        int: The number of documents successfully inserted into the collection.

    Raises:
        ConnectionError: If there's an issue connecting to the database.
    """

    client = None
    inserted_count = 0

    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        for document in data:
            if not document_exists(document):
                try:
                    collection.insert_one(document)
                    inserted_count += 1
                except OperationFailure as e:
                    print(f"An error occurred while inserting a document: {e}")

        return inserted_count

    except ConnectionFailure as e:
        raise ConnectionError(f"Failed to connect to the database: {str(e)}")

    finally:
        if client:
            client.close()
        print(f"Inserted {inserted_count} unique documents into MongoDB.")


def get_existing_versions(subject, data_model):
    """Retrieve the existing version of a data model from the database.

    Args:
        subject (str): The subject of the data model.
        data_model (str): The name of the data model.

    Returns:
        dict: The existing version document, or None if not found.

    Raises:
        ConnectionError: If there's an issue connecting to the database.
    """
    client = None
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        filter = {
            "subject": subject,
            "dataModel": data_model
        }

        existing_document = collection.find_one(filter)
        return existing_document

    except ConnectionFailure as e:
        raise ConnectionError(f"Failed to connect to the database: {str(e)}")

    finally:
        if client:
            client.close()
