#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##
# Copyright 2024 FIWARE Foundation, e.V.
#
# This file is part of SDM Quality Testing
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


from fastapi import FastAPI, HTTPException, Request, status
from dotenv import dotenv_values
from pymongo import MongoClient
from contextlib import asynccontextmanager


config = dotenv_values(dotenv_path="../.env")


# Define a lifespan context manager
@asynccontextmanager
async def lifespan(app):
    # Startup logic
    app.mongodb_client = MongoClient(config["MONGO_URI"])
    app.database = app.mongodb_client[config["DB_NAME"]]
    print("Connected to the MongoDB database!")

    # Yield control back to the application
    yield

    # Shutdown logic
    app.mongodb_client.close()
    print("Disconnected from the MongoDB database!")


app = FastAPI(lifespan=lifespan, title="SDM versions manager")

@app.get("/")
async def root():
    return {"message: This is the SDM version manager api."}


@app.get("/datamodel/{name}/versions", response_description="Get all the versions of a data model", status_code=status.HTTP_200_OK)
def list_datamodel_versions(name: str):    
    collection = app.database["versions"]

    # Querying the database for all documents of the specified data model name
    data_model_list = list(collection.find({"dataModel": name}))
    if not data_model_list:
        raise HTTPException(status_code=404, detail="Data model not found in the database")
    
    # Extracting only the version numbers from the documents
    versions = [model["version"] for model in data_model_list]
    
    return versions


@app.get("/datamodel/{name}/version/{version}", response_description="Get the schema URL of a data model at a particular version", status_code=status.HTTP_200_OK)
def get_schema(name: str, version: str):
    collection = app.database["versions"]
    
    # Querying the database for the specific data model and version
    result = collection.find_one({"dataModel": name, "version": version})
    
    if result is None:
        raise HTTPException(status_code=404, detail="Data model version not found in the database")

    # Prepare the response dictionary with version and schemaUrl
    response_data = {
        "version": result["version"],
        "schemaUrl": result["schemaUrl"],
    }
    
    return response_data
    
