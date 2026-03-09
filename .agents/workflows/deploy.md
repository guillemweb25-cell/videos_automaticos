---
description: how to sync and deploy to production
---

This workflow guides you through synchronizing your local laptop development with the production server at `5622enguillem.es`.

### 1. Synchronize Data (Cache & DB)

Use these commands to keep your data in sync.

#### Push to Server:
Use this when you have generated content (audio/images) or updated database records on your laptop and want them on the server.
// turbo
1. Run `./scripts/sync_push.sh`

#### Pull from Server:
Use this when you have generated content on the server and want to bring it back to your laptop for further development.
// turbo
1. Run `./scripts/sync_pull.sh`

### 2. Update Code (Git)

Your server always stays on the `main` branch.

1. On your laptop, merge your feature branch into `main`.
2. Push `main` to the remote repository (e.g., GitHub).
3. On the server, pull the latest changes:

### 3. Update Code on Server

1. SSH into the server: `ssh -p 5622 guillem@enguillem.es`
2. Pull the latest changes:
   ```bash
   git pull origin main
   ```
3. **Important**: If you are accessing from a new IP or domain, update the `CORS_ORIGINS` in your `.env` file on the server:
   ```bash
   nano .env
   # Add or update:
   # CORS_ORIGINS=http://localhost:8501,http://your-ip-or-domain:8501
   ```

### 4. Restart Production Services

If you changed environment variables or the `docker-compose.yml`, restart the services on the server:
1. SSH into the server: `ssh -p 5622 guillem@enguillem.es`
2. Restart using the helper script:
   ```bash
   ./scripts/start.sh
   ```
