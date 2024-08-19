# A script specifically for populating the database with existing data model versions based on commit history.

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
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

def construct_schema_link(subject, data_model):
    # Construct the GitHub link to the schema.json file
    base_url = "https://github.com/smart-data-models"
    repo_name = f"dataModel.{subject}"
    return f"{base_url}/{repo_name}/blob/master/{data_model}/schema.json"

def get_commits_from_github(subject, data_model):
    # Construct the API URL for the commits
    repo_name = f"dataModel.{subject}"
    url = f"https://api.github.com/repos/smart-data-models/{repo_name}/commits?path={data_model}/schema.json"
    
    headers = {
        "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github.v3+json"
    }

    all_commits = []
    page = 1

    while True:
        # Add pagination to the request
        response = requests.get(f"{url}&page={page}", headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        commits = response.json()

        if not commits:  # Break the loop if there are no more commits
            break

        all_commits.extend(commits)
        page += 1  # Move to the next page

    return all_commits, repo_name  # Return all commits and the repo name

def parse_commits(data_model_list):
    json_payload = []

    # Iterate through each subject and data model pair
    for subject, data_model in data_model_list:
        commits, repo_name = get_commits_from_github(subject, data_model)

        # Initialize variables to track the last version and subject
        last_version = None
        last_subject = None

        # Iterate over the commits
        for commit in commits:
            commit_hash = commit['sha']
            commit_date = commit['commit']['committer']['date']

            # Fetch commit details to get the list of files changed
            commit_details_url = f"https://api.github.com/repos/smart-data-models/{repo_name}/commits/{commit_hash}"
            commit_details_response = requests.get(commit_details_url, headers={
                "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
                "Accept": "application/vnd.github.v3+json"
            })
            commit_details_response.raise_for_status()
            commit_details = commit_details_response.json()

            # Check if schema.json is in the list of changed files
            files_changed = commit_details.get('files', [])
            for file in files_changed:
                if file['filename'] == f"{data_model}/schema.json":
                    # Fetch the schema.json content from the commit
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
                        # Use a regular expression to extract the version number
                        match = re.search(r'"\$schemaVersion"\s*:\s*"([^"]+)"', version_line)
                        if match:
                            current_version = match.group(1)

                        # Check if the data model has not changed and the version has changed
                        if last_subject == subject and last_version != current_version:
                            json_payload.append({
                                "subject": subject,
                                "datamodel": data_model,
                                "version": current_version,
                                "schema.json_link": construct_schema_link(subject, data_model),
                                "commit_hash": commit_hash,
                                "commit_date": commit_date
                            })

                        # Update the last version and subject
                        last_version = current_version
                        last_subject = subject

    return json.dumps(json_payload, indent=4)

# List of waterverse data models to check
data_models_list = [
    ["Weather", "WeatherAlert"],
    ["WaterDistribution", "WaterDistributionNetwork"],
    ["Environment", "WaterObserved"],
    ["Agrifood", "AgriSoil"],
    ["Environment", "PhreaticObserved"],
    ["Environment", "FloodMonitoring"],
    ["WaterDistributionManagementEPANET", "Pipe"],
    ["WaterDistributionManagementEPANET", "Pump"],
    ["WaterDistributionManagementEPANET", "Valve"],
    ["WaterDistributionManagementEPANET", "Junction"],
    ["WaterQuality", "WaterQualityObserved"],
    ["WaterConsumption", "WaterConsumptionObserved"],
    ["Weather", "WeatherObserved"],
    ["WaterQuality", "WaterQualityPredicted"],
    ["Environment", "EnvironmentObserved"]
]

# Running the function and storing the result
result_json = parse_commits(data_models_list)

# Print the final result
print(result_json)