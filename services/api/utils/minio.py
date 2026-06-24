from core.common.minio import MinIOClient
import os
import sys
from datetime import datetime
from io import BytesIO
import boto3
from botocore.exceptions import ClientError
import structlog

# Thiết lập đường dẫn dự án
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MinioConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# Khởi tạo MinIO client
s3_client = MinIOClient().client

def secure_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and invalid characters."""
    filename = os.path.basename(filename.replace('\\', '/'))
    return ''.join(c for c in filename if c.isalnum() or c in ('.', '_', '-')).strip()


def upload_to_minio(file, 
                    bucket_name=MinioConfig.UPLOAD_BUCKET_NAME, 
                    object_name: str = None, 
                    file_name: str = None) -> str:
    """
    Upload a file to MinIO and return the object name.
    
    Args:
        file: The file object to upload (e.g., from request.files or a BufferedReader).
        bucket_name (str): The name of the MinIO bucket.
        object_name (str): The name to give the file in MinIO. If None, it will be generated.
        filename (str): The name of the file, required if file object lacks a 'filename' attribute.
    
    Returns:
        str: The object name if successful.
    
    Raises:
        ValueError: If filename is missing or invalid.
        ClientError: If MinIO upload fails.
    """
    try:
        # Kiểm tra bucket tồn tại
        s3_client.head_bucket(Bucket=bucket_name)
        logger.debug("minio_bucket_exists", action="upload_to_minio", bucket_name=bucket_name)

        # Xác định filename
        if object_name is None:
            if hasattr(file, 'filename') and file.filename:
                file_name = file.filename
            elif file_name:
                file_name = file_name
            else:
                raise ValueError("Either 'object_name' must be provided or 'file' must have a 'filename' attribute, or pass 'filename' explicitly")
            object_name = f"uploads_record/{file_name}"

        # Upload file
        s3_client.upload_fileobj(file, bucket_name, object_name)
        logger.info("upload_to_minio_success", action="upload_to_minio", bucket_name=bucket_name, object_name=object_name)
        return object_name

    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error("upload_to_minio_failed", action="upload_to_minio", **{"error.code": "EXT", "error.message": str(e)}, minio_error_code=error_code, exc_info=True)
        raise ClientError(f"Failed to upload to MinIO: {error_code}", "upload_fileobj")
    except Exception as e:
        logger.error("upload_to_minio_failed", action="upload_to_minio", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
        raise


def download_from_minio(object_name: str, bucket_name=MinioConfig.UPLOAD_BUCKET_NAME) -> BytesIO:
    """
    Download a file from MinIO and return it as a BytesIO stream.
    
    Args:
        object_name (str): The object key in MinIO.
        bucket_name (str): The name of the MinIO bucket.
    
    Returns:
        BytesIO: The file stream if successful.
    
    Raises:
        ClientError: If the file or bucket does not exist.
        ValueError: If object_name is invalid.
    """
    try:
        # Kiểm tra bucket tồn tại
        s3_client.head_bucket(Bucket=bucket_name)
        logger.debug("minio_bucket_exists", action="download_from_minio", bucket_name=bucket_name)

        # Kiểm tra object tồn tại
        s3_client.head_object(Bucket=bucket_name, Key=object_name)
        logger.debug("minio_object_exists", action="download_from_minio", bucket_name=bucket_name, object_name=object_name)

        # Tải file
        response = s3_client.get_object(Bucket=bucket_name, Key=object_name)
        file_stream = BytesIO(response['Body'].read())
        logger.info("download_from_minio_success", action="download_from_minio", bucket_name=bucket_name, object_name=object_name)
        return file_stream

    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error("download_from_minio_failed", action="download_from_minio", **{"error.code": "EXT", "error.message": str(e)}, minio_error_code=error_code, exc_info=True)
        if error_code == 'NoSuchKey':
            raise ClientError(f"File not found in MinIO: {object_name}", "get_object")
        elif error_code == 'NoSuchBucket':
            raise ClientError(f"Bucket not found: {bucket_name}", "head_bucket")
        raise
    except Exception as e:
        logger.error("download_from_minio_failed", action="download_from_minio", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
        raise
    return False


def delete_minio_object(bucket_name=MinioConfig.UPLOAD_BUCKET_NAME, 
                        object_name=None, 
                        secure=True):
    """
    Delete an object from a MinIO bucket.
    
    Args:
        endpoint (str): MinIO server address (e.g., 'play.min.io')
        access_key (str): Access key for MinIO
        secret_key (str): Secret key for MinIO
        bucket_name (str): Name of the bucket
        object_name (str): Name of the object to delete
        secure (bool): Use HTTPS if True, HTTP if False
    
    Returns:
        bool: True if deletion is successful, False otherwise
    """
    try:        
        s3_client.remove_object(bucket_name, object_name)
        logger.debug("delete_minio_object_success", action="delete_minio_object", object_name=object_name, bucket_name=bucket_name)
        return True
    except Exception as err:
        logger.error("delete_minio_object_failed", action="delete_minio_object", **{"error.code": "EXT", "error.message": str(err)}, exc_info=True)
        return False

if __name__ == "__main__":
    try:
        object_name = "uploads_record/21_2023_QH15 _ Fake.doc"
        bucket_name = MinioConfig.UPLOAD_BUCKET_NAME
        file_stream = download_from_minio(object_name, bucket_name)
        with open("/home/ubuntu/projects/AI/git/users/giangnv/law-document-sync-core-service/services/uploads/DOWNLOAD_FILE.doc", "wb") as file:
            file.write(file_stream.read())
        logger.info("download_and_save_success", action="main")
    except ClientError as e:
        logger.error("download_and_save_failed", action="main", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
    except Exception as e:
        logger.error("download_and_save_failed", action="main", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)