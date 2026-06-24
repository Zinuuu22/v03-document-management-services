"""
MongoDB Serializer Utility
Handles serialization of MongoDB documents for external systems
"""

import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict
from bson import ObjectId
import structlog

logger = structlog.get_logger()


def serialize_mongo_document(doc: Any) -> Dict[str, Any]:
    """
    Serialize MongoDB document to JSON-serializable dictionary
    
    Args:
        doc: MongoDB document or any Python object
        
    Returns:
        JSON-serializable dictionary
    """
    if doc is None:
        return None
    
    try:
        if isinstance(doc, dict):
            return {key: serialize_mongo_document(value) for key, value in doc.items()}
        elif isinstance(doc, list):
            return [serialize_mongo_document(item) for item in doc]
        elif isinstance(doc, ObjectId):
            return str(doc)
        elif isinstance(doc, (datetime, date)):
            return doc.isoformat()
        elif isinstance(doc, Decimal):
            return float(doc)
        elif isinstance(doc, (bytes, bytearray)):
            return doc.decode('utf-8', errors='ignore')
        elif hasattr(doc, '__dict__'):
            # Handle custom objects
            return serialize_mongo_document(doc.__dict__)
        else:
            # For basic types (str, int, float, bool, None)
            return doc
            
    except Exception as e:
        logger.error(
            "serialize_mongo_document_failed",
            action="serialize_mongo_document",
            **{"error.code": "SER", "error.message": str(e)},
            doc_type=type(doc).__name__
        )
        return str(doc)


def deserialize_mongo_document(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deserialize JSON dictionary back to MongoDB-compatible format
    
    Args:
        data: JSON-serializable dictionary
        
    Returns:
        MongoDB-compatible dictionary
    """
    if data is None:
        return None
    
    try:
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # Try to convert ObjectId strings back
                if key == '_id' and isinstance(value, str) and len(value) == 24:
                    try:
                        result[key] = ObjectId(value)
                        continue
                    except:
                        pass
                
                # Try to convert datetime strings back
                if isinstance(value, str):
                    # Try ISO format datetime
                    try:
                        result[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        continue
                    except:
                        pass
                
                # Try to convert ObjectId strings in arrays
                if isinstance(value, list):
                    result[key] = [deserialize_mongo_document(item) if isinstance(item, dict) else item for item in value]
                elif isinstance(value, dict):
                    result[key] = deserialize_mongo_document(value)
                else:
                    result[key] = value
            
            return result
        else:
            return data
            
    except Exception as e:
        logger.error(
            "deserialize_mongo_document_failed",
            action="deserialize_mongo_document",
            **{"error.code": "SER", "error.message": str(e)},
            data_type=type(data).__name__
        )
        return data


def sanitize_for_json(doc: Any) -> Dict[str, Any]:
    """
    Sanitize document for JSON serialization (more aggressive than serialize_mongo_document)
    
    Args:
        doc: MongoDB document or any Python object
        
    Returns:
        JSON-safe dictionary
    """
    if doc is None:
        return None
    
    try:
        if isinstance(doc, dict):
            return {str(key): sanitize_for_json(value) for key, value in doc.items()}
        elif isinstance(doc, list):
            return [sanitize_for_json(item) for item in doc]
        elif isinstance(doc, ObjectId):
            return {"$oid": str(doc)}
        elif isinstance(doc, datetime):
            return {"$date": doc.isoformat()}
        elif isinstance(doc, date):
            return {"$date": doc.isoformat()}
        elif isinstance(doc, Decimal):
            return {"$decimal": str(doc)}
        elif isinstance(doc, (bytes, bytearray)):
            return {"$binary": doc.hex()}
        elif isinstance(doc, (str, int, float, bool)):
            return doc
        else:
            # Convert anything else to string
            return str(doc)
            
    except Exception as e:
        logger.error(
            "sanitize_for_json_failed",
            action="sanitize_for_json",
            **{"error.code": "SER", "error.message": str(e)},
            doc_type=type(doc).__name__
        )
        return {"$error": str(doc)}


def extract_object_id(doc: Dict[str, Any]) -> str:
    """
    Extract ObjectId from document as string
    
    Args:
        doc: MongoDB document
        
    Returns:
        ObjectId as string
    """
    if not isinstance(doc, dict):
        return None
    
    if '_id' in doc:
        obj_id = doc['_id']
        if isinstance(obj_id, ObjectId):
            return str(obj_id)
        elif isinstance(obj_id, str):
            return obj_id
    
    return None


def create_mongo_filter_from_query(query: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create MongoDB filter from query parameters
    
    Args:
        query: Query parameters dictionary
        
    Returns:
        MongoDB filter dictionary
    """
    if not query:
        return {}
    
    filter_dict = {}
    
    for key, value in query.items():
        if key == '_id' and isinstance(value, str):
            try:
                filter_dict[key] = ObjectId(value)
            except:
                filter_dict[key] = value
        elif key.endswith('_id') and isinstance(value, str):
            try:
                filter_dict[key] = ObjectId(value)
            except:
                filter_dict[key] = value
        elif isinstance(value, str) and value.startswith('regex:'):
            # Handle regex queries
            pattern = value[6:]  # Remove 'regex:' prefix
            filter_dict[key] = {"$regex": pattern, "$options": "i"}
        else:
            filter_dict[key] = value
    
    return filter_dict


def validate_mongo_document(doc: Dict[str, Any], required_fields: list = None) -> tuple[bool, str]:
    """
    Validate MongoDB document structure
    
    Args:
        doc: Document to validate
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(doc, dict):
        return False, "Document must be a dictionary"
    
    if required_fields:
        missing_fields = [field for field in required_fields if field not in doc]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    # Check for invalid field names (MongoDB restrictions)
    invalid_keys = [key for key in doc.keys() if key.startswith('$')]
    if invalid_keys:
        return False, f"Invalid field names (cannot start with $): {', '.join(invalid_keys)}"
    
    return True, ""


def merge_mongo_documents(base_doc: Dict[str, Any], update_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two MongoDB documents
    
    Args:
        base_doc: Base document
        update_doc: Document with updates
        
    Returns:
        Merged document
    """
    if not base_doc:
        return update_doc.copy() if update_doc else {}
    
    if not update_doc:
        return base_doc.copy()
    
    merged = base_doc.copy()
    
    for key, value in update_doc.items():
        if key == '_id':
            continue  # Don't overwrite _id
        
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_mongo_documents(merged[key], value)
        else:
            merged[key] = value
    
    return merged
