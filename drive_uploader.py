"""
Google Drive Upload Integration for CurveTracker
Uploads JSON exports to Google Drive with public access
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class DriveUploader:
    """Upload JSON files to Google Drive"""

    def __init__(
        self,
        creds_file: str = "Google Credentials.json",
        folder_id: Optional[str] = None
    ):
        """
        Initialize Drive uploader.

        Args:
            creds_file: Path to Google service account credentials
            folder_id: Optional parent folder ID for uploads
        """
        self.creds_file = creds_file
        self.folder_id = folder_id
        self.service = None

    def _get_service(self):
        """
        Initialize Google Drive API service.

        Returns:
            Google Drive API service object
        """
        if self.service is None:
            try:
                from google.oauth2.service_account import Credentials
                from googleapiclient.discovery import build

                scopes = ['https://www.googleapis.com/auth/drive.file']
                creds = Credentials.from_service_account_file(
                    self.creds_file,
                    scopes=scopes
                )
                self.service = build('drive', 'v3', credentials=creds)
            except Exception as e:
                raise Exception(f"Failed to initialize Drive service: {e}")

        return self.service

    def upload_json(
        self,
        local_file_path: str,
        drive_file_name: str
    ) -> Dict[str, Any]:
        """
        Upload or update JSON file on Google Drive.

        Args:
            local_file_path: Path to local JSON file
            drive_file_name: Name for file in Drive

        Returns:
            Dict with keys:
                - success (bool): Whether upload succeeded
                - file_id (str): Drive file ID (if success)
                - url (str): Public download URL (if success)
                - error (str): Error message (if failed)
        """
        try:
            from googleapiclient.http import MediaFileUpload

            # Validate local file exists
            if not os.path.exists(local_file_path):
                return {
                    'success': False,
                    'error': f"Local file not found: {local_file_path}"
                }

            service = self._get_service()

            # Check if file already exists
            existing_file = self._find_file_by_name(drive_file_name)

            file_metadata = {
                'name': drive_file_name,
                'mimeType': 'application/json'
            }

            if self.folder_id:
                file_metadata['parents'] = [self.folder_id]

            media = MediaFileUpload(
                local_file_path,
                mimetype='application/json',
                resumable=True
            )

            if existing_file:
                # Update existing file
                file_id = existing_file['id']
                file = service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                print(f"📝 Updated existing file: {drive_file_name}")
            else:
                # Create new file
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink, webContentLink'
                ).execute()
                file_id = file['id']
                print(f"📤 Uploaded new file: {drive_file_name}")

                # Make file publicly readable
                self._make_public(file_id)

            # Get public download URL
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

            return {
                'success': True,
                'file_id': file_id,
                'url': download_url
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _find_file_by_name(self, filename: str) -> Optional[Dict]:
        """
        Find file by name in Drive.

        Args:
            filename: Name of file to find

        Returns:
            File metadata dict if found, None otherwise
        """
        try:
            service = self._get_service()

            query = f"name='{filename}' and trashed=false"
            if self.folder_id:
                query += f" and '{self.folder_id}' in parents"

            results = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, webViewLink, webContentLink)',
                pageSize=1
            ).execute()

            files = results.get('files', [])
            return files[0] if files else None

        except Exception as e:
            print(f"⚠️  Error searching for file: {e}")
            return None

    def _make_public(self, file_id: str) -> bool:
        """
        Make file publicly readable.

        Args:
            file_id: Google Drive file ID

        Returns:
            True if successful, False otherwise
        """
        try:
            service = self._get_service()

            permission = {
                'type': 'anyone',
                'role': 'reader'
            }

            service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()

            print(f"🌐 File set to public access")
            return True

        except Exception as e:
            print(f"⚠️  Warning: Could not set public permissions: {e}")
            return False

    def cleanup_old_archives(self, days_to_keep: int = 30) -> int:
        """
        Delete archive files older than specified days.

        Args:
            days_to_keep: Number of days of archives to keep

        Returns:
            Number of files deleted
        """
        try:
            service = self._get_service()

            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_rfc3339 = cutoff_date.strftime('%Y-%m-%dT%H:%M:%S')

            # Search for old archive files
            query = f"name contains 'curve_pools_' and name contains '.json' and createdTime < '{cutoff_rfc3339}' and trashed=false"
            if self.folder_id:
                query += f" and '{self.folder_id}' in parents"

            results = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, createdTime)'
            ).execute()

            files = results.get('files', [])
            deleted_count = 0

            for file in files:
                # Skip the "latest" file
                if file['name'] == 'curve_pools_latest.json':
                    continue

                try:
                    service.files().delete(fileId=file['id']).execute()
                    print(f"🗑️  Deleted old archive: {file['name']}")
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️  Could not delete {file['name']}: {e}")

            if deleted_count > 0:
                print(f"✅ Cleaned up {deleted_count} old archive(s)")

            return deleted_count

        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
            return 0

    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """
        Get information about a file.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dict or None
        """
        try:
            service = self._get_service()

            file = service.files().get(
                fileId=file_id,
                fields='id, name, size, createdTime, modifiedTime, webViewLink, webContentLink'
            ).execute()

            return file

        except Exception as e:
            print(f"⚠️  Error getting file info: {e}")
            return None
