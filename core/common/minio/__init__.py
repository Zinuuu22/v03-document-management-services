import os
import sys
from typing import Optional, Union
from io import BytesIO
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename as werkzeugUtilsSecureFilename
import boto3
from botocore.exceptions import ClientError

# Thiết lập đường dẫn dự án
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from constants import MinioConfig
from core.common.external_logging import execute_external_with_logging

def classify_minio_error(e):
    e_str = str(e).lower()
    e_type = type(e).__name__.lower()
    if "nosuchkey" in e_str or "not found" in e_str or "404" in e_str:
        return "not_found"
    if "timeout" in e_type or "timeout" in e_str:
        return "timeout"
    if "connection" in e_type or "connection error" in e_str:
        return "network"
    if "unavailable" in e_str or "503" in e_str or "502" in e_str:
        return "service_unavailable"
    return "unknown"

class MinIOClient:
    """A class to interact with MinIO storage service."""
    
    def __init__(self):
        """Initialize MinIO client with configuration from MinioConfig."""
        try:
            self.client = boto3.client(
                "s3",
                endpoint_url=MinioConfig.ENDPOINT,
                aws_access_key_id=MinioConfig.ACCESS_KEY,
                aws_secret_access_key=MinioConfig.SECRET_KEY,
            )
            logger.debug("minio_client_initialized", action="__init__")
        except Exception as e:
            logger.error("minio_client_init_failed", action="__init__", **{"error.code": "IO", "error.message": str(e)}, exc_info=True)
            raise
    
    def secure_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and invalid characters."""
        return werkzeugUtilsSecureFilename(filename)
    
    def upload_file(self, 
                    file: Optional[Union[str, FileStorage, BytesIO]] = None,
                    bucket_name: str = MinioConfig.DEFAULT_BUCKET_NAME,
                    object_name: Optional[str] = None, 
                    file_name: Optional[str] = None) -> str:
        """
        Upload a file to MinIO and return the object name.
        
        Args:
            file: File object (FileStorage, BytesIO) or file path (str).
            bucket_name: Name of the MinIO bucket.
            object_name: Name to give the file in MinIO. If None, generated automatically.
            file_name: File name if file object lacks a filename attribute.
        
        Returns:
            str: Object name in MinIO.
        
        Raises:
            ValueError: If filename is missing or invalid.
            ClientError: If MinIO upload fails.
        """
        try:
            # Check if bucket exists
            self.client.head_bucket(Bucket=bucket_name)
            logger.debug("bucket_exists", action="upload_file", bucket=bucket_name)
            
            # Determine object_name
            if object_name is None:
                if isinstance(file, str):
                    file_name = os.path.basename(file)
                elif hasattr(file, 'filename') and file.filename:
                    file_name = file.filename
                elif file_name:
                    file_name = file_name
                else:
                    raise ValueError("Either 'object_name' or 'file_name' must be provided, or 'file' must have a 'filename' attribute")
                object_name = f"uploads_record/{file_name}"
            
            # Ensure file is readable
            if hasattr(file, 'seek'):
                file.seek(0)
            
            # Configure multipart upload for large files
            config = boto3.s3.transfer.TransferConfig(multipart_threshold=1024*1024*20)  # 10MB
            
            # Upload file
            if isinstance(file, str):
                logger.debug("file_upload_started", action="upload_file", method="upload_file", bucket=bucket_name, object_name=object_name)
                execute_external_with_logging(
                    func=lambda: self.client.upload_file(file, bucket_name, object_name, Config=config),
                    action="upload_file",
                    service_name="minio",
                    operation="upload_object",
                    error_classifier=classify_minio_error,
                    meta={"object_name": object_name},
                    error_code="IO"
                )
            else:                
                logger.debug("file_upload_started", action="upload_file", bucket=bucket_name, object_name=object_name)
                execute_external_with_logging(
                    func=lambda: self.client.upload_fileobj(file, bucket_name, object_name, Config=config),
                    action="upload_file",
                    service_name="minio",
                    operation="upload_object",
                    error_classifier=classify_minio_error,
                    meta={"object_name": object_name},
                    error_code="IO"
                )
                            
            return object_name
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise
        except Exception as e:
            raise
    
    def download_file(self, object_name: str, bucket_name: str = MinioConfig.DEFAULT_BUCKET_NAME) -> BytesIO:
        """
        Download a file from MinIO as a BytesIO stream.
        
        Args:
            object_name: Object key in MinIO.
            bucket_name: Name of the MinIO bucket.
        
        Returns:
            BytesIO: File stream.
        
        Raises:
            ClientError: If file or bucket does not exist.
            ValueError: If object_name is invalid.
        """
        try:
            if not object_name:
                raise ValueError("Object name is required")
            
            # Check if bucket and object exist
            self.client.head_bucket(Bucket=bucket_name)
            self.client.head_object(Bucket=bucket_name, Key=object_name)
            
            # Download file
            response = execute_external_with_logging(
                func=lambda: self.client.get_object(Bucket=bucket_name, Key=object_name),
                action="download_file",
                service_name="minio",
                operation="download_object",
                error_classifier=classify_minio_error,
                meta={"object_name": object_name},
                error_code="IO"
            )
            file_stream = BytesIO(response['Body'].read())
            return file_stream
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise ClientError(f"File not found in MinIO: {object_name}", "get_object")
            elif error_code == 'NoSuchBucket':
                raise ClientError(f"Bucket not found: {bucket_name}", "head_bucket")
            raise
        except Exception as e:
            raise
    

    def delete_file(self, object_name: str, bucket_name: str = MinioConfig.DEFAULT_BUCKET_NAME) -> bool:
        """
        Delete an object from a MinIO bucket.
        
        Args:
            object_name: Object key in MinIO.
            bucket_name: Name of the MinIO bucket.
        
        Returns:
            bool: True if deletion is successful, False otherwise.
        
        Raises:
            ValueError: If object_name is invalid.
        """
        try:
            if not object_name:
                raise ValueError("Object name is required")
            
            # Check if bucket exists
            self.client.head_bucket(Bucket=bucket_name)
            
            # Delete object
            execute_external_with_logging(
                func=lambda: self.client.delete_object(Bucket=bucket_name, Key=object_name),
                action="delete_file",
                service_name="minio",
                operation="delete_object",
                error_classifier=classify_minio_error,
                meta={"object_name": object_name},
                error_code="IO"
            )
            return True
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            return False
        except Exception as e:
            return False
    
    def object_exists(self, object_name: str, bucket_name: str = MinioConfig.DEFAULT_BUCKET_NAME) -> bool:
        """
        Check if an object exists in a MinIO bucket.
        
        Args:
            object_name: Object key in MinIO.
            bucket_name: Name of the MinIO bucket.
        
        Returns:
            bool: True if object exists, False otherwise.
        """
        try:
            def do_check():
                try:
                    self.client.head_object(Bucket=bucket_name, Key=object_name)
                    return True
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        return False
                    raise e
                    
            res = execute_external_with_logging(
                func=do_check,
                action="object_exists",
                service_name="minio",
                operation="check_object",
                error_classifier=classify_minio_error,
                meta={"object_name": object_name},
                error_code="IO"
            )
            
            if res:
                logger.debug("object_exists", action="object_exists", bucket=bucket_name, object_name=object_name)
            else:
                logger.debug("object_not_found", action="object_exists", bucket=bucket_name, object_name=object_name)
            return res
        except Exception as e:
            raise

if __name__ == "__main__":
    try:
        minio_client = MinIOClient()
        # Test upload
        # with open(f"{PROJECT_ROOT}/uploads/900a18e4-1083-4de9-96cd-8e88e03a14ae_2682_2007_QD-UBND_m_61508.docx", "rb") as file:
        #     object_name = minio_client.upload_file(file, file_name="test.doc")
        
        # path_file = f"{PROJECT_ROOT}/uploads/900a18e4-1083-4de9-96cd-8e88e03a14ae_2682_2007_QD-UBND_m_61508.docx"
        # object_name = minio_client.upload_file(file=path_file)
        
        
        # Test download
        # object_name = "uploads_record/900a18e4-1083-4de9-96cd-8e88e03a14ae_2682_2007_QD-UBND_m_61508.docx"
        # file_stream = minio_client.download_file(object_name)
        # with open("downloaded_file.doc", "wb") as f:
        #     f.write(file_stream.read())
        
        # # Test check existence
        # object_name = "uploads_record/900a18e4-1083-4de9-96cd-8e88e03a14ae_2682_2007_QD-UBND_m_61508.docx"        
        # exists = minio_client.object_exists(object_name)
        
        # Test delete
        # object_name = "uploads_record/900a18e4-1083-4de9-96cd-8e88e03a14ae_2682_2007_QD-UBND_m_61508.docx"                
        object_name = "uploads_record/test.docx"                
        deleted = minio_client.delete_file(object_name)
        logger.info("object_deleted_result", action="main", deleted=deleted)
        
    except Exception as e:
        logger.error("test_failed", action="main", **{"error.code": "IO", "error.message": str(e)}, exc_info=True)
