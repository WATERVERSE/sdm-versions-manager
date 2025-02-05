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

# A script for populating the database with existing data model versions based on commit history.

# This script is designed to run independently. 
# It will take the name of the data model and subject as inputs and fetch the historical commit data 
# from the GitHub repository to populate the database with past versions. 
# This script can utilize the GitHub API to retrieve commit history and extract relevant information.


# SDMs versions data structure to fill the dataset with:
#json_data_db = {
#    "subject": "",
#    "dataModel": "",
#    "version": "",
#    "schemaUrl": "",
#    "commitDate"
#    "commitHash": "",
#}

from dotenv import load_dotenv
from datetime import datetime
from database import insert_data_to_mongo
from requests import get
from requests.exceptions import RequestException
from json import load, dumps, loads
from logging import info, warning, error, basicConfig, INFO
from time import time, sleep
from os import getenv, makedirs
from re import search
from tqdm import tqdm


# Load environment variables from .env file
load_dotenv()


# Logging setup
makedirs('logs', exist_ok=True)

basicConfig(filename='logs/initial_population.log', level=INFO,
            format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


# Constants for GitHub API
GITHUB_BASE_URL = "https://github.com/smart-data-models"
GITHUB_API_URL = "https://api.github.com/repos/smart-data-models"
HEADERS = {
    "Authorization": f"token {getenv('GITHUB_TOKEN')}",
    "Accept": "application/vnd.github.v3+json"
}

def load_config(config_file) -> dict:
    """
    Load configuration from a JSON file containing the data models and subjects.
    
    Args:
        config_file (str): The path to the JSON configuration file.

    Returns:
        dict: A dictionary containing the configuration data loaded from the JSON file.
    """
    
    with open(config_file, 'r') as file:
        return load(file)


def construct_mater_schema_link(subject, data_model):
    """
    Construct the GitHub link to the schema.json file in the Master branch.

    This function generates a URL pointing to the schema.json file in the master branch
    for a specific data model within the Smart Data Models repository on GitHub.

    Args:
        subject (str): The subject or domain of the data model (e.g., "Energy", "Environment").
        data_model (str): The name of the specific data model.

    Returns:
        str: A complete URL to the schema.json file on GitHub.
    
    """

    base_url = "https://github.com/smart-data-models"
    repo_name = f"dataModel.{subject}"
    return f"{base_url}/{repo_name}/blob/master/{data_model}/schema.json"


def get_commits_from_github(subject, data_model):
    """
    Fetch commit history from GitHub for a data model.

    This function retrieves the commit history for a given data model's schema.json file
    from the Smart Data Models GitHub repository. It handles pagination to fetch all commits.

    Args:
        subject (str): The subject or domain of the data model (e.g., "Energy", "Environment").
        data_model (str): The name of the specific data model.

    Returns:
        Tuple[List[dict], str]: A tuple containing two elements:
            - List[dict]: A list of dictionaries, each representing a commit. 
              Each dictionary contains commit details such as SHA, author, date, and message.
            - str: The name of the GitHub repository.
    
    Raises:
        requests.exceptions.RequestException: If there's an error in making the HTTP request.
    
    """

    repo_name = f"dataModel.{subject}"
    url = f"{GITHUB_API_URL}/{repo_name}/commits?path={data_model}/schema.json"
    
    all_commits = []
    page = 1

    while True:
        try:
            response = get(f"{url}&page={page}", headers=HEADERS)
            response.raise_for_status()

            # Check rate limit
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            if remaining <= 1:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                sleep_time = max(reset_time - time(), 0) + 1
                warning(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
                sleep(sleep_time)

            commits = response.json()
            if not commits:
                break

            all_commits.extend(commits)
            page += 1

        except RequestException as e:
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                sleep_time = max(reset_time - time(), 0) + 1
                warning(f"Rate limit exceeded. Sleeping for {sleep_time:.2f} seconds.")
                sleep(sleep_time)
                continue  # Retry the request
            else:
                error(f"Error fetching commits: {e}")
                return [], repo_name

    return all_commits, repo_name


def parse_commits(data_model_list):
    """
    Parse commits for each data model to extract relevant information 
    when the schemaVersion changes in the commit changed files.
    
    Args:
        data_model_list (List[List[str, str]]): A list of list, where each list contains
            two strings: the subject and the data model name.

    Returns:
        str: A JSON-formatted string containing an array of objects. Each object represents
             a schema version change and includes the following fields:
             - subject: The subject of the data model.
             - dataModel: The name of the data model.
             - version: The schema version.
             - schemaLink: A link to the schema file on GitHub.
             - commitHash: The hash of the commit where the version changed.
             - commitDate: The date of the commit.
    """
    
    json_payload = []

    # Iterate through each subject and data model pair in the provided list
    for subject, data_model in tqdm(data_model_list, desc="Data Models", ncols=80, colour='green'):
        # Fetch the commit history from GitHub for the current subject and data model
        commits, repo_name = get_commits_from_github(subject, data_model)

        last_version = None
        last_subject = None

        # Iterate over each commit in the fetched commit history
        for commit in commits:
            commit_hash = commit['sha']
            commit_date = commit['commit']['committer']['date']

            # Construct the URL to fetch detailed information about the commit
            commit_details_url = f"{GITHUB_API_URL}/{repo_name}/commits/{commit_hash}"
            try:
                # Send a request to get the commit details
                commit_details_response = get(commit_details_url, headers=HEADERS)
                commit_details_response.raise_for_status()  
                commit_details = commit_details_response.json()
            except RequestException as e:
                # Log errors while fetching commit details
                error(f"Error fetching commit details: {e}")
                continue  # Skip to the next commit if an error occurs

            # Get the list of files changed in the commit
            files_changed = commit_details.get('files', [])
            for file in files_changed:
                # Check if the changed file is the schema.json for the current data model
                if file['filename'] == f"{data_model}/schema.json":
                    # Construct the URL to fetch the schema.json content from the commit
                    schema_url = f"https://raw.githubusercontent.com/smart-data-models/{repo_name}/{commit_hash}/{data_model}/schema.json"
                    try:
                        # Send a request to get the schema content
                        schema_response = get(schema_url)
                        schema_response.raise_for_status() 
                        schema_content = schema_response.text 
                    except RequestException as e:
                        # Log any errors encountered while fetching schema content
                        error(f"Error fetching schema content: {e}")
                        continue  # Skip to the next file if an error occurs

                    # Look for the line in the schema content that contains the schemaVersion
                    version_line = next(
                        (line for line in schema_content.splitlines() if "$schemaVersion" in line),
                        None  # Default to None if no such line is found
                    )
                    if version_line:
                        # Use a regular expression to extract the version number from the line
                        match = search(r'"\$schemaVersion"\s*:\s*"([^"]+)"', version_line)
                        current_version = match.group(1) if match else None  # Get the version if found

                        # Check if the subject has not changed and the version has changed
                        if last_subject == subject and last_version != current_version:
                            # Append the relevant information to the JSON payload
                            json_payload.append({
                                "subject": subject,
                                "dataModel": data_model,
                                "version": current_version,
                                "schemaUrl": schema_url,
                                "commitHash": commit_hash,
                                "commitDate": commit_date
                            })

                        # Update the last version and subject to the current values
                        last_version = current_version
                        last_subject = subject

    return dumps(json_payload, indent=4)


def main():
    """Main function to execute the script."""
    start_time = datetime.now()
    info(f"Starting initial population at {start_time}")

    config = load_config("config.json")
    data_models_list = config.get('data_models', [])

    info(f"Loaded {len(data_models_list)} data models from configuration")

    result_json = parse_commits(data_models_list)

    # Insert data into MongoDB
    insert_data_to_mongo(loads(result_json))  # Call the function to insert data
    info("Inserted versions data into MongoDB")

    end_time = datetime.now()
    duration = end_time - start_time
    info(f"Initial population completed at {end_time}")
    info(f"Total duration: {duration}")
    info("-" * 50)  # Add a separator line for readability


if __name__ == "__main__":
    main()
