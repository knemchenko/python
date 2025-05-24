#!/bin/bash

set -e # Exit on error

# --- Configuration ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )" # Assumes script is in project_root/scripts
ENV_FILE="$PROJECT_ROOT/.env"

# Default values
UPLOAD_FOLDER_DEFAULT="data/uploads" # Relative to project root
ZIP_RETENTION_DAYS_DEFAULT=365

# Load from .env if it exists
if [ -f "$ENV_FILE" ]; then
  # Use grep and cut to parse simple VAR=VAL lines. Handles missing vars.
  # More robust .env parsing is complex in bash, keep it simple.
  # Source the .env file to get variables. This is generally safer than parsing if .env is trusted.
  # However, be cautious if .env can contain arbitrary commands.
  # For this specific case, we expect simple VAR=VAL.
  # Using grep as specified in the prompt.
  CONFIGURED_UPLOAD_FOLDER_ENV=$(grep -E '^UPLOAD_FOLDER=' "$ENV_FILE" | cut -d'=' -f2-)
  CONFIGURED_RETENTION_DAYS_ENV=$(grep -E '^ZIP_RETENTION_DAYS=' "$ENV_FILE" | cut -d'=' -f2-)
  echo "Loaded configuration from $ENV_FILE"
else
  echo "No .env file found at $ENV_FILE. Using default or command-line configurations."
fi

# Determine effective configuration (CLI args override .env, which overrides defaults)
# Ensure that empty strings from .env parsing don't override defaults incorrectly.
# Use parameter expansion: ${VAR:-default} uses default if VAR is unset or null.
# ${VAR} alone might be empty if VAR was `VAR=` in .env.

ARG_RETENTION_DAYS=$1
ARG_UPLOAD_FOLDER_REL=$2 # This will be the second argument if provided

# Priority: CLI > .env > Default
if [ -n "$ARG_RETENTION_DAYS" ]; then
    EFFECTIVE_RETENTION_DAYS="$ARG_RETENTION_DAYS"
elif [ -n "$CONFIGURED_RETENTION_DAYS_ENV" ]; then
    EFFECTIVE_RETENTION_DAYS="$CONFIGURED_RETENTION_DAYS_ENV"
else
    EFFECTIVE_RETENTION_DAYS="$ZIP_RETENTION_DAYS_DEFAULT"
fi

if [ -n "$ARG_UPLOAD_FOLDER_REL" ]; then
    EFFECTIVE_UPLOAD_FOLDER_REL="$ARG_UPLOAD_FOLDER_REL"
elif [ -n "$CONFIGURED_UPLOAD_FOLDER_ENV" ]; then
    EFFECTIVE_UPLOAD_FOLDER_REL="$CONFIGURED_UPLOAD_FOLDER_ENV"
else
    EFFECTIVE_UPLOAD_FOLDER_REL="$UPLOAD_FOLDER_DEFAULT"
fi


# Ensure UPLOAD_FOLDER is an absolute path or relative to project root
if [[ "$EFFECTIVE_UPLOAD_FOLDER_REL" != /* ]]; then
  EFFECTIVE_UPLOAD_FOLDER="$PROJECT_ROOT/$EFFECTIVE_UPLOAD_FOLDER_REL"
else
  EFFECTIVE_UPLOAD_FOLDER="$EFFECTIVE_UPLOAD_FOLDER_REL"
fi

echo "--- ZIP File Retention Policy ---"
echo "Effective Retention Days: $EFFECTIVE_RETENTION_DAYS"
echo "Effective Upload Folder: $EFFECTIVE_UPLOAD_FOLDER"
echo "Current time: $(date)"

if [ ! -d "$EFFECTIVE_UPLOAD_FOLDER" ]; then
  echo "Error: Upload folder '$EFFECTIVE_UPLOAD_FOLDER' does not exist. Exiting."
  exit 1
fi

# --- Delete old ZIP files ---
echo "Searching for ZIP files older than $EFFECTIVE_RETENTION_DAYS days in $EFFECTIVE_UPLOAD_FOLDER..."
# The -mtime +N means older than N+1 days. So for "older than 365 days", use +364.
DAYS_FOR_FIND=$((EFFECTIVE_RETENTION_DAYS - 1))
if [ "$DAYS_FOR_FIND" -lt 0 ]; then # Handles retention_days = 0 or 1
    DAYS_FOR_FIND=0 # Delete files modified more than 0 days ago (i.e. yesterday or older if retention is 1)
                    # If retention is 0, this deletes all files not modified "today".
fi

# Find and delete old ZIP files. Store paths of deleted files' parent dirs for cleanup.
DELETED_PARENT_DIRS=()
# Use process substitution and a while loop to read filenames safely, even those with spaces.
# The find command with -print0 and read -d $'\0' is safer for arbitrary filenames.
# However, given typical panel/version names, spaces are less likely. Sticking to newline separation for now.
while IFS= read -r file_to_delete; do
    if [ -z "$file_to_delete" ]; then # Skip empty lines if any
        continue
    fi
    echo "Deleting old ZIP file: $file_to_delete (modified: $(stat -c %y "$file_to_delete"))"
    # Real deletion:
    rm "$file_to_delete"
    # Store parent dir
    DELETED_PARENT_DIRS+=("$(dirname "$file_to_delete")")
done < <(find "$EFFECTIVE_UPLOAD_FOLDER" -name "*.zip" -type f -mtime +"$DAYS_FOR_FIND")


# --- Clean up empty directories ---
# Deduplicate and sort parent directories, deepest first for safe removal
# Using sort -r to get deeper paths first.
UNIQUE_PARENT_DIRS=($(printf "%s\n" "${DELETED_PARENT_DIRS[@]}" | sort -ur))

if [ ${#UNIQUE_PARENT_DIRS[@]} -gt 0 ]; then
    echo "Checking for empty version and panel directories..."
    for dir_path in "${UNIQUE_PARENT_DIRS[@]}"; do
        # Ensure dir_path is not empty and is a directory
        if [ -n "$dir_path" ] && [ -d "$dir_path" ]; then
            # Check if it's a 'version' directory (e.g., .../panel_name/version_str)
            # This check is heuristic: checks if parent is not the UPLOAD_FOLDER root and current dir is empty
            if [ "$dir_path" != "$EFFECTIVE_UPLOAD_FOLDER" ] && [ -z "$(ls -A "$dir_path")" ]; then # Check if directory is empty
                echo "Removing empty version directory: $dir_path"
                rmdir "$dir_path"
                # Now check and try to remove parent 'panel' directory if it also became empty
                panel_dir_path=$(dirname "$dir_path")
                # Ensure panel_dir_path is not empty, is a directory, and not the root upload folder
                if [ -n "$panel_dir_path" ] && [ -d "$panel_dir_path" ] && [ "$panel_dir_path" != "$EFFECTIVE_UPLOAD_FOLDER" ] && [ -z "$(ls -A "$panel_dir_path")" ]; then
                    echo "Removing empty panel directory: $panel_dir_path"
                    rmdir "$panel_dir_path"
                fi
            fi
        fi
    done
fi

echo "Purge script completed."
