from core.common.mongo.client import get_mongo_client
import time
from pymongo import MongoClient

import sys
sys.path.append('/home/ubuntu/projects/AI/git/users/haivt/v03-dev/law-document-sync-core-service')

from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.llms import LLMs
from constants import LLMsConfigExtractRelationship

llm_instance = LLMs(llms_config=LLMsConfigExtractRelationship)


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

def generate_social_relations(content: str):
    prompt = f"""
Bạn là chuyên gia pháp lý Việt Nam có nhiệm vụ bóc tách **"QUAN HỆ XÃ HỘI"** được điều chỉnh trong điều luật.

---

### 1. ĐỊNH NGHĨA CHUYÊN MÔN:
- “Quan hệ xã hội” là mối liên hệ giữa người với người (hoặc tổ chức, cơ quan) phát sinh trong quá trình họ tham gia vào các hoạt động xã hội như quản lý, sở hữu, lao động, giao dịch, hành chính, hình sự...
- Một “quan hệ xã hội” chỉ được coi là “quan hệ pháp luật” khi có:
  1. **Chủ thể**: cá nhân, tổ chức, cơ quan nhà nước...
  2. **Khách thể**: hành vi, lợi ích hoặc giá trị xã hội được điều chỉnh.
  3. **Nội dung**: quyền và nghĩa vụ pháp lý được xác lập.
  4. **Căn cứ pháp lý**: điều luật điều chỉnh hành vi đó.

---

### 2. NHIỆM VỤ:
Phân tích nội dung điều luật đầu vào để xác định các **quan hệ xã hội được điều chỉnh**.

Mỗi quan hệ xã hội cần thể hiện rõ:
- Chủ thể tham gia
- Hành vi hoặc loại quan hệ (bản chất xã hội)
- Đối tượng/khách thể bị tác động
- Quyền hoặc nghĩa vụ được xác lập
- Loại quan hệ pháp lý (Dân sự, Hành chính, Hình sự, Lao động, Đất đai, v.v.)
- Căn cứ trích xuất (đoạn, câu trong điều luật thể hiện quan hệ đó)

---

### 3. YÊU CẦU ĐẦU RA:
Chỉ trả về **JSON hợp lệ tuyệt đối**, không kèm lời giải thích hoặc mô tả ngoài JSON.  
Dữ liệu phải tuân theo cấu trúc:

{{
  "social_relations": [
    {{
      "relation_name": "Tên mô tả ngắn gọn về quan hệ xã hội",
      "relation_type": "Dân sự / Hành chính / Hình sự / Lao động / Đất đai / Hôn nhân và gia đình / Quốc phòng - an ninh - trật tự xã hội/ Tố tụng / Tài chính - thuế - ngân sách / Khác",
      "actors": [
        {{"role": "Chủ thể 1", "description": "Mô tả vai trò hoặc quyền của chủ thể 1"}},
        {{"role": "Chủ thể 2", "description": "Mô tả vai trò hoặc nghĩa vụ của chủ thể 2"}}
      ],
      "object": "Đối tượng hoặc lợi ích xã hội bị tác động (ví dụ: đất đai, tài sản, quyền công dân...)",
      "rights_obligations": "Tóm tắt quyền và nghĩa vụ pháp lý giữa các chủ thể",
      "legal_basis": "Trích dẫn câu, cụm hoặc nội dung trong điều luật thể hiện quan hệ này"
    }}
  ]
}}

Nếu điều luật **không chứa quan hệ xã hội rõ ràng**, trả về:
`{{"social_relations": []}}`

---

### 4. NGUYÊN TẮC:
- Chỉ sử dụng thông tin trong **nội dung điều luật**. Không suy diễn từ các văn bản khác.
- Nếu điều luật có nhiều quan hệ xã hội, liệt kê **từng quan hệ riêng biệt**.
- Không thêm mô tả ngoài JSON.

---

### 5. ĐẦU VÀO:
'{content}'

---

### 6. VÍ DỤ MINH HỌA:

**Đầu vào:**
Điều 10. Quyền và nghĩa vụ của người sử dụng đất
Người sử dụng đất được chuyển đổi, chuyển nhượng, cho thuê, thừa kế, tặng cho quyền sử dụng đất theo quy định của pháp luật.
Người sử dụng đất có nghĩa vụ sử dụng đất đúng mục đích, tiết kiệm, hiệu quả.

**Đầu ra:**
{{
  "social_relations": [
    {{
      "relation_name": "Quan hệ chuyển nhượng, tặng cho, thừa kế quyền sử dụng đất",
      "relation_type": "Dân sự",
      "actors": [
        {{"role": "Người sử dụng đất", "description": "Có quyền chuyển nhượng, tặng cho, thừa kế quyền sử dụng đất"}},
        {{"role": "Người nhận chuyển nhượng hoặc người thừa kế", "description": "Được nhận quyền sử dụng đất theo quy định"}}
      ],
      "object": "Quyền sử dụng đất",
      "rights_obligations": "Thiết lập quyền định đoạt và nghĩa vụ tuân thủ pháp luật đất đai",
      "legal_basis": "Khoản 1, Điều 10"
    }},
    {{
      "relation_name": "Quan hệ giữa người sử dụng đất và Nhà nước trong quản lý sử dụng đất",
      "relation_type": "Hành chính",
      "actors": [
        {{"role": "Người sử dụng đất", "description": "Có nghĩa vụ sử dụng đất đúng mục đích, tiết kiệm, hiệu quả"}},
        {{"role": "Cơ quan nhà nước", "description": "Thực hiện chức năng giám sát việc sử dụng đất theo quy định"}}
      ],
      "object": "Việc sử dụng đất",
      "rights_obligations": "Nghĩa vụ tuân thủ pháp luật đất đai và chịu sự giám sát của Nhà nước",
      "legal_basis": "Khoản 2, Điều 10"
    }}
  ]
}}
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
        result = generate_social_relations(content)
        result_json = json.loads(result)
        social_relations = result_json['social_relations']
        if social_relations:
            relation_name = social_relations[0]['relation_name']
            relation_type = social_relations[0]['relation_type']
            actors = social_relations[0]['actors']
            _objects = social_relations[0]['object']
            rights_obligations = social_relations[0]['rights_obligations']
            legal_basis = social_relations[0]['legal_basis']
            
            results.append({
                'content': content,
                'relation_name': relation_name,
                'relation_type': relation_type,
                'actors': [actor['role'] for actor in actors],
                'objects': _objects,
                'rights_obligations': rights_obligations,
                'legal_basis': legal_basis
            })

