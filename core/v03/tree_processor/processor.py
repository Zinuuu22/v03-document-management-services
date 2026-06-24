from core.common.mongo.client import get_mongo_client
import time
import os
import sys
from datetime import datetime
from typing import Tuple, Optional, List, Dict
import uuid
import pandas as pd
from pymongo import MongoClient, UpdateOne, UpdateMany
from pymongo.errors import PyMongoError
import structlog
import unicodedata


# Set up project root and append to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(PROJECT_ROOT)

from logs.logger_conf import setup_logging
from core.v03.tree_processor.utils import DocumentMapper
from constants import MongoDBConfig, MigrateConfig, ImportTreeConfig, MongoDBCollectionConfig


setup_logging()
logger = structlog.get_logger()


# Initialize MongoDB client and collections
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COLLECTION_NAME]
subject_tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COMPONENT_COLLECTION_NAME]
law_document_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_keywords_collection = db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME]

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}

def normalize_keyword(text) -> str:
    if text is None:
        return ""
    if isinstance(text, float):
        return ""
    text = str(text).strip().lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text

class LawTreeManager:
    """Manages law tree and subject tree operations in MongoDB."""

    def __init__(self):
        """Initialize LawTreeManager with MongoDB collections and document mapper."""
        self.tree_collection = tree_collection
        self.subject_tree_collection = subject_tree_collection
        self.law_keywords_collection = law_keywords_collection

        self.law_document_collection = law_document_collection
        self.document_mapper = DocumentMapper()
        self.BATCH_SIZE = 1000    
    
    def allowed_file(self, filename: str) -> bool:
        """Check if the file extension is allowed.

        Args:
            filename: Name of the file to check.

        Returns:
            True if the file extension is allowed, False otherwise.
        """
        return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

    def check_valid_file(self, 
                        tree_name: str, 
                        created_by: str,
                        path_file_excel: str):
        try:
            df = pd.read_excel(path_file_excel)
            required_columns = [
                ImportTreeConfig.PARENT_FIELD,
                ImportTreeConfig.CHILD_FIELD,
                ImportTreeConfig.NAME_FIELD
            ]
            if not all(col in df.columns for col in required_columns):
                return False, "", f"File must contain columns: {', '.join(required_columns)}"

            # Create tree
            status, tree_id, message = self.create_tree(tree_name, created_by)
            if not status:
                return False, "", message            
            return True, tree_id, "File is valid. Import tree to database started"
            
        except Exception as e:
            logger.error("file_validation_failed", action="check_valid_file", **{"error.code": "IO", "error.message": str(e)}, exc_info=True)
            raise

    def create_tree(self, tree_name: str, created_by: str = "ROOT") -> Tuple[bool, str, str]:
        """Create a new tree if it doesn't exist.

        Args:
            tree_name: Name of the tree.
            created_by: User who created the tree.

        Returns:
            Tuple of (status, tree_id, message): Success status, tree ID, and message.
        """
        try:
            if not tree_name:
                return False, "", "Tree name cannot be empty"
            
            existing_tree = self.tree_collection.find_one({"tree_name": tree_name})
            if existing_tree:
                return False, existing_tree["tree_id"], "Tree name already exists"

            tree_id = str(uuid.uuid4())
            tree = {
                "tree_id": tree_id,
                "tree_name": tree_name,
                "created_by": created_by,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_by": created_by,
                "status": "ACTIVE",
                "state": "PENDING",
                "category": "RULE"
            }
            self.tree_collection.insert_one(tree)
            return True, tree_id, "Tree created successfully"
        except PyMongoError as e:
            logger.error("tree_creation_failed", action="create_tree", **{"error.code": "DB", "error.message": str(e)}, tree_name=tree_name, exc_info=True)
            raise

    def update_tree(self, tree_id: str, tree_name: Optional[str] = None, last_modified_by: str = "ROOT") -> bool:
        """Update an existing tree.

        Args:
            tree_id: ID of the tree to update.
            tree_name: New name of the tree, if updating.
            last_modified_by: User who modified the tree.

        Returns:
            True if update was successful, False if tree not found.
        """
        try:
            tree = self.tree_collection.find_one({"tree_id": tree_id})
            if not tree:
                return False

            update_fields = {
                        "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_modified_by": last_modified_by
                        }
            if tree_name and tree_name != tree["tree_name"]:
                update_fields["tree_name"] = tree_name

            if update_fields:
                self.tree_collection.update_one({"tree_id": tree_id}, {"$set": update_fields})
            return True
        except PyMongoError as e:
            logger.error("tree_update_failed", action="update_tree", **{"error.code": "DB", "error.message": str(e)}, tree_id=tree_id, exc_info=True)
            raise

    def add_document_to_subject(self, subject_id: str, doc_id: str):
        """Add a document to a subject."""
        try:
            subject = self.subject_tree_collection.find_one({"subject_id": subject_id})
            if not subject:
                return False

            update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": "ROOT"}
            if doc_id not in subject["doc_id_includes"]:
                # Update Child
                update_fields["doc_id_includes"] = subject["doc_id_includes"] + [doc_id]
                update_fields["count"] = subject["count"] + 1
                self.subject_tree_collection.update_one({"subject_id": subject_id}, {"$set": update_fields})
                
                # Update Parent    
                parent_subject = self.subject_tree_collection.find_one({"subject_id": subject["subject_parent_id"]})
                if parent_subject:
                    update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": "ROOT"}
                    update_fields["count"] = parent_subject["count"] + 1
                    self.subject_tree_collection.update_one({"subject_id": parent_subject["subject_id"]}, {"$set": update_fields})

                # Update Tree
                tree = self.tree_collection.find_one({"tree_id": subject["tree_id"]})
                if tree:
                    update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": "ROOT"}
                    update_fields["count"] = tree["count"] + 1
                    self.tree_collection.update_one({"tree_id": subject["tree_id"]}, {"$set": update_fields})

            return True
        except PyMongoError as e:
            logger.error("document_add_to_subject_failed", action="add_document_to_subject", **{"error.code": "DB", "error.message": str(e)}, doc_id=doc_id, subject_id=subject_id, exc_info=True)
            raise

    def remove_document_to_subject(self, subject_id: str, doc_id: str, keyword_ids: list = None):
        """Remove a document from a subject."""
        try:
            subject = self.subject_tree_collection.find_one({"subject_id": subject_id})
            if not subject:
                return False

            update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": "ROOT"}
            if doc_id not in subject["doc_id_includes"]:
                return True
            
            # Update Child
            update_fields["doc_id_includes"] = subject["doc_id_includes"].copy()
            update_fields["doc_id_includes"].remove(doc_id)
            update_fields["count"] = subject["count"] - 1
            self.subject_tree_collection.update_one({"subject_id": subject_id}, {"$set": update_fields})
            
            # Update Parent    
            parent_subject = self.subject_tree_collection.find_one({"subject_id": subject["subject_parent_id"]})
            if parent_subject:
                update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": "ROOT"}
                update_fields["count"] = parent_subject["count"] - 1
                self.subject_tree_collection.update_one({"subject_id": parent_subject["subject_id"]}, {"$set": update_fields})

            # Update Tree
            tree = self.tree_collection.find_one({"tree_id": subject["tree_id"]})
            if tree:
                update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": "ROOT"}
                update_fields["count"] = tree["count"] -1 
                self.tree_collection.update_one({"tree_id": subject["tree_id"]}, {"$set": update_fields})

            return True
        except PyMongoError as e:
            logger.error("document_remove_from_subject_failed", action="remove_document_to_subject", **{"error.code": "DB", "error.message": str(e)}, doc_id=doc_id, subject_id=subject_id, exc_info=True)
            raise
        
    
    def create_parent_subject(self, tree_id: str, subject_name: str, 
                                created_by: str = "ROOT") -> Tuple[bool, str, str]:
        """Create a new parent subject if it doesn't exist.

        Args:
            tree_id: ID of the tree.
            subject_name: Name of the subject.
            description: Description of the subject.
            created_by: User who created the subject.

        Returns:
            Tuple of (status, subject_id, message): Success status, subject ID, and message.
        """
        try:
            if not subject_name:
                return False, "", "Subject name cannot be empty"
                
            existing_subject = self.subject_tree_collection.find_one({"tree_id": tree_id, "subject_name": subject_name})
            if existing_subject:
                return False, existing_subject["subject_id"], "Subject name already exists"

            subject_id = str(uuid.uuid4())
            subject = {
                "tree_id": tree_id,
                "subject_id": subject_id,
                "subject_name": subject_name,
                "created_by": created_by,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_by": created_by,
                "count": 0,
                "subject_level": "PARENT",
                "subject_parent_id": None,
                "doc_id_includes": [],
                "rules": {},
                "status": "ACTIVE",
                "state": "PENDING",
                "category": "RULE"                
            }
            self.subject_tree_collection.insert_one(subject)
            return True, subject_id, "Parent subject created successfully"
        except PyMongoError as e:
            logger.error("parent_subject_creation_failed", action="create_parent_subject", **{"error.code": "DB", "error.message": str(e)}, subject_name=subject_name, exc_info=True)
            raise

    def update_parent_subject(self, subject_id: str, subject_name: Optional[str] = None, 
                              last_modified_by: str = "ROOT") -> bool:
        """Update an existing parent subject.

        Args:
            subject_id: ID of the subject to update.
            subject_name: New name of the subject, if updating.
            last_modified_by: User who modified the subject.

        Returns:
            True if update was successful, False if subject not found.
        """
        try:
            # Check if it's a parent subject
            logger.debug("update_parent_subject_started", action="update_parent_subject", subject_id=subject_id, subject_name=subject_name, last_modified_by=last_modified_by)
            subject = self.subject_tree_collection.find_one({"subject_id": subject_id})
            if not subject:
                return False

            update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": last_modified_by}
            if subject_name and subject_name != subject["subject_name"]:
                update_fields["subject_name"] = subject_name

            if update_fields:
                self.subject_tree_collection.update_one({"subject_id": subject_id}, {"$set": update_fields})
            return True
        except PyMongoError as e:
            logger.error("parent_subject_update_failed", action="update_parent_subject", **{"error.code": "DB", "error.message": str(e)}, subject_id=subject_id, exc_info=True)
            raise



    def get_documents_by_rules(self, rules: dict) -> List[str]:
        """Retrieve document IDs based on given rules.

        Args:
            rules: Dictionary containing document filtering rules.

        Returns:
            List of document IDs matching the rules.
        """
        try:            
            query = {}
            if "documentCategoryCodes" in rules and rules["documentCategoryCodes"]:                
                query["type_id"] = {"$in": rules["documentCategoryCodes"] }
            if "issuedLevelCodes" in rules and rules["issuedLevelCodes"]:
                query["issuing_level_id"] = {"$in": rules["issuedLevelCodes"] }            
            if "industrySectorCodes" in rules and rules["industrySectorCodes"]:
                query['industry_sector_ids'] = {"$in": rules['industrySectorCodes'] }                                    
            if "keywordCodes" in rules and rules["keywordCodes"]:
                query['keyword_ids'] = {"$in": rules['keywordCodes']}            
            logger.debug("prepare_documents_query_successful", action="get_documents_by_rules", query=query)
            
            # Query document_collection
            documents = list(self.law_document_collection.find(query, {"doc_id": 1}))
            if documents:
                return [str(doc["doc_id"]) for doc in documents]
            else:
                return []
        except PyMongoError as e:
            logger.error("documents_retrieval_by_rules_failed", action="get_documents_by_rules", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            raise


    def create_child_subject(self, subject_name: str, subject_parent_id: str, rules: dict = {}, 
                                created_by: str = "ROOT") -> Tuple[bool, str, str]:
        """Create a new child subject if it doesn't exist.

        Args:
            subject_name: Name of the subject.
            subject_parent_id: ID of the parent subject.
            rules: Rules to filter documents.
            description: Description of the subject.
            created_by: User who created the subject.

        Returns:
            Tuple of (status, subject_id, message): Success status, subject ID, and message.
        """
        try:
            if not subject_name:
                return False, "", "Subject name cannot be empty"
                
            parent_subject = self.subject_tree_collection.find_one({"subject_id": subject_parent_id})
            if not parent_subject:
                return False, "", "Parent subject not found"

            tree_id = parent_subject["tree_id"]
            existing_subject = self.subject_tree_collection.find_one({"tree_id": tree_id, "subject_name": subject_name})
            if existing_subject:
                return False, existing_subject["subject_id"], "Subject name already exists"

            doc_id_includes = self.get_documents_by_rules(rules)
            subject_id = str(uuid.uuid4())
            subject = {
                "tree_id": tree_id,
                "subject_id": subject_id,
                "subject_name": subject_name,
                "created_by": created_by,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_by": created_by,
                "count": len(doc_id_includes),
                "subject_level": "CHILD",
                "subject_parent_id": subject_parent_id,
                "doc_id_includes": doc_id_includes,
                "rules": rules,
                "status": "ACTIVE",
                "state": "PENDING",
                "category": "RULE" if rules else "IMPORT"                
            }
            self.subject_tree_collection.insert_one(subject)

            # Update parent subject count
            self.subject_tree_collection.update_one(
                {"subject_id": subject_parent_id},
                {"$set": {"count": parent_subject["count"] + len(doc_id_includes)}}
            )
            # Update law document
            for doc_id in doc_id_includes:
                self.law_document_collection.update_one(
                    {"doc_id": doc_id},
                    {"$push": {"tree_ids": subject_id}}
                )
            return True, subject_id, "Child subject created successfully"
        except PyMongoError as e:
            logger.error("child_subject_creation_failed", action="create_child_subject", **{"error.code": "DB", "error.message": str(e)}, subject_name=subject_name, exc_info=True)
            raise

    def update_child_subject(self, subject_id: str, subject_name: Optional[str] = None, 
                            rules: Optional[dict] = None, 
                            last_modified_by: str = "ROOT") -> bool:
        """Update an existing child subject.

        Args:
            subject_id: ID of the subject to update.
            subject_name: New name of the subject, if updating.
            rules: New rules to filter documents, if updating.
            last_modified_by: User who modified the subject.

        Returns:
            True if update was successful, False if subject not found.
        """
        try:
            subject = self.subject_tree_collection.find_one({"subject_id": subject_id})
            if not subject:
                return False

            update_fields = {"last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_modified_by": last_modified_by}
            if subject_name and subject_name != subject["subject_name"]:
                update_fields["subject_name"] = subject_name

            parent_subject = self.subject_tree_collection.find_one({"subject_id": subject["subject_parent_id"]})
            logger.debug("retrieve_parent_subject_successful", action="update_child_subject", parent_subject=parent_subject)
            if rules and rules != subject["rules"]:
                old_doc_ids = set(subject["doc_id_includes"])
                doc_id_includes = self.get_documents_by_rules(rules)
                new_doc_ids = set(doc_id_includes)
                old_count = len(old_doc_ids)
                update_fields["doc_id_includes"] = doc_id_includes
                update_fields["rules"] = rules
                update_fields["count"] = len(doc_id_includes)
                # Update parent subject count
                if parent_subject:
                    new_parent_count = parent_subject["count"] - old_count + len(doc_id_includes)
                    self.subject_tree_collection.update_one(
                        {"subject_id": subject["subject_parent_id"]},
                        {"$set": {"count": new_parent_count}}
                    )

                # Docs mới được thêm vào → $addToSet subject_id vào tree_ids
                added_doc_ids = new_doc_ids - old_doc_ids
                for doc_id in added_doc_ids:
                    self.law_document_collection.update_one(
                        {"doc_id": doc_id},
                        {"$addToSet": {"tree_ids": subject_id}}
                    )

                # Docs bị loại ra → $pull subject_id khỏi tree_ids
                removed_doc_ids = old_doc_ids - new_doc_ids
                for doc_id in removed_doc_ids:
                    self.law_document_collection.update_one(
                        {"doc_id": doc_id},
                        {"$pull": {"tree_ids": subject_id}}
                    )
            if update_fields:
                self.subject_tree_collection.update_one({"subject_id": subject_id}, {"$set": update_fields})
            return True
        except PyMongoError as e:
            logger.error("child_subject_update_failed", action="update_child_subject", **{"error.code": "DB", "error.message": str(e)}, subject_id=subject_id, exc_info=True)
            raise

    def create_subject_tree_with_rule(self, name: Optional[str] = None, subject_level: Optional[str] = None,
                                     parent_subject_id: Optional[str] = None, rules: Optional[dict] = None, 
                                     created_by: str = "ROOT") -> Tuple[str, bool, str, str]:
        """Create a new tree, parent subject, or child subject with rules.

        Args:
            name: Name of the tree or subject.
            subject_level: Level of the subject ("PARENT" or "CHILD").
            parent_subject_id: ID of the parent subject, if creating a subject.
            rules: Rules to filter documents, if creating a child subject.
            created_by: User who created the tree or subject.

        Returns:
            Tuple of (type, status, id, message): Type (TREE, PARENT, CHILD), success status, ID, and message.
        """
        try:
            if not name:
                return "NONE", False, "", "Name cannot be empty"

            if subject_level == "TREE":
                # Create new tree
                status, tree_id, message = self.create_tree(tree_name=name, 
                                                            created_by=created_by)
                logger.debug("create_tree_successful", action="create_subject_tree_with_rule", status=status, tree_id=tree_id, message=message)
                return "TREE", status, tree_id, message
            elif subject_level == "PARENT":
                # Create new parent subject
                status, subject_id, message = self.create_parent_subject(
                    tree_id=parent_subject_id, subject_name=name, created_by=created_by
                )
                logger.debug("create_parent_subject_successful", action="create_subject_tree_with_rule", status=status, subject_id=subject_id, message=message)
                return "PARENT", status, subject_id, message
            elif subject_level == "CHILD":
                # Create new child subject
                status, subject_id, message = self.create_child_subject(
                    subject_name=name, subject_parent_id=parent_subject_id, rules=rules, created_by=created_by
                )
                logger.debug("create_child_subject_successful", action="create_subject_tree_with_rule", status=status, subject_id=subject_id, message=message)
                return "CHILD", status, subject_id, message
            else:
                return "NONE", False, "", "Invalid subject level"
        except PyMongoError as e:
            logger.error("subject_tree_creation_failed", action="create_subject_tree_with_rule", **{"error.code": "DB", "error.message": str(e)}, name=name, exc_info=True)
            raise

    def delete_subject(self, subject_id: str) -> Tuple[bool, str]:
        try:
            # ── Check if it's a Tree ──────────────────────────────────────────
            tree = self.tree_collection.find_one({"tree_id": subject_id})
            if tree:
                # Lấy tất cả subject_id thuộc tree này
                all_subject_ids = [
                    s["subject_id"]
                    for s in self.subject_tree_collection.find(
                        {"tree_id": subject_id},
                        {"subject_id": 1, "_id": 0}
                    )
                ]

                # Pull toàn bộ subject_id (CHILD) ra khỏi tree_ids trên documents
                if all_subject_ids:
                    self.law_document_collection.update_many(
                        {"tree_ids": {"$in": all_subject_ids}},
                        {"$pull": {"tree_ids": {"$in": all_subject_ids}}}
                    )

                # Xoá tree và toàn bộ subjects thuộc tree
                self.tree_collection.delete_one({"tree_id": subject_id})
                deleted_count = self.subject_tree_collection.delete_many(
                    {"tree_id": subject_id}
                ).deleted_count

                logger.info(
                    "delete_tree_successful",
                    action="delete_subject",
                    tree_id=subject_id,
                    subjects_deleted=deleted_count,
                    subject_ids_pulled=len(all_subject_ids),
                )
                return True, f"Tree and {deleted_count} related subjects deleted successfully"

            # ── Check if it's a Subject ───────────────────────────────────────
            subject = self.subject_tree_collection.find_one({"subject_id": subject_id})
            if not subject:
                return False, "Tree or subject not found"

            subject_level = subject.get("subject_level")

            if subject_level == "PARENT":
                # Lấy tất cả CHILD thuộc parent này
                child_subject_ids = [
                    s["subject_id"]
                    for s in self.subject_tree_collection.find(
                        {"subject_parent_id": subject_id},
                        {"subject_id": 1, "_id": 0}
                    )
                ]
                ids_to_pull = child_subject_ids + [subject_id]

                # Pull toàn bộ khỏi tree_ids trên documents
                if ids_to_pull:
                    self.law_document_collection.update_many(
                        {"tree_ids": {"$in": ids_to_pull}},
                        {"$pull": {"tree_ids": {"$in": ids_to_pull}}}
                    )

                # Xoá children trước, sau đó xoá chính parent
                deleted_count = self.subject_tree_collection.delete_many(
                    {"subject_parent_id": subject_id}
                ).deleted_count
                self.subject_tree_collection.delete_one({"subject_id": subject_id})

                # Cập nhật count trên Tree
                tree = self.tree_collection.find_one({"tree_id": subject["tree_id"]})
                if tree:
                    self.tree_collection.update_one(
                        {"tree_id": subject["tree_id"]},
                        {"$set": {
                            "count": max(0, tree["count"] - deleted_count),
                            "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_by": "ROOT",
                        }}
                    )

                logger.info(
                    "delete_parent_subject_successful",
                    action="delete_subject",
                    subject_id=subject_id,
                    children_deleted=deleted_count,
                    ids_pulled=ids_to_pull,
                )
                return True, f"Parent subject and {deleted_count} child subjects deleted successfully"

            else:
                # CHILD: chỉ pull subject_id này khỏi tree_ids
                self.law_document_collection.update_many(
                    {"tree_ids": subject_id},
                    {"$pull": {"tree_ids": subject_id}}
                )
                self.subject_tree_collection.delete_one({"subject_id": subject_id})

                # Cập nhật count trên Parent
                parent = self.subject_tree_collection.find_one(
                    {"subject_id": subject["subject_parent_id"]}
                )
                if parent:
                    self.subject_tree_collection.update_one(
                        {"subject_id": parent["subject_id"]},
                        {"$set": {
                            "count": max(0, parent["count"] - 1),
                            "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_by": "ROOT",
                        }}
                    )

                # Cập nhật count trên Tree
                tree = self.tree_collection.find_one({"tree_id": subject["tree_id"]})
                if tree:
                    self.tree_collection.update_one(
                        {"tree_id": subject["tree_id"]},
                        {"$set": {
                            "count": max(0, tree["count"] - 1),
                            "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_by": "ROOT",
                        }}
                    )

                logger.info("delete_child_subject_successful", action="delete_subject", subject_id=subject_id)
                return True, "Child subject deleted successfully"

        except PyMongoError as e:
            logger.error(
                "delete_subject_failed",
                action="delete_subject",
                **{"error.code": "DB", "error.message": str(e)},
                subject_id=subject_id,
                exc_info=True,
            )
            raise

    def update_subject(self, subject_id: str, subject_name: Optional[str] = None, 
                       rules: Optional[dict] = None, 
                       last_modified_by: str = "ROOT") -> Tuple[str, bool]:
        """Update a tree, parent subject, or child subject.

        Args:
            subject_id: ID of the tree or subject to update.
            subject_name: New name, if updating.
            rules: New rules, if updating.
            last_modified_by: User who modified the tree or subject.

        Returns:
            Tuple of (type, status): Type (TREE, PARENT, CHILD) and success status.
        """
        try:
            # Check if it's a tree
            tree = self.tree_collection.find_one({"tree_id": subject_id})
            if tree:
                status = self.update_tree(tree_id=subject_id, tree_name=subject_name, 
                                         last_modified_by=last_modified_by)
                return "TREE", status

            # Check if it's a subject
            subject = self.subject_tree_collection.find_one({"subject_id": subject_id})
            if not subject:
                return "NONE", False

            if subject["subject_level"] == "PARENT":
                status = self.update_parent_subject(subject_id=subject_id, subject_name=subject_name, 
                                                  last_modified_by=last_modified_by)
                return "PARENT", status
            else:  # CHILD
                status = self.update_child_subject(subject_id=subject_id, subject_name=subject_name, 
                                                  rules=rules, last_modified_by=last_modified_by)
                return "CHILD", status
        except PyMongoError as e:
            logger.error("update_subject_failed", action="update_subject", **{"error.code": "DB", "error.message": str(e)}, subject_id=subject_id, exc_info=True)
            raise


    def bulk_write_to_collection(self, collection, updates):
        for i in range(0, len(updates), self.BATCH_SIZE):
            batch = updates[i:i + self.BATCH_SIZE]
            start_time = time.time()
            collection.bulk_write(batch, ordered=False)
            logger.debug("complete_bulk_write_batch", action="bulk_write_to_collection", collection_name=collection.name, elapsed_seconds=round(time.time() - start_time, 2))


    def import_tree_from_excel(
        self, tree_id: str, excel_file_path: str, created_by: str = "System"
    ) -> Tuple[bool, str, List[Dict[str, str]]]:
        """Import a subject tree from an Excel file, returning failed imports.

        Args:
            tree_id: ID of the tree to create.
            excel_file_path: Path to the Excel file.
            created_by: User who initiated the import.

        Returns:
            Tuple[bool, str, List[Dict[str, str]]]: Status, message, and list of failed imports.
            Failed imports format: [{"Cấp cha": str, "Cấp con": str, "Tên văn bản": str}]
        """
        failed_imports = []
        try:
            # Validate file
            if not self.allowed_file(excel_file_path):
                return False, f"Invalid file extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}", failed_imports

            # Read and validate Excel file
            logger.info("read_excel_file_started", action="import_tree_from_excel", file_path=excel_file_path)
            df = pd.read_excel(excel_file_path)
            if df.empty:
                raise pd.errors.EmptyDataError("Excel file is empty")

            required_columns = [
                ImportTreeConfig.PARENT_FIELD,
                ImportTreeConfig.CHILD_FIELD,
                ImportTreeConfig.NAME_FIELD
            ]
            if not all(col in df.columns for col in required_columns):
                return False, f"Excel file must contain columns: {', '.join(required_columns)}", failed_imports

            # Preprocess DataFrame
            logger.info("preprocess_dataframe_started", action="import_tree_from_excel")
            df[ImportTreeConfig.PARENT_FIELD] = df[ImportTreeConfig.PARENT_FIELD].fillna(
                df.index.to_series().apply(lambda x: f"Parent_{x + 1}")
            )
            df[ImportTreeConfig.CHILD_FIELD] = df[ImportTreeConfig.CHILD_FIELD].fillna("")
            df[ImportTreeConfig.NAME_FIELD] = df[ImportTreeConfig.NAME_FIELD].apply(
                lambda x: [i.strip() for i in str(x).split(",")] if isinstance(x, str) else [str(x).strip()]
            )

            # Process parent subjects
            logger.info("process_parent_subjects_started", action="import_tree_from_excel")
            parent_subjects = {}  # parent_name -> subject_id
            parent_ops = []
            for parent_name in df[ImportTreeConfig.PARENT_FIELD].unique():
                parent_id = str(uuid.uuid4())
                parent_ops.append({
                        "tree_id": tree_id,
                        "subject_id": parent_id,
                        "subject_name": parent_name,
                        "created_by": created_by,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_modified_by": created_by,
                        "count": 0,
                        "subject_level": "PARENT",
                        "subject_parent_id": None,
                        "doc_id_includes": [],
                        "rules": {},
                        "status": "ACTIVE",
                        "state": "PENDING",
                        "category": "IMPORT"
                    })
                parent_subjects[parent_name] = parent_id
            if parent_ops:
                self.subject_tree_collection.insert_many(parent_ops)
                logger.info("process_parent_subjects_completed", action="import_tree_from_excel", count=len(parent_subjects))

            # Process keywords
            logger.info("process_keywords_started", action="import_tree_from_excel")
            keyword_ops = []
            keyword_subjects = {}

            existing_keywords = self.law_keywords_collection.find({"status": "ACTIVE"})
            keyword_map = {
                normalize_keyword(k["keyword_name"]): k
                for k in existing_keywords
            }

            for child_name in df[ImportTreeConfig.CHILD_FIELD].unique():
                normalized_name = normalize_keyword(child_name)
                if normalized_name in keyword_map:
                    keyword_subjects[child_name] = keyword_map[normalized_name]["keyword_id"]
                    logger.info("check_keyword_exists", action="import_tree_from_excel", keyword=child_name)
                else:
                    keyword_id = str(uuid.uuid4())
                    keyword_subjects[child_name] = keyword_id
                    if child_name != "":
                        keyword_ops.append({
                            'keyword_id': keyword_id,
                            'keyword_name': child_name,
                            'created_by': created_by,
                            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'last_modified_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'last_modified_by': created_by,
                            'status': 'ACTIVE',
                        })
                        keyword_map[normalized_name] = {
                            "keyword_id": keyword_id
                        }
                        logger.info("create_keyword_successful", action="import_tree_from_excel", keyword=child_name)

            if keyword_ops:
                self.law_keywords_collection.insert_many(keyword_ops)
                logger.info("process_keywords_completed", action="import_tree_from_excel", count=len(keyword_ops))

            
            # Batch map document names
            logger.info("map_document_names_started", action="import_tree_from_excel")
            all_doc_names = set()
            doc_name_to_rows = {}  # doc_name -> List[Dict[parent_name, child_name]]
            for _, row in df.iterrows():
                parent_name = row[ImportTreeConfig.PARENT_FIELD]
                child_name = row[ImportTreeConfig.CHILD_FIELD]
                doc_name = row[ImportTreeConfig.NAME_FIELD][0]
                all_doc_names.add(doc_name)
                if doc_name not in doc_name_to_rows:
                    doc_name_to_rows[doc_name] = []
                doc_name_to_rows[doc_name].append({
                        ImportTreeConfig.PARENT_FIELD: parent_name,
                        ImportTreeConfig.CHILD_FIELD: child_name,
                        ImportTreeConfig.NAME_FIELD: doc_name
                    })
            logger.info("collect_document_names_successful", action="import_tree_from_excel", count=len(list(all_doc_names)))

            doc_name_to_id = self.document_mapper.map_document_names_multithread(list(all_doc_names))
            logger.info("map_documents_completed", action="import_tree_from_excel", count=len(doc_name_to_id))
            for doc_name, rows in doc_name_to_rows.items():
                if doc_name not in doc_name_to_id or not doc_name_to_id[doc_name]:
                    for row in rows:
                        failed_imports.append({
                            ImportTreeConfig.PARENT_FIELD: row[ImportTreeConfig.PARENT_FIELD],
                            ImportTreeConfig.CHILD_FIELD: row[ImportTreeConfig.CHILD_FIELD],
                            ImportTreeConfig.NAME_FIELD: doc_name
                        })
            logger.info("detect_failed_imports_completed", action="import_tree_from_excel", count=len(failed_imports))

            
            # Process child subjects and documents
            logger.info("process_child_subjects_started", action="import_tree_from_excel")
            child_subjects = {}  # child_name -> {parent_id, doc_ids, subject_id}
            doc_ops = []  # doc_name -> subject_id
            for _, row in df.iterrows():
                parent_name = row[ImportTreeConfig.PARENT_FIELD]
                child_name = row[ImportTreeConfig.CHILD_FIELD]
                doc_name = row[ImportTreeConfig.NAME_FIELD][0]
                if not child_name or not parent_name or parent_name not in parent_subjects:
                    continue

                parent_id = parent_subjects[parent_name]
                doc_id = doc_name_to_id.get(doc_name)
                if not doc_id:
                    continue
                
                if child_name not in child_subjects:
                    child_id = str(uuid.uuid4())
                    child_subjects[child_name] = {
                        "subject_id": child_id,
                        "parent_id": parent_id,
                        "doc_ids": [doc_id],
                        "tree_id": tree_id
                    }
                else:
                    child_subjects[child_name]["doc_ids"].append(doc_id)                
                
                doc_ops.append(UpdateOne(
                    {"doc_id": doc_id},
                    {"$set": {"keyword_ids": [keyword_subjects[child_name]]}}
                ))
            
            # Bulk insert child subjects
            logger.info("insert_child_subjects_started", action="import_tree_from_excel")
            child_ops = []
            for child_name, child in child_subjects.items():
                child_id = child["subject_id"]
                parent_id = child["parent_id"]
                doc_ids = child["doc_ids"]
                child_ops.append({
                    "tree_id": tree_id,
                    "subject_id": child_id,
                    "subject_name": child_name,
                    "created_by": created_by,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_modified_by": created_by,
                    "count": len(doc_ids),
                    "subject_level": "CHILD",
                    "subject_parent_id": parent_id,
                    "doc_id_includes": doc_ids,
                    "rules": {'keywordCodes': [keyword_subjects[child_name]]},
                    "status": "ACTIVE",
                    "state": "PENDING",
                    "category": "IMPORT"
                })
            if child_ops:
                self.subject_tree_collection.insert_many(child_ops)
                logger.info("insert_child_subjects_completed", action="import_tree_from_excel", count=len(child_ops))

            # Update law_document: add child_id vào tree_ids theo doc_ids
            doc_updates = []
            for child_name, child in child_subjects.items():
                child_id = child["subject_id"]
                doc_ids = child["doc_ids"]

                doc_updates.append(
                    UpdateMany(
                        {"doc_id": {"$in": doc_ids}},
                        {"$addToSet": {"tree_ids": child_id}}  # tránh trùng
                    )
                )
            if doc_updates:
                self.law_document_collection.bulk_write(doc_updates, ordered=False)
                logger.info("update_law_documents_completed", action="import_tree_from_excel", count=len(doc_updates))

            # Update parent subject counts
            logger.info("update_parent_subject_counts_started", action="import_tree_from_excel")
            pipeline = [
                {"$match": {"tree_id": tree_id, "subject_level": "CHILD"}},
                {"$group": {"_id": "$subject_parent_id", "doc_ids": {"$push": "$doc_id_includes"}}}
            ]
            parent_counts = self.subject_tree_collection.aggregate(pipeline)
            parent_updates = [
                UpdateOne(
                    {"subject_id": parent["_id"], "subject_level": "PARENT"},
                    {"$set": {"count": len({str(item) for sublist in parent["doc_ids"] for item in sublist}), "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
                )
                for parent in parent_counts
            ]
            if parent_updates:
                self.subject_tree_collection.bulk_write(parent_updates, ordered=False)
                logger.info("update_parent_subject_counts_completed", action="import_tree_from_excel", count=len(parent_updates))

                        
            # Update tree count
            logger.info("update_tree_count_started", action="import_tree_from_excel")
            tree_counts = sum(len({str(item) for sublist in parent["doc_ids"] for item in sublist}) for parent in parent_counts)
            self.tree_collection.update_one(
                {"tree_id": tree_id},
                {"$set": {"count": tree_counts, "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
            )

            # Compile result
            logger.info("compile_result_started", action="import_tree_from_excel")
            message = f"Tree {tree_id} imported with {len(parent_subjects)} parent subjects and {len(child_subjects)} child subjects"
            if failed_imports:
                message += f". {len(failed_imports)} documents failed to import"

            
            # Clean up temporary file
            logger.info("clean_temporary_file_started", action="import_tree_from_excel", file_path=excel_file_path)
            if os.path.exists(excel_file_path):
                os.remove(excel_file_path)
                logger.debug("delete_temporary_file_successful", action="import_tree_from_excel", file_path=excel_file_path)
            else:
                logger.warning("delete_temporary_file_not_found", action="import_tree_from_excel", file_path=excel_file_path)
            return True, message, failed_imports, doc_ops

        except pd.errors.EmptyDataError:
            return False, "Excel file is empty", failed_imports, None
        except pd.errors.ParserError:
            return False, "Invalid Excel file format", failed_imports, None
        except PyMongoError as e:
            logger.error("import_tree_failed", action="import_tree_from_excel", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return False, f"Database error: {str(e)}", failed_imports, None
        except Exception as e:
            logger.error("import_tree_failed", action="import_tree_from_excel", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return False, f"Unexpected error: {str(e)}", failed_imports, None
    
    # def update_subject_ids_with_doc_id(self, doc_id: str, update_subject_ids: list):        
    #     query = {"doc_id_includes": {"$in": [doc_id]}}        
    #     subjects = list(self.subject_tree_collection.find(query))
    #     logger.info("subjects_retrieved", count=len(subjects))   

    #     exist_subject_ids = []
    #     for subject in subjects:
    #         if subject.get("subject_id", None) is not None:
    #             exist_subject_ids.append(subject.get("subject_id"))
        
    #     for subject_id in update_subject_ids:
    #         if subject_id not in exist_subject_ids:
    #             self.add_document_to_subject(doc_id=doc_id, subject_id=subject_id)
        
    #     for subject_id in exist_subject_ids:
    #         if subject_id not in update_subject_ids or len(update_subject_ids) == 0:
    #             self.remove_document_to_subject(doc_id=doc_id, subject_id=subject_id)
    def update_subject_ids_with_doc_id(self, doc_id: str, keyword_ids: list):
        """
        Sync doc_id vào subject tree khi keyword_ids thay đổi.
        - So sánh keyword_ids cũ (từ document hiện tại) vs keyword_ids
        - Add doc_id vào các subject mới được match
        - Remove doc_id khỏi các subject không còn match
        - Cập nhật tree_ids trên law_document
        """
        try:
            # ── 1. Lấy document hiện tại để biết keyword_ids & tree_ids cũ ──────
            document = self.law_document_collection.find_one({"doc_id": doc_id})
            if not document:
                logger.warning("update_subject_ids_not_found", action="update_subject_ids_with_doc_id", doc_id=doc_id)
                return False

            old_keyword_ids = set(document.get("keyword_ids", []))
            keyword_ids = set(keyword_ids)
            current_tree_ids = set(document.get("tree_ids", []))

            if old_keyword_ids == keyword_ids:
                return True
            added_keyword_ids   = keyword_ids - old_keyword_ids
            removed_keyword_ids = old_keyword_ids - keyword_ids
            all_child_subjects = list(
                self.subject_tree_collection.find({"subject_level": "CHILD"})
            )
            
            all_relevant_keyword_ids = old_keyword_ids | keyword_ids
            keywords = list(
                self.law_keywords_collection.find(
                    {"keyword_id": {"$in": list(all_relevant_keyword_ids)}}
                )
            )
            keyword_map = {
                normalize_keyword(k["keyword_name"]): k["keyword_id"]
                for k in keywords
            }
            # ── 5. Xác định subject nào match với added/removed keywords ─────────
            subjects_to_add    = []  # subject_id cần add doc_id vào
            subjects_to_remove = []  # subject_id cần remove doc_id khỏi

            for subject in all_child_subjects:
                norm_name = normalize_keyword(subject["subject_name"])
                matched_keyword_id = keyword_map.get(norm_name)
                if matched_keyword_id is None:
                    continue
                if matched_keyword_id in added_keyword_ids:
                    subjects_to_add.append(subject["subject_id"])
                if matched_keyword_id in removed_keyword_ids:
                    subjects_to_remove.append(subject["subject_id"])

            # ── 6. Thực hiện add/remove doc_id trên subject tree ─────────────────
            for subject_id in subjects_to_add:
                self.add_document_to_subject(subject_id, doc_id)

            for subject_id in subjects_to_remove:
                self.remove_document_to_subject(subject_id, doc_id)

            new_tree_ids = (current_tree_ids | set(subjects_to_add)) - set(subjects_to_remove)
            self.law_document_collection.update_one(
                {"doc_id": doc_id},
                {"$set": {
                    "keyword_ids": list(keyword_ids),
                    "tree_ids":    list(new_tree_ids),
                }}
            )

            logger.info("update_subject_ids_completed", action="update_subject_ids_with_doc_id", doc_id=doc_id, added_subjects=subjects_to_add)
            return True

        except PyMongoError as e:
            logger.error("update_subject_ids_failed", action="update_subject_ids_with_doc_id", **{"error.code": "DB", "error.message": str(e)}, doc_id=doc_id, exc_info=True)
            raise

if __name__ == "__main__":
    # path_file_excel = "/home/ubuntu/projects/AI/git/users/giangnv/law-document-sync-core-service/core/v03/tree_processor/data/Bộ Pháp điển 2025 04 28.xlsx"
    # # tree_name = "Bộ Pháp điển 2025 04 28"
    # tree_id = "Tree_ID_TEST_IMPORT"
    # created_by = "System"
    
    # import time
    # start_time = time.time()
    # law_tree_manager = LawTreeManager()
    # status, message, failed_imports = law_tree_manager.import_tree_from_excel(tree_id=tree_id, 
    #                                                                         excel_file_path=path_file_excel, 
    #                                                                         created_by=created_by)
    

    document_code = "143494"
    law_tree_manager = LawTreeManager()
    subjects = law_tree_manager.get_subject_ids_with_document_code(document_code)
    logger.info("show_subjects_found_successful", action="__main__", subjects=subjects)

    