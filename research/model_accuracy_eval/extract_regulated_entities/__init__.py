from core.common.mongo.client import get_mongo_client
import sys
sys.path.append('/home/ubuntu/projects/AI/git/users/haivt/v03-dev/law-document-sync-core-service')

from pymongo import MongoClient
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.llms import LLMs
from constants import LLMsConfigExtractRelationship

llm_instance = LLMs(llms_config=LLMsConfigExtractRelationship)


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]


def generate_regulated_entities(content: str):
    prompt = f"""
# Vai trò: Bạn là chuyên gia pháp lý, có nhiệm vụ đọc hiểu và phân tích nội dung điều luật để trích xuất các chủ thể được nhắc đến hoặc chịu sự điều chỉnh.

# Mục tiêu: Từ nội dung điều luật được cung cấp, hãy xác định và liệt kê các chủ thể (cá nhân, tổ chức, cơ quan, nhóm người, đơn vị hành chính, v.v.) mà điều luật hướng tới, điều chỉnh hoặc quy định nghĩa vụ/quyền hạn.

# Định nghĩa “Chủ thể” trong điều luật:
- Là đối tượng pháp lý cụ thể hoặc nhóm đối tượng có quyền, nghĩa vụ, trách nhiệm hoặc thẩm quyền theo điều luật.
- Bao gồm (nhưng không giới hạn):
+ Cơ quan nhà nước (ví dụ: Bộ Tư pháp, Ủy ban nhân dân, Tòa án, Thanh tra, Cảnh sát,…)
+ Tổ chức (doanh nghiệp, tổ chức xã hội, đơn vị sự nghiệp,…)
+ Cá nhân hoặc nhóm cá nhân (công dân, sĩ quan, người lao động, học sinh,…)
+ Chủ thể đặc thù (chủ đầu tư, người có thẩm quyền xử phạt, người vi phạm, người bị kiểm tra,…)

# Đầu vào:
'{content}'

# Yêu cầu đầu ra:
- Trả về duy nhất một JSON hợp lệ với cấu trúc sau:
{{
  "subjects": [
    {{
      "name": "Tên chủ thể",
      "type": "Loại chủ thể (cá nhân / tổ chức / cơ quan nhà nước / nhóm người / chủ thể đặc thù)",
      "role_in_law": "Vai trò hoặc mối quan hệ của chủ thể trong điều luật (ví dụ: chịu trách nhiệm, được quyền, bị cấm, có thẩm quyền, đối tượng bị kiểm tra...)",
      "example_clause": "Trích dẫn ngắn gọn câu hoặc cụm từ trong điều luật thể hiện sự xuất hiện của chủ thể này"
    }}
  ]
}}

# Lưu ý:
- Chỉ sử dụng thông tin có trong nội dung điều luật – không suy luận từ bên ngoài.
- Nếu có nhiều chủ thể xuất hiện trong cùng điều luật, liệt kê tất cả.
- Không trùng lặp chủ thể (nếu cùng tên, gộp lại và thống nhất loại + vai trò).
- Không thêm giải thích hoặc mô tả ngoài JSON.
"""

    response = llm_instance.llms(prompt)
    return response


if __name__ == '__main__':
    query = {
    "$and": [
        {
            "doc_category": "Văn bản Pháp Luật"
        },
        {
            "issuing_level_id": "1d583b10-0d3e-4a63-b77a-e5c2a23c24cb"
        },
        {
            "doc_effective_status": "Còn hiệu lực"
        },
        {
            "$or": [
                {
                    "type_id": {
                        "$in": [
                            "20250300003WEH",
                            "20250300015YPU",
                            "20250300016FBN",
                            "202503000202MJ"
                        ]
                    }
                }
            ]
        }
    ]
}

    documents = list(law_documents_collection.find(query,{"_id":0, 'doc_id':1}))
    doc_ids = [doc.get('doc_id') for doc in documents]
    articles = list(law_articles_collection.find({'doc_id': {"$in": doc_ids}}))

    results = []
    for article in articles:
        article_title = article['article_title']
        article_content = article['article_content']
        content = article_title + '\n' + article_content
        result = generate_regulated_entities(content)

        results.append({
            'content': content,
            'result': result
        })

    