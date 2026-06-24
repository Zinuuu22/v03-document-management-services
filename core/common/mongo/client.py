"""
Centralized MongoDB client factory.

Usage:
    from core.common.mongo.client import get_mongo_client
    client = get_mongo_client()
"""

import os
import sys
from pymongo import MongoClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from constants import MongoDBConfig


_mongo_client_instance = None


def get_mongo_client() -> MongoClient:
    """
    Returns a module-level MongoClient configured from MongoDBConfig.
    Re-uses the same instance across calls (connection pooling is handled by pymongo).
    """
    global _mongo_client_instance
    if _mongo_client_instance is None:
        _mongo_client_instance = MongoClient(
            host=MongoDBConfig.HOST,
            port=MongoDBConfig.PORT,
            username=MongoDBConfig.USERNAME,
            password=MongoDBConfig.PASSWORD,
            authSource=MongoDBConfig.AUTH_SOURCE,
            # MongoDBConfig.URI
        )
    return _mongo_client_instance

print(f"MongoDB URI: {MongoDBConfig.URI}")
print(f"MongoDB client: {get_mongo_client()}")