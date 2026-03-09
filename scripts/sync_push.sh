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

echo "--- Starting Sync: Laptop -> Server ---"

# 1. Sync Cache
echo "Step 1: Synchronizing cache..."
# Using -rtvz and disabling times/perms preservation to avoid permission issues on remote
rsync -rtvz --no-o --no-g --no-perms --no-t --exclude="*.mp4" -e "ssh -p $REMOTE_PORT_SSH" cache/ $REMOTE_SSH:$REMOTE_BASE_PATH/cache/

# 2. Sync YouTube Credentials
echo "Step 2: Synchronizing YouTube credentials..."
rsync -rtvz --no-o --no-g --no-perms --no-t -e "ssh -p $REMOTE_PORT_SSH" backend/youtube_creds/ $REMOTE_SSH:$REMOTE_BASE_PATH/backend/youtube_creds/

# 3. Sync Database
echo "Step 3: Synchronizing database..."
# Check if local DB is running
if ! docker ps | grep -q "videos_automaticos-db-1"; then
    echo "Error: Local database container (videos_automaticos-db-1) is not running!"
    exit 1
fi

# Export local DB
DATE=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="/tmp/db_dump_$DATE.sql"

echo "Exporting local database..."
if ! docker exec videos_automaticos-db-1 mariadb-dump -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE > $DUMP_FILE; then
    echo "Error: Failed to export local database!"
    rm -f $DUMP_FILE
    exit 1
fi

# Upload and import to remote DB
echo "Uploading and importing to remote database..."
if ! cat $DUMP_FILE | ssh -p $REMOTE_PORT_SSH $REMOTE_SSH "docker exec -i videos_automaticos-db-1 mariadb -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE"; then
    echo "Error: Failed to import to remote database!"
    rm -f $DUMP_FILE
    exit 1
fi

# Cleanup
rm $DUMP_FILE

echo "--- Sync Complete! ---"
