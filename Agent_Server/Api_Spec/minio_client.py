"""
MinIO 客户端封装

作者: Ai_Test_Agent Team
"""
import os
from minio import Minio
from dotenv import load_dotenv

load_dotenv()


def get_minio_client() -> Minio:
    """获取 MinIO 客户端实例"""
    endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
    access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure
    )


def get_bucket_name() -> str:
    return os.getenv('MINIO_BUCKET', 'aitest')


def ensure_bucket():
    """确保 bucket 存在"""
    client = get_minio_client()
    bucket = get_bucket_name()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    return client, bucket
