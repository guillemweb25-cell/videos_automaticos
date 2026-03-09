#!/bin/bash

# Load environment variables safely
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo ".env file not found!"
    exit 1
fi

# Check if required remote variables are set
if [ -z "$REMOTE_SSH_USER" ] || [ -z "$REMOTE_SSH_HOST" ] || [ -z "$REMOTE_SSH_PORT" ]; then
    echo "Error: Remote sync variables (REMOTE_SSH_*) not found in .env"
    echo "Please add them from .env.example"
    exit 1
fi

REMOTE_SSH="$REMOTE_SSH_USER@$REMOTE_SSH_HOST"
REMOTE_PORT_SSH=$REMOTE_SSH_PORT

echo "--- Starting Sync: Server -> Laptop ---"

# 1. Sync Cache
echo "Step 1: Synchronizing cache from server..."
# Use --no-o --no-g to avoid permission errors locally
rsync -avz --no-o --no-g --exclude="*.mp4" -e "ssh -p $REMOTE_PORT_SSH" $REMOTE_SSH:$REMOTE_BASE_PATH/cache/ cache/

# 2. Sync YouTube Credentials
echo "Step 2: Synchronizing YouTube credentials from server..."
rsync -avz --no-o --no-g -e "ssh -p $REMOTE_PORT_SSH" $REMOTE_SSH:$REMOTE_BASE_PATH/youtube_creds/ youtube_creds/

# 3. Sync Database
echo "Step 3: Synchronizing database from server..."
# Check if local DB is running
if ! docker ps | grep -q "videos_automaticos-db-1"; then
    echo "Error: Local database container (videos_automaticos-db-1) is not running!"
    exit 1
fi

# Export remote DB (using videos_automaticos-db-1 for remote)
DATE=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="/tmp/db_pull_$DATE.sql"

echo "Exporting remote database..."
if ! ssh -p $REMOTE_PORT_SSH $REMOTE_SSH "docker exec videos_automaticos-db-1 mariadb-dump -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE" > $DUMP_FILE; then
    echo "Error: Failed to export remote database!"
    rm -f $DUMP_FILE
    exit 1
fi

# Import to local DB
echo "Importing to local database..."
if ! cat $DUMP_FILE | docker exec -i videos_automaticos-db-1 mariadb -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE; then
    echo "Error: Failed to import to local database!"
    rm -f $DUMP_FILE
    exit 1
fi

# Cleanup
rm $DUMP_FILE

echo "--- Sync Complete! ---"
