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
#    "schemaLink": "",
#    "commitDate"
#    "commitHash": "",
#}

import os
import re
import json
import requests
import logging
from dotenv import load_dotenv

from database import insert_data_to_mongo


# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants for GitHub API
GITHUB_BASE_URL = "https://github.com/smart-data-models"
GITHUB_API_URL = "https://api.github.com/repos/smart-data-models"
HEADERS = {
    "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
    "Accept": "application/vnd.github.v3+json"
}

def load_config(config_file) -> dict:
    """Load configuration from a JSON file containing the data models and subjects."""
    
    with open(config_file, 'r') as file:
        return json.load(file)


def construct_schema_link(subject, data_model):
    """Construct the GitHub link to the schema.json file."""

    base_url = "https://github.com/smart-data-models"
    repo_name = f"dataModel.{subject}"
    return f"{base_url}/{repo_name}/blob/master/{data_model}/schema.json"


def get_commits_from_github(subject, data_model):
    """Fetch commit history from GitHub for a data model."""

    repo_name = f"dataModel.{subject}"
    url = f"{GITHUB_API_URL}/{repo_name}/commits?path={data_model}/schema.json"
    
    all_commits = []
    page = 1

    while True:
        try:
            response = requests.get(f"{url}&page={page}", headers=HEADERS)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching commits: {e}")
            return [], repo_name

        commits = response.json()
        if not commits:
            break

        all_commits.extend(commits)
        page += 1

    return all_commits, repo_name


def parse_commits(data_model_list):
    """Parse commits for each data model to extract relevant information 
    when the schemaVersion changes in the commit changed files."""
    
    json_payload = []

    # Iterate through each subject and data model pair in the provided list
    for subject, data_model in data_model_list:
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
                commit_details_response = requests.get(commit_details_url, headers=HEADERS)
                commit_details_response.raise_for_status()  
                commit_details = commit_details_response.json()
            except requests.exceptions.RequestException as e:
                # Log errors while fetching commit details
                logging.error(f"Error fetching commit details: {e}")
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
                        schema_response = requests.get(schema_url)
                        schema_response.raise_for_status() 
                        schema_content = schema_response.text 
                    except requests.exceptions.RequestException as e:
                        # Log any errors encountered while fetching schema content
                        logging.error(f"Error fetching schema content: {e}")
                        continue  # Skip to the next file if an error occurs

                    # Look for the line in the schema content that contains the schemaVersion
                    version_line = next(
                        (line for line in schema_content.splitlines() if "$schemaVersion" in line),
                        None  # Default to None if no such line is found
                    )
                    if version_line:
                        # Use a regular expression to extract the version number from the line
                        match = re.search(r'"\$schemaVersion"\s*:\s*"([^"]+)"', version_line)
                        current_version = match.group(1) if match else None  # Get the version if found

                        # Check if the subject has not changed and the version has changed
                        if last_subject == subject and last_version != current_version:
                            # Append the relevant information to the JSON payload
                            json_payload.append({
                                "subject": subject,
                                "dataModel": data_model,
                                "version": current_version,
                                "schemaLink": construct_schema_link(subject, data_model),
                                "commitHash": commit_hash,
                                "commitDate": commit_date
                            })

                        # Update the last version and subject to the current values
                        last_version = current_version
                        last_subject = subject

    return json.dumps(json_payload, indent=4)


def main():

    config = load_config("sdm_versions_manager/config.json")
    data_models_list = config.get('data_models', [])

    result_json = parse_commits(data_models_list)

    # Insert data into MongoDB
    insert_data_to_mongo(json.loads(result_json))  # Call the function to insert data

    # Print the final result
    logging.info("Commit data has been written to %s and inserted into MongoDB.")

if __name__ == "__main__":
    main()