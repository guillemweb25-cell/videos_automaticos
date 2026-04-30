import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import re
from typing import Dict, Any

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# Allow scope changes (Google sometimes returns scopes in different formats)
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

class YouTubeService:
    @staticmethod
    def get_creds_dir(channel_id: int, user_id: int, channel_name: str) -> Path:
        """Finds or creates the YouTube credentials directory within the channel's cache folder."""
        user_dir = Path("cache") / f"user_{user_id:04d}"
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Search for folder starting with ID (e.g., "0005-")
        pattern = f"{channel_id:04d}-*"
        matches = list(user_dir.glob(pattern))
        
        if matches:
            channel_dir = matches[0]
        else:
            from app.core.utils import slugify
            channel_dir = user_dir / f"{channel_id:04d}-{slugify(channel_name)}"
            channel_dir.mkdir(parents=True, exist_ok=True)
            
        creds_dir = channel_dir / "youtube_credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)
        print(f"[DEBUG] Creds dir for channel {channel_id}: {creds_dir}")
        return creds_dir

    def __init__(self, channel_id: int, user_id: int, channel_name: str):
        self.creds_dir = self.get_creds_dir(channel_id, user_id, channel_name)
        self.token_path = self.creds_dir / "token.json"
        self.secret_path = self.creds_dir / "client_secret.json"

    def get_credentials(self):
        creds = None
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                print(f"Error loading credentials from {self.token_path}: {e}")
                return None
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    from google.auth.exceptions import RefreshError
                    creds.refresh(Request())
                    self.token_path.write_text(creds.to_json())
                except RefreshError:
                    print(f"Token expired or revoked for {self.creds_dir}. Deleting invalid token.")
                    if self.token_path.exists():
                        self.token_path.unlink()
                    return None
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    return None
            else:
                return None
        return creds

    def get_auth_url(self, redirect_uri: str):
        """Generates the authorization URL for Google OAuth."""
        if not self.secret_path.exists():
            # Check if there's a global one
            global_secret = YOUTUBE_CREDS_BASE / "client_secret.json"
            if global_secret.exists():
                 # Copy it to the current dir for the flow
                 import shutil
                 shutil.copy(global_secret, self.secret_path)
            else:
                raise FileNotFoundError(f"Missing client_secret.json in {self.creds_dir}")
        
        # Read client_id directly to avoid PKCE auto-generation in google-auth-oauthlib
        with open(self.secret_path, 'r') as f:
            data = json.load(f)
            web_data = data.get('web') or data.get('installed')
            client_id = web_data['client_id']
            auth_uri = web_data['auth_uri']

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true"
        }
        import urllib.parse
        auth_url = f"{auth_uri}?{urllib.parse.urlencode(params)}"
        return auth_url

    def finish_oauth(self, code: str, redirect_uri: str):
        """Exchanges the auth code for a token and saves it."""
        print(f"[DEBUG] finish_oauth: Exchange code for channel {self.creds_dir.name} with redirect_uri: {redirect_uri}")
        # Use Flow only for the token exchange
        flow = Flow.from_client_secrets_file(
            str(self.secret_path), scopes=SCOPES, redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Save the credentials for the next run
        self.creds_dir.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
        return creds

    def is_authenticated(self):
        return self.get_credentials() is not None

    async def get_channel_info(self):
        creds = self.get_credentials()
        if not creds:
            return None
        
        youtube = build("youtube", "v3", credentials=creds)
        request = youtube.channels().list(part="snippet,statistics", mine=True)
        response = request.execute()
        
        if response.get("items"):
            return response["items"][0]
        return None

    async def get_videos(self, max_results=50, exclude_title_tags: list[str] | None = None):
        creds = self.get_credentials()
        if not creds:
            return []

        youtube = build("youtube", "v3", credentials=creds)
        # First get uploads playlist ID
        ch_request = youtube.channels().list(part="contentDetails", mine=True)
        ch_response = ch_request.execute()

        uploads_playlist_id = ch_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Paginate uploads playlist up to max_results
        video_ids: list[str] = []
        page_token = None
        remaining = max_results
        while remaining > 0:
            batch = min(50, remaining)
            playlist_response = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=batch,
                pageToken=page_token
            ).execute()
            for item in playlist_response.get("items", []):
                vid = item.get("contentDetails", {}).get("videoId")
                if vid:
                    video_ids.append(vid)
            page_token = playlist_response.get("nextPageToken")
            remaining -= batch
            if not page_token:
                break

        if not video_ids:
            return []

        def parse_duration(duration_str):
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str or "")
            if not match:
                return 0
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds

        excluded = [t.strip().lower() for t in (exclude_title_tags or []) if t.strip()]

        videos = []
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i:i + 50]
            video_response = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(chunk)
            ).execute()
            for v in video_response.get("items", []):
                title = v["snippet"]["title"]
                if excluded and any(tag in title.lower() for tag in excluded):
                    continue
                videos.append({
                    "id": v["id"],
                    "title": title,
                    "thumbnail": v["snippet"]["thumbnails"]["medium"]["url"],
                    "published_at": v["snippet"]["publishedAt"],
                    "duration_seconds": parse_duration(v["contentDetails"]["duration"]),
                    "view_count": int(v["statistics"].get("viewCount") or 0)
                })
        return videos

    def upload_video(self, video_path: Path, metadata: Dict[str, Any]):
        """Uploads a video to YouTube with the provided metadata."""
        creds = self.get_credentials()
        if not creds:
            raise RuntimeError("Not authenticated with YouTube")
        
        youtube = build("youtube", "v3", credentials=creds)
        
        # Sanitize tags: YouTube tags cannot contain certain characters like < > or be too long
        raw_tags = metadata.get("tags", "").split(",")
        clean_tags = []
        total_len = 0
        for tag in raw_tags:
            # Remove invalid chars and extra spaces
            t = tag.replace("?", "").replace("\u00bf", "").strip()
            if not t: continue
            if len(t) > 100: t = t[:97] + "..." # YouTube limit is 100 per tag
            
            if total_len + len(t) + 1 < 500: # Total limit is 500
                clean_tags.append(t)
                total_len += len(t) + 1
            else:
                break

        body = {
            "snippet": {
                "title": metadata.get("title", "Untitled Video"),
                "description": metadata.get("description", ""),
                "tags": clean_tags,
                "categoryId": metadata.get("category_id", "22")  # Default to People & Blogs
            },
            "status": {
                "privacyStatus": metadata.get("privacy_status", "private"),
                "selfDeclaredMadeForKids": False
            }
        }
        
        if metadata.get("publish_at"):
            body["status"]["publishAt"] = metadata["publish_at"]
            # Scheduled videos must be private or unlisted during upload
            if body["status"]["privacyStatus"] == "public":
                body["status"]["privacyStatus"] = "private"

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True
        )
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        try:
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Uploaded {int(status.progress() * 100)}%")
            
            return response
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    def update_video_metadata(self, video_id: str, metadata: Dict[str, Any]):
        """Updates metadata for an existing YouTube video."""
        creds = self.get_credentials()
        if not creds:
            raise RuntimeError("Not authenticated with YouTube")
        
        youtube = build("youtube", "v3", credentials=creds)
        
        # Sanitize tags (reusing logic from upload_video)
        raw_tags = metadata.get("tags", "").split(",")
        clean_tags = []
        total_len = 0
        for tag in raw_tags:
            t = tag.replace("?", "").replace("\u00bf", "").strip()
            if not t: continue
            if len(t) > 100: t = t[:97] + "..."
            if total_len + len(t) + 1 < 500:
                clean_tags.append(t)
                total_len += len(t) + 1
            else:
                break

        body = {
            "id": video_id,
            "snippet": {
                "title": metadata.get("title"),
                "description": metadata.get("description"),
                "tags": clean_tags,
                "categoryId": metadata.get("category_id", "22")
            }
        }
        
        request = youtube.videos().update(
            part="snippet",
            body=body
        )
        response = request.execute()
        return response

    def set_thumbnail(self, video_id: str, thumbnail_path: Path):
        """Sets a custom thumbnail for a video. Automatically compresses if > 2MB."""
        creds = self.get_credentials()
        if not creds:
            raise RuntimeError("Not authenticated with YouTube")
        
        # YouTube limit is 2MB
        MAX_SIZE = 2 * 1024 * 1024
        upload_path = thumbnail_path
        
        if thumbnail_path.stat().st_size > MAX_SIZE:
            print(f"[youtube] Thumbnail {thumbnail_path.name} is too large ({thumbnail_path.stat().st_size / 1024 / 1024:.2f}MB). Compressing...", flush=True)
            from PIL import Image
            img = Image.open(thumbnail_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Save as JPEG with decreasing quality until < 2MB
            tmp_thumb = thumbnail_path.parent / f"__tmp_thumb_{video_id}.jpg"
            quality = 95
            img.save(tmp_thumb, "JPEG", quality=quality, optimize=True)
            
            while tmp_thumb.stat().st_size > MAX_SIZE and quality > 10:
                quality -= 5
                img.save(tmp_thumb, "JPEG", quality=quality, optimize=True)
                print(f"[youtube] Retrying compression: quality={quality}, size={tmp_thumb.stat().st_size / 1024:.1f}KB")
            
            upload_path = tmp_thumb
        
        youtube = build("youtube", "v3", credentials=creds)
        
        try:
            request = youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(upload_path))
            )
            response = request.execute()
            return response
        finally:
            # Clean up temporary compressed thumbnail if it was created
            if upload_path != thumbnail_path and upload_path.exists():
                upload_path.unlink()
