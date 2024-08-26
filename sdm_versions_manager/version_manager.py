# This script manages the logic for checking if new versions of data models are available.
# It interacts with the GitHub API to determine if there have been updates to the data models since the last run.
# If new versions are detected, it inserts the new version information into the MongoDB database.

# Next Steps: It can also handle any additional logic related to version management, 
# such as logging updates to WDME or notifying users of data models from WDME.

import os
import requests
import re
from database import insert_data_to_mongo, get_existing_versions
from dotenv import load_dotenv
import logging
from datetime import datetime


# Load environment variables
load_dotenv()


# Logging set up 
os.makedirs('logs', exist_ok=True)

logging.basicConfig(filename='logs/version_updates.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


GITHUB_API_URL = "https://api.github.com/repos/smart-data-models"
HEADERS = {
    "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
    "Accept": "application/vnd.github.v3+json"
}


def fetch_latest_versions(data_model_list):
    """Fetch the latest versions of data models from GitHub."""
    latest_versions = []

    for subject, data_model in data_model_list:
        repo_name = f"dataModel.{subject}"
        url = f"{GITHUB_API_URL}/{repo_name}/commits?path={data_model}/schema.json"

        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            commits = response.json()

            if commits:
                latest_commit = commits[0]  # Get the most recent commit
                commit_hash = latest_commit['sha']
                commit_date = latest_commit['commit']['committer']['date']

                # Fetch the schema content from the latest commit
                schema_url = f"https://raw.githubusercontent.com/smart-data-models/{repo_name}/{commit_hash}/{data_model}/schema.json"
                schema_response = requests.get(schema_url)
                schema_response.raise_for_status()
                schema_content = schema_response.text

                # Extract the schema version
                version_line = next(
                    (line for line in schema_content.splitlines() if "$schemaVersion" in line),
                    None
                )
                if version_line:
                    match = re.search(r'"\$schemaVersion"\s*:\s*"([^"]+)"', version_line)
                    current_version = match.group(1) if match else None

                    if current_version:
                        latest_versions.append({
                            "subject": subject,
                            "dataModel": data_model,
                            "version": current_version,
                            "schemaLink": f"https://github.com/smart-data-models/dataModel.{subject}/blob/master/{data_model}/schema.json",
                            "commitHash": commit_hash,
                            "commitDate": commit_date
                        })

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from GitHub for {subject}/{data_model}: {e}")

    return latest_versions

def update_database_with_new_versions(data_model_list):
    """Check for new versions and update the MongoDB database."""
    latest_versions = fetch_latest_versions(data_model_list)
    update_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates_made = False

    logging.info(f"Version check started at {update_date}")

    for version_info in latest_versions:
        # Check if the version already exists in the database
        existing_version = get_existing_versions(version_info["subject"], version_info["dataModel"])

        if existing_version:
            # Compare the existing version with the latest version
            # exisiting_version: latest version of data model already in database
            # version_info: current version on GitHub
            if existing_version['version'] != version_info['version']:
                insert_data_to_mongo([version_info])  # Insert as a list
                log_message = f"Updated {version_info['dataModel']} from version {existing_version['version']} to {version_info['version']}"
                print(log_message)
                logging.info(log_message)
                updates_made = True
        else:
            # If no existing version, insert the new version
            insert_data_to_mongo([version_info])
            log_message = f"Inserted new version: {version_info['version']} for {version_info['dataModel']}"
            print(log_message)
            logging.info(log_message)
            updates_made = True

        if not updates_made:
            logging.info("No updates were necessary. All versions are current.")

        logging.info(f"Version check completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("-" * 50)  # Separator line for readability


if __name__ == "__main__":
    import json

    # Load the data models from the config file
    with open('sdm_versions_manager/config.json', 'r') as config_file:
        config = json.load(config_file)
        data_models_list = config.get('data_models', [])

    # Update the database with new versions
    update_database_with_new_versions(data_models_list)