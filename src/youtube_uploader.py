import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import googleapiclient.http

class YouTubeUploader:
    def __init__(self, client_secrets_file="client_secrets.json"):
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        self.client_secrets_file = client_secrets_file
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.credentials = None

    def _build_credentials_from_env(self):
        """Build OAuth2 credentials from env vars — no token.json needed in CI."""
        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
        if not (client_id and client_secret and refresh_token):
            return None
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=self.scopes,
        )
        creds.refresh(Request())
        return creds

    def authenticate(self):
        # 1. Try env var credentials first (CI-safe, no expiry issues)
        try:
            env_creds = self._build_credentials_from_env()
            if env_creds and env_creds.valid:
                print("Authenticated via YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN env vars.")
                self.credentials = env_creds
                return googleapiclient.discovery.build(
                    self.api_service_name, self.api_version, credentials=self.credentials)
        except Exception as e:
            print(f"Env var auth failed, falling back to token.json: {e}")

        # 2. Fall back to token.json
        if os.path.exists('token.json'):
            print("Found existing token.json, attempting to authenticate...")
            self.credentials = Credentials.from_authorized_user_file('token.json', self.scopes)

        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                print("Refreshing expired YouTube access token...")
                try:
                    self.credentials.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    self.credentials = None

            if not self.credentials or not self.credentials.valid:
                if os.getenv("CI", "false").lower() in ("true", "1"):
                    raise RuntimeError(
                        "YouTube credentials are missing or expired in CI. "
                        "Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN "
                        "as GitHub secrets (run scripts/get_youtube_token.py locally to obtain them)."
                    )
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"ERROR: {self.client_secrets_file} is missing! "
                        "Download it from Google Cloud Console."
                    )
                print("No existing token. Opening browser for first-time YouTube verification...")
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes)
                self.credentials = flow.run_local_server(port=0)

            # Save credentials for next local run
            with open('token.json', 'w') as token:
                token.write(self.credentials.to_json())

        return googleapiclient.discovery.build(
            self.api_service_name, self.api_version, credentials=self.credentials)

    def upload_short(self, file_path, title, description, category_id="22", privacy_status=None, tags=None):
        if privacy_status is None:
            privacy_status = (os.getenv("YOUTUBE_PRIVACY_STATUS") or os.getenv("YOUTUBE_PRIVACY") or "public").lower()
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ERROR: Video file not found: {file_path}")
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"ERROR: Video file is empty: {file_path}")
        if tags is None:
            tags = ["shorts", "shortsfeed", "viral"]
        youtube = self.authenticate()
        
        print(f"Uploading {file_path} to YouTube Shorts...")
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        # We use a resumable upload for better stability
        media = googleapiclient.http.MediaFileUpload(file_path, mimetype='video/mp4', chunksize=-1, resumable=True)
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = None
        try:
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Uploaded {int(status.progress() * 100)}%")
                
        except googleapiclient.errors.HttpError as e:
            error_details = e.content.decode()
            if "quotaExceeded" in error_details:
                print("ERROR: YouTube API Quota Exceeded! You can only upload about 6 videos per day with default limits.")
            elif "insufficientPermissions" in error_details:
                print("ERROR: Insufficient Permissions. Your token might not have the 'youtube.upload' scope.")
            else:
                print(f"ERROR: YouTube API returned an error: {e}")
            raise e
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during upload: {e}")
            raise e
        
        print(f"Upload Complete! Video published with ID: {response['id']}")
        return response['id']
