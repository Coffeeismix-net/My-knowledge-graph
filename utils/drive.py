# utils/drive.py
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# 구글 드라이브 API 권한 설정
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """
    secrets.toml의 정보를 이용해 구글 드라이브 서비스 객체를 생성합니다.
    """
    if "gcp_service_account" not in st.secrets:
        st.error("Secrets에 gcp_service_account 정보가 없습니다.")
        return None
        
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def ensure_folder_exists(service, folder_name):
    """
    루트에 특정 폴더가 있는지 확인하고, 없으면 생성합니다.
    """
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])

    if not files:
        # 폴더가 없으면 생성
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    else:
        # 있으면 첫 번째 폴더 ID 반환
        return files[0].get('id')

def upload_image_to_drive(file_obj, filename):
    """
    이미지 파일 객체를 받아 드라이브의 'Stock_Analysis_Images' 폴더에 업로드하고 링크를 반환합니다.
    """
    service = get_drive_service()
    if not service:
        return None

    # 1. 저장할 폴더 ID 확보 (없으면 자동 생성)
    folder_id = ensure_folder_exists(service, "Stock_Analysis_Images")

    # 2. 파일 메타데이터 설정
    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }

    # 3. 업로드 실행
    media = MediaIoBaseUpload(file_obj, mimetype=file_obj.type, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink, webContentLink'
    ).execute()

    # 4. 이미지 링크 반환 (webContentLink가 이미지 직접 주소)
    return file.get('webContentLink')
