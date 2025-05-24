#!/bin/bash

set -e # Exit on error, consider `set -u` for unset variables too

# --- Configuration ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
ENV_FILE="$PROJECT_ROOT/.env"

# Default DB connection values
DB_HOST_DEFAULT="localhost"
DB_PORT_DEFAULT="5432"
DB_USER_DEFAULT="aqua"
DB_PASS_DEFAULT="password"
DB_NAME_DEFAULT="aqua_tests_db"
BACKUP_DIR_DEFAULT="/var/backups/aqua" # Standard backup location

# Load from .env if it exists
# Use parameter expansion for defaults if variables are not found or empty
if [ -f "$ENV_FILE" ]; then
  echo "Loading configuration from $ENV_FILE"
  # Source the .env file in a subshell to avoid polluting the current environment
  # and to handle potential errors or complex values in .env more gracefully.
  # This is generally safer than manual parsing for simple VAR=VAL.
  # However, for strict VAR=VAL and to avoid sourcing, grep is used as per prompt example.
  
  # Ensure that if grep finds nothing, the default is used.
  # The "|| echo" part in the prompt's example is problematic as it assigns the literal string "echo default"
  # if the var is not found. Correct parsing with grep is tricky for empty values vs. unset.
  # A slightly better grep approach:
  TEMP_DB_HOST=$(grep -E '^POSTGRES_HOST=' "$ENV_FILE" | cut -d'=' -f2-)
  TEMP_DB_PORT=$(grep -E '^POSTGRES_PORT=' "$ENV_FILE" | cut -d'=' -f2-)
  TEMP_DB_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d'=' -f2-)
  TEMP_DB_PASS=$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2-)
  TEMP_DB_NAME=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d'=' -f2-)
  TEMP_BACKUP_DIR=$(grep -E '^BACKUP_DIR=' "$ENV_FILE" | cut -d'=' -f2-)

  DB_HOST=${TEMP_DB_HOST:-$DB_HOST_DEFAULT}
  DB_PORT=${TEMP_DB_PORT:-$DB_PORT_DEFAULT}
  DB_USER=${TEMP_DB_USER:-$DB_USER_DEFAULT}
  DB_PASS=${TEMP_DB_PASS:-$DB_PASS_DEFAULT}
  DB_NAME=${TEMP_DB_NAME:-$DB_NAME_DEFAULT}
  BACKUP_DIR=${TEMP_BACKUP_DIR:-$BACKUP_DIR_DEFAULT}
else
  DB_HOST=$DB_HOST_DEFAULT
  DB_PORT=$DB_PORT_DEFAULT
  DB_USER=$DB_USER_DEFAULT
  DB_PASS=$DB_PASS_DEFAULT
  DB_NAME=$DB_NAME_DEFAULT
  BACKUP_DIR=$BACKUP_DIR_DEFAULT
  echo "No .env file found at $ENV_FILE. Using default database connection parameters and backup directory."
fi

# Allow backup directory override via CLI argument
EFFECTIVE_BACKUP_DIR=${1:-$BACKUP_DIR} # Use $BACKUP_DIR which now holds .env or default

echo "--- Database Backup Script ---"
echo "Backup Directory: $EFFECTIVE_BACKUP_DIR"
echo "Database: $DB_NAME on $DB_HOST:$DB_PORT"
echo "Current time: $(date)"

# Create backup directory if it doesn't exist
# This command will try to create parent directories as needed.
# It will not error if the directory already exists.
echo "Ensuring backup directory '$EFFECTIVE_BACKUP_DIR' exists..."
mkdir -p "$EFFECTIVE_BACKUP_DIR"
if [ ! -d "$EFFECTIVE_BACKUP_DIR" ]; then
  echo "Error: Backup directory '$EFFECTIVE_BACKUP_DIR' could not be created. Check permissions. Exiting."
  exit 1
fi

# Basic check for pg_dump
if ! command -v pg_dump &> /dev/null; then
    echo "Error: pg_dump command not found. Please install PostgreSQL client tools."
    exit 1
fi
if ! command -v gzip &> /dev/null; then
    echo "Error: gzip command not found. Please install gzip."
    exit 1
fi


# --- Create new backup ---
TODAY=$(date +"%Y-%m-%d")
BACKUP_FILENAME="${TODAY}.sql.gz"
BACKUP_FILE_PATH="$EFFECTIVE_BACKUP_DIR/$BACKUP_FILENAME"

echo "Starting backup of database '$DB_NAME' to '$BACKUP_FILE_PATH'..."
export PGPASSWORD="$DB_PASS" # Set PGPASSWORD environment variable for pg_dump
# The actual pg_dump command. Shellcheck might warn about DB_PASS in PGPASSWORD.
# Using process substitution or other methods can be more secure if DB_PASS has special chars.
# For this context, direct env var is common.
if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --format=custom | gzip > "$BACKUP_FILE_PATH"; then
  echo "Backup created successfully: $BACKUP_FILE_PATH (format: custom, compressed)"
else
  # If pg_dump fails, it usually returns a non-zero exit code, caught by `set -e` or the if condition.
  echo "Error: Backup failed. Check pg_dump output or logs."
  # Remove potentially incomplete or empty backup file
  if [ -f "$BACKUP_FILE_PATH" ]; then
      rm "$BACKUP_FILE_PATH"
      echo "Removed incomplete backup file: $BACKUP_FILE_PATH"
  fi
  exit 1 # Explicitly exit if set -e is not relied upon or for clarity
fi
unset PGPASSWORD

# --- Retention Policy (7-1-1) ---
echo "Applying retention policy (7 daily, 1 previous month, 1 previous quarter)..."
cd "$EFFECTIVE_BACKUP_DIR" || { echo "Error: Could not change to backup directory '$EFFECTIVE_BACKUP_DIR'. Exiting."; exit 1; }


# List all .sql.gz files, sort them reverse chronologically (newest first by filename)
# This assumes YYYY-MM-DD naming makes ls -t (mtime sort) and filename sort equivalent for recent files.
# For robustness, especially if mtimes could be altered, parsing dates from names is better.
# However, `ls -t` is simpler. Let's use filename sort for date logic to be explicit on YYYY-MM-DD.
ALL_BACKUPS_UNSORTED=($(ls *.sql.gz 2>/dev/null))
# Sort by name descending (YYYY-MM-DD means newest first)
IFS=$'\n' ALL_BACKUPS=($(LC_ALL=C sort -r <<<"${ALL_BACKUPS_UNSORTED[*]}"))
unset IFS


# Files to keep
KEEP_FILES=()

# 1. Keep latest 7 daily backups
for ((i=0; i<7 && i<${#ALL_BACKUPS[@]}; i++)); do
  KEEP_FILES+=("${ALL_BACKUPS[i]}")
done

# 2. Keep 1 from previous month
PREV_MONTH_TARGET=$(date -d "last month" +"%Y-%m")
PREV_MONTH_BACKUP=""
# Iterate through all backups to find the newest one from the previous month
for backup_file in "${ALL_BACKUPS[@]}"; do
  if [[ "$backup_file" == "${PREV_MONTH_TARGET}"* ]]; then
    if [ -z "$PREV_MONTH_BACKUP" ] || [[ "$backup_file" > "$PREV_MONTH_BACKUP" ]]; then # > for string comparison of YYYY-MM-DD
        PREV_MONTH_BACKUP=$backup_file
    fi
  fi
done
if [ -n "$PREV_MONTH_BACKUP" ]; then
  KEEP_FILES+=("$PREV_MONTH_BACKUP")
fi


# 3. Keep 1 from previous quarter
CURRENT_MONTH_NUM=$(date +%m | sed 's/^0*//') # Remove leading zeros for arithmetic
CURRENT_YEAR=$(date +%Y)

PREV_Q_YEAR=$CURRENT_YEAR
declare -a PREV_Q_MONTHS_PATTERNS

# Determine previous quarter's months and year
if (( CURRENT_MONTH_NUM >= 1 && CURRENT_MONTH_NUM <= 3 )); then # Q1 -> Prev Q4 of Prev Year
  PREV_Q_YEAR=$((CURRENT_YEAR - 1))
  PREV_Q_MONTHS_PATTERNS=("${PREV_Q_YEAR}-10" "${PREV_Q_YEAR}-11" "${PREV_Q_YEAR}-12")
elif (( CURRENT_MONTH_NUM >= 4 && CURRENT_MONTH_NUM <= 6 )); then # Q2 -> Prev Q1
  PREV_Q_MONTHS_PATTERNS=("${PREV_Q_YEAR}-01" "${PREV_Q_YEAR}-02" "${PREV_Q_YEAR}-03")
elif (( CURRENT_MONTH_NUM >= 7 && CURRENT_MONTH_NUM <= 9 )); then # Q3 -> Prev Q2
  PREV_Q_MONTHS_PATTERNS=("${PREV_Q_YEAR}-04" "${PREV_Q_YEAR}-05" "${PREV_Q_YEAR}-06")
else # Q4 -> Prev Q3
  PREV_Q_MONTHS_PATTERNS=("${PREV_Q_YEAR}-07" "${PREV_Q_YEAR}-08" "${PREV_Q_YEAR}-09")
fi

PREV_QUARTER_BACKUP=""
for month_pattern in "${PREV_Q_MONTHS_PATTERNS[@]}"; do
  for backup_file in "${ALL_BACKUPS[@]}"; do # Iterate all existing backups
    if [[ "$backup_file" == "${month_pattern}"* ]]; then # If backup is from this month of the target quarter
      if [ -z "$PREV_QUARTER_BACKUP" ] || [[ "$backup_file" > "$PREV_QUARTER_BACKUP" ]]; then
          PREV_QUARTER_BACKUP=$backup_file
      fi
    fi
  done
done
if [ -n "$PREV_QUARTER_BACKUP" ]; then
  KEEP_FILES+=("$PREV_QUARTER_BACKUP")
fi

# Deduplicate KEEP_FILES (sort -u)
UNIQUE_KEEP_FILES=($(printf "%s\n" "${KEEP_FILES[@]}" | LC_ALL=C sort -u))

echo "Files to keep under retention policy:"
if [ ${#UNIQUE_KEEP_FILES[@]} -eq 0 ]; then
    echo " - None (this might happen if script just ran and no historical files match criteria yet)"
else
    for K_FILE in "${UNIQUE_KEEP_FILES[@]}"; do echo " - $K_FILE"; done
fi


# Delete files not in UNIQUE_KEEP_FILES
DELETED_COUNT=0
for B_FILE in "${ALL_BACKUPS_UNSORTED[@]}"; do # Iterate original unsorted list for deletion
  should_keep=0
  for K_FILE in "${UNIQUE_KEEP_FILES[@]}"; do
    if [[ "$B_FILE" == "$K_FILE" ]]; then
      should_keep=1
      break
    fi
  done
  if (( should_keep == 0 )); then
    echo "Deleting old backup (not in retention set): $B_FILE"
    rm "$B_FILE"
    DELETED_COUNT=$((DELETED_COUNT + 1))
  fi
done
echo "$DELETED_COUNT files deleted."

echo "Database backup and retention policy application completed."
