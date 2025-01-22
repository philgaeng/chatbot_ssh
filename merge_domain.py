import yaml
import glob
import os

# Path to the domain directory
DOMAIN_DIR = "./domain"

# List all YAML files in the domain directory
yaml_files = glob.glob(os.path.join(DOMAIN_DIR, "*.yml"))

# Initialize an empty dictionary for the merged domain
merged_domain = {}

# Iterate through each YAML file and merge contents
for file in yaml_files:
    with open(file, "r") as f:
        content = yaml.safe_load(f)
        for key, value in content.items():
            if key in merged_domain:
                if isinstance(merged_domain[key], list) and isinstance(value, list):
                    merged_domain[key].extend(value)
                elif isinstance(merged_domain[key], dict) and isinstance(value, dict):
                    merged_domain[key].update(value)
            else:
                merged_domain[key] = value

# Add the version field explicitly (assuming version "3.1")
merged_domain["version"] = "3.1"

# Write the merged content to domain.yml
with open("domain.yml", "w") as f:
    yaml.dump(merged_domain, f, sort_keys=False)