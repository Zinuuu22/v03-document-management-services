import uuid
def post_process_response(relationships_result, article_id, doc_id=None):
    """
    Chuyển kết quả từ process_article sang format Kafka response chuẩn
    
    Input: relationships_result từ process_article
    - [{{"relationships": [...]}}] nếu success
    - [{{"noted": "Error", "error": "..."}}] nếu error
    - [] nếu không có relationship (skipped)
    
    Output: Standard Kafka response
    """
    
    # Case 1: Empty result (article bị skip do không có legal keywords)
    if not relationships_result or len(relationships_result) == 0:
        return {
            "doc_id": doc_id,
            "article_id": article_id,
            "status": "skipped",
            "reason": "no_legal_reference_or_filtered",
            "relationships": [],
        }
    
    # Case 2: Success result
    # Extract relationships từ result
    relationships = []
    if "relationships" in relationships_result[0]:
        relationships = relationships_result[0]["relationships"]

    for relationship in relationships:
        return {
            "doc_id": doc_id,
            "article_id": article_id,
            "article_relationship_id" : str(uuid.uuid4()),
            "status": "ACTIVE",
            "relationships": relationship,
            "create_date": "",
            "create_by": "root",
            "last_modified":"",
            "last_modified_by": "", 
        }

