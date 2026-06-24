import os
import sys
import argparse
import json
from datetime import datetime
from pymongo import UpdateOne

# Add project root to sys.path to resolve imports correctly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

try:
    from services.api.core.common.mongo.client import get_mongo_client
    from services.api.constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
except ImportError:
    try:
        # Fallback if executed directly within services/api
        from core.common.mongo.client import get_mongo_client
        from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Please run this script from the project root directory.")
        sys.exit(1)

client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COLLECTION_NAME]
subject_tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COMPONENT_COLLECTION_NAME]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]

def get_existing_doc_ids():
    """Fetch all unique document IDs currently in law_documents_collection."""
    print("Fetching existing document IDs from database...")
    docs = law_documents_collection.find({}, {"doc_id": 1, "_id": 0})
    return set(str(d["doc_id"]) for d in docs)

def process_sync(mode="dry-run"):
    existing_doc_ids = get_existing_doc_ids()
    print(f"Total documents in database: {len(existing_doc_ids)}")
    
    print("Analyzing subject_tree_collection for orphaned document IDs...")
    subjects = list(subject_tree_collection.find({}))
    
    trees_to_update = {} # tree_id -> tree details to update
    subjects_to_update = [] # list of subject updates
    
    backup_data = {
        "trees": [],
        "subjects": []
    }
    
    # 1. First pass: Fix CHILD subjects
    child_subjects = [s for s in subjects if s.get("subject_level") == "CHILD"]
    for subject in child_subjects:
        original_doc_ids = subject.get("doc_id_includes", [])
        
        valid_doc_ids = [d for d in original_doc_ids if str(d) in existing_doc_ids]
        
        if len(valid_doc_ids) != len(original_doc_ids):
            # Orphaned documents found
            subjects_to_update.append({
                "subject_id": subject["subject_id"],
                "old_doc_ids": original_doc_ids,
                "new_doc_ids": valid_doc_ids,
                "old_count": subject.get("count", 0),
                "new_count": len(valid_doc_ids),
                "original_doc": subject # for backup
            })
            
    # Map current states for simulated bottom-up count calculation
    simulated_subject_map = {s["subject_id"]: dict(s) for s in subjects}
    
    # Apply simulated updates to child subjects
    for update in subjects_to_update:
        s_id = update["subject_id"]
        simulated_subject_map[s_id]["doc_id_includes"] = update["new_doc_ids"]
        simulated_subject_map[s_id]["count"] = update["new_count"]
        
    # Recalculate PARENT counts
    parent_subjects = [s for s in subjects if s.get("subject_level") == "PARENT"]
    for parent in parent_subjects:
        children = [s for s in simulated_subject_map.values() if s.get("subject_parent_id") == parent["subject_id"] and s.get("subject_level") == "CHILD"]
        new_count = sum(c.get("count", 0) for c in children)
        if new_count != parent.get("count", 0):
            subjects_to_update.append({
                "subject_id": parent["subject_id"],
                "old_doc_ids": parent.get("doc_id_includes", []),
                "new_doc_ids": parent.get("doc_id_includes", []),
                "old_count": parent.get("count", 0),
                "new_count": new_count,
                "original_doc": parent
            })
            simulated_subject_map[parent["subject_id"]]["count"] = new_count

    # Recalculate TREE counts
    trees = list(tree_collection.find({}))
    for tree in trees:
        # Tree count is the sum of all its CHILD counts
        children_in_tree = [s for s in simulated_subject_map.values() if s.get("tree_id") == tree["tree_id"] and s.get("subject_level") == "CHILD"]
        new_tree_count = sum(c.get("count", 0) for c in children_in_tree)
        
        if new_tree_count != tree.get("count", 0):
            trees_to_update[tree["tree_id"]] = {
                "old_count": tree.get("count", 0),
                "new_count": new_tree_count,
                "original_doc": tree
            }
            
    if not subjects_to_update and not trees_to_update:
        print("No orphaned documents found. All counts are already perfectly synchronized.")
        return
        
    print(f"\nFound {len(subjects_to_update)} subjects and {len(trees_to_update)} trees requiring updates.")
    
    if mode == "dry-run":
        print("\n--- DRY RUN SUMMARY ---")
        for update in subjects_to_update:
            diff = update['old_count'] - update['new_count']
            print(f"Subject {update['subject_id']}: count {update['old_count']} -> {update['new_count']} (-{diff} orphans)")
        for t_id, update in trees_to_update.items():
            print(f"Tree {t_id}: count {update['old_count']} -> {update['new_count']}")
        print("\nRun with --execute to apply these changes safely.")
        return
        
    if mode == "execute":
        # Create Backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"tree_sync_backup_{timestamp}.json"
        
        for update in subjects_to_update:
            doc_copy = dict(update["original_doc"])
            doc_copy["_id"] = str(doc_copy["_id"])
            backup_data["subjects"].append(doc_copy)
            
        for update in trees_to_update.values():
            doc_copy = dict(update["original_doc"])
            doc_copy["_id"] = str(doc_copy["_id"])
            backup_data["trees"].append(doc_copy)
            
        with open(backup_filename, 'w') as f:
            json.dump(backup_data, f, indent=2)
            
        print(f"\nBackup successfully saved to {os.path.abspath(backup_filename)}")
        print("Applying updates to database...")
        
        # Apply Subjects Updates
        if subjects_to_update:
            subject_ops = [
                UpdateOne(
                    {"subject_id": u["subject_id"]},
                    {"$set": {"doc_id_includes": u["new_doc_ids"], "count": u["new_count"]}}
                ) for u in subjects_to_update
            ]
            subject_tree_collection.bulk_write(subject_ops)
                
        # Apply Trees Updates
        if trees_to_update:
            tree_ops = [
                UpdateOne(
                    {"tree_id": t_id},
                    {"$set": {"count": u["new_count"]}}
                ) for t_id, u in trees_to_update.items()
            ]
            tree_collection.bulk_write(tree_ops)
                
        print("\nUpdates applied successfully.")
        print(f"If you need to rollback, simply run: python scripts/sync_tree_counts.py --rollback {backup_filename}")


def process_rollback(backup_file):
    if not os.path.exists(backup_file):
        print(f"Backup file {backup_file} not found.")
        return
        
    print(f"Reading backup from {backup_file}...")
    with open(backup_file, 'r') as f:
        backup_data = json.load(f)
        
    subject_ops = [
        UpdateOne(
            {"subject_id": s["subject_id"]},
            {"$set": {"doc_id_includes": s.get("doc_id_includes", []), "count": s.get("count", 0)}}
        ) for s in backup_data.get("subjects", [])
    ]
        
    tree_ops = [
        UpdateOne(
            {"tree_id": t["tree_id"]},
            {"$set": {"count": t.get("count", 0)}}
        ) for t in backup_data.get("trees", [])
    ]
        
    if subject_ops:
        print(f"Rolling back {len(subject_ops)} subjects to previous state...")
        subject_tree_collection.bulk_write(subject_ops)
        
    if tree_ops:
        print(f"Rolling back {len(tree_ops)} trees to previous state...")
        tree_collection.bulk_write(tree_ops)
        
    print("Rollback completed successfully. Database is exactly as it was before.")

def process_verify():
    print("Verifying tree data integrity...")
    existing_doc_ids = get_existing_doc_ids()
    subjects = list(subject_tree_collection.find({}))
    
    errors = 0
    
    # 1. Verify no orphaned documents
    child_subjects = [s for s in subjects if s.get("subject_level") == "CHILD"]
    for subject in child_subjects:
        orphans = [d for d in subject.get("doc_id_includes", []) if str(d) not in existing_doc_ids]
        if orphans:
            print(f"[ERROR] Subject {subject['subject_id']} has {len(orphans)} orphaned documents.")
            errors += 1
            
        if subject.get("count", 0) != len(subject.get("doc_id_includes", [])):
            print(f"[ERROR] Subject {subject['subject_id']} count mismatch: property says {subject.get('count', 0)}, actual array length is {len(subject.get('doc_id_includes', []))}")
            errors += 1
            
    # 2. Verify PARENT counts = sum of CHILD counts
    parent_subjects = [s for s in subjects if s.get("subject_level") == "PARENT"]
    for parent in parent_subjects:
        children = [s for s in subjects if s.get("subject_parent_id") == parent["subject_id"] and s.get("subject_level") == "CHILD"]
        expected_count = sum(c.get("count", 0) for c in children)
        if parent.get("count", 0) != expected_count:
            print(f"[ERROR] Parent Subject {parent['subject_id']} count mismatch. Expected {expected_count}, got {parent.get('count', 0)}")
            errors += 1
            
    # 3. Verify TREE counts
    trees = list(tree_collection.find({}))
    for tree in trees:
        children_in_tree = [s for s in subjects if s.get("tree_id") == tree["tree_id"] and s.get("subject_level") == "CHILD"]
        expected_count = sum(c.get("count", 0) for c in children_in_tree)
        if tree.get("count", 0) != expected_count:
            print(f"[ERROR] Tree {tree['tree_id']} count mismatch. Expected {expected_count}, got {tree.get('count', 0)}")
            errors += 1
            
    if errors == 0:
        print("\nVerification passed! No orphaned documents found and all tree/subject counts are perfectly synchronized.")
    else:
        print(f"\nVerification failed with {errors} errors. Run with --execute to fix them.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize Tree Document Counts and Remove Orphans")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Print what would be updated without applying changes")
    group.add_argument("--execute", action="store_true", help="Apply changes and create a backup for rollback")
    group.add_argument("--verify", action="store_true", help="Verify the integrity of tree counts and doc_id_includes")
    group.add_argument("--rollback", type=str, metavar="BACKUP_FILE", help="Rollback changes using the backup JSON file")
    
    args = parser.parse_args()
    
    if args.dry_run:
        process_sync(mode="dry-run")
    elif args.execute:
        process_sync(mode="execute")
    elif args.verify:
        process_verify()
    elif args.rollback:
        process_rollback(args.rollback)
