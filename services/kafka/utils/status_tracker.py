"""
Status Tracker Utility
Tracks and manages status updates for various processes
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class StatusTracker:
    """Tracks status for various processes (training, extraction, etc.)"""

    def __init__(self):
        self.client = None
        self.db = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize MongoDB connection"""
        try:
            from core.common.mongo.client import get_mongo_client
            self.client = get_mongo_client()

            # Test connection
            self.client.admin.command('ping')

            # Get database
            from constants import MigrateConfig
            self.db = self.client[MigrateConfig.MIGRATE_CORE_DB]

            logger.info("status_tracker_mongodb_connected", action="_initialize_connection")

        except Exception as e:
            logger.error(
                "status_tracker_mongodb_connect_failed",
                action="_initialize_connection",
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True
            )
            # Continue without MongoDB - will use in-memory tracking
            self.client = None
            self.db = None

    def update_training_status(self, train_id: str, status: str, metadata: Dict[str, Any] = None):
        """Update training process status"""
        try:
            if self.db:
                from constants import MongoDBCollectionConfig
                collection = self.db[MongoDBCollectionConfig.BIZ_TRAINING_PROCESS_COLLECTION_NAME]

                update_data = {
                    "status": status,
                    "updated_at": datetime.now()
                }

                if metadata:
                    update_data.update(metadata)

                result = collection.update_one(
                    {"train_id": train_id},
                    {"$set": update_data},
                    upsert=True
                )

                logger.debug(
                    "update_training_status_success",
                    action="update_training_status",
                    train_id=train_id,
                    status=status,
                    matched=result.matched_count,
                    upserted=result.upserted_id is not None
                )
            else:
                logger.info(
                    "update_training_status_in_memory",
                    action="update_training_status",
                    train_id=train_id,
                    status=status
                )

        except Exception as e:
            logger.error(
                "update_training_status_failed",
                action="update_training_status",
                train_id=train_id,
                status=status,
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True
            )

    def update_extraction_status(self, document_id: str, status: str, metadata: Dict[str, Any] = None):
        """Update extraction process status"""
        try:
            if self.db:
                # Use a general status collection for extraction processes
                collection = self.db["extraction_status"]

                update_data = {
                    "document_id": document_id,
                    "status": status,
                    "updated_at": datetime.now()
                }

                if metadata:
                    update_data.update(metadata)

                result = collection.update_one(
                    {"document_id": document_id},
                    {"$set": update_data},
                    upsert=True
                )

                logger.debug(
                    "update_extraction_status_success",
                    action="update_extraction_status",
                    document_id=document_id,
                    status=status,
                    matched=result.matched_count
                )
            else:
                logger.info(
                    "update_extraction_status_in_memory",
                    action="update_extraction_status",
                    document_id=document_id,
                    status=status
                )

        except Exception as e:
            logger.error(
                "update_extraction_status_failed",
                action="update_extraction_status",
                document_id=document_id,
                status=status,
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True
            )

    def get_training_status(self, train_id: str) -> Optional[Dict[str, Any]]:
        """Get training process status"""
        try:
            if self.db:
                from constants import MongoDBCollectionConfig
                collection = self.db[MongoDBCollectionConfig.BIZ_TRAINING_PROCESS_COLLECTION_NAME]

                result = collection.find_one({"train_id": train_id})

                if result:
                    # Convert ObjectId to string for serialization
                    if '_id' in result:
                        result['_id'] = str(result['_id'])

                    # Convert datetime objects
                    if 'updated_at' in result and isinstance(result['updated_at'], datetime):
                        result['updated_at'] = result['updated_at'].isoformat()

                    return result
                else:
                    return None
            else:
                logger.warning(
                    "get_training_status_no_db",
                    action="get_training_status",
                    train_id=train_id,
                    **{"error.message": "No MongoDB connection"}
                )
                return None

        except Exception as e:
            logger.error(
                "get_training_status_failed",
                action="get_training_status",
                train_id=train_id,
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True
            )
            return None

    def get_extraction_status(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get extraction process status"""
        try:
            if self.db:
                collection = self.db["extraction_status"]

                result = collection.find_one({"document_id": document_id})

                if result:
                    # Convert ObjectId to string for serialization
                    if '_id' in result:
                        result['_id'] = str(result['_id'])

                    # Convert datetime objects
                    if 'updated_at' in result and isinstance(result['updated_at'], datetime):
                        result['updated_at'] = result['updated_at'].isoformat()

                    return result
                else:
                    return None
            else:
                logger.warning(
                    "get_extraction_status_no_db",
                    action="get_extraction_status",
                    document_id=document_id,
                    **{"error.message": "No MongoDB connection"}
                )
                return None

        except Exception as e:
            logger.error(
                "get_extraction_status_failed",
                action="get_extraction_status",
                document_id=document_id,
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True
            )
            return None

    def cleanup_old_status(self, days_old: int = 30):
        """Clean up old status records"""
        try:
            if not self.db:
                logger.warning(
                    "cleanup_old_status_no_db",
                    action="cleanup_old_status",
                    **{"error.message": "No MongoDB connection"}
                )
                return

            cutoff_date = datetime.now() - timedelta(days=days_old)

            # Clean up training status
            from constants import MongoDBCollectionConfig
            training_collection = self.db[MongoDBCollectionConfig.BIZ_TRAINING_PROCESS_COLLECTION_NAME]
            training_result = training_collection.delete_many({
                "updated_at": {"$lt": cutoff_date},
                "status": {"$in": ["COMPLETED", "FAILED"]}
            })

            # Clean up extraction status
            extraction_collection = self.db["extraction_status"]
            extraction_result = extraction_collection.delete_many({
                "updated_at": {"$lt": cutoff_date},
                "status": {"$in": ["COMPLETED", "FAILED"]}
            })

            logger.info(
                "cleanup_old_status_success",
                action="cleanup_old_status",
                training_deleted=training_result.deleted_count,
                extraction_deleted=extraction_result.deleted_count,
                cutoff_date=cutoff_date.isoformat()
            )

        except Exception as e:
            logger.error(
                "cleanup_old_status_failed",
                action="cleanup_old_status",
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True
            )

    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all status records"""
        try:
            if not self.db:
                return {"error": "No MongoDB connection"}

            summary = {}

            # Training status summary
            from constants import MongoDBCollectionConfig
            training_collection = self.db[MongoDBCollectionConfig.BIZ_TRAINING_PROCESS_COLLECTION_NAME]

            pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            training_stats = list(training_collection.aggregate(pipeline))
            summary["training"] = {stat["_id"]: stat["count"] for stat in training_stats}

            # Extraction status summary
            extraction_collection = self.db["extraction_status"]
            extraction_stats = list(extraction_collection.aggregate(pipeline))
            summary["extraction"] = {stat["_id"]: stat["count"] for stat in extraction_stats}

            return summary

        except Exception as e:
            logger.error(
                "get_status_summary_failed",
                action="get_status_summary",
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True
            )
            return {"error": str(e)}

    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.debug("status_tracker_mongodb_closed", action="close")
