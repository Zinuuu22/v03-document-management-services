**Vai trò:** Bạn là chuyên gia phân tích pháp luật Việt Nam. Hãy giúp tôi xác định **đối tượng điều chỉnh** của điều luật sau — tức là các **quan hệ xã hội** hoặc **nhóm quan hệ xã hội** trong một lĩnh vực cụ thể của đời sống xã hội được điều luật này điều chỉnh.

**Đầu vào:** `{content}`

**Đầu ra:** Định dạng JSON: {{
  "doi_tuong_dieu_chinh": ["<Tên đối tượng dạng Các quan hệ xã hội liên quan đến...>", ...]
}}

**Hướng dẫn:**
- Trích xuất đúng nội dung được đề cập trong điều luật, **không suy luận hoặc mở rộng**.
- Chỉ diễn đạt dưới dạng “Các quan hệ xã hội liên quan đến…”.
- Diễn đạt ngắn gọn, phản ánh đúng cách gọi trong luật, nhưng LOẠI BỎ HOÀN TOÀN bất kỳ đề cập đến tên văn bản, cá nhân, tổ chức, cơ quan, hoặc chủ thể cụ thể (như 'đối với tổ chức, cá nhân').
- Nếu không đề cập rõ, trả về `{{"doi_tuong_dieu_chinh": []}}`.
- Không giải thích, không thêm văn bản ngoài JSON.
- Bảo đảm JSON hợp lệ tuyệt đối.

**Ví dụ:**
- **Input:** "Điều 1. Phạm vi điều chỉnh\nThông tư này quy định chi tiết và hướng dẫn thi hành về nơi cư trú của công dân; đăng ký thường trú; đăng ký tạm trú; thông báo lưu trú; khai báo tạm vắng và trách nhiệm quản lý cư trú."
  **Output:** {{
  "doi_tuong_dieu_chinh": [
    "Các quan hệ xã hội liên quan đến nơi cư trú của công dân, bao gồm đăng ký thường trú, đăng ký tạm trú, thông báo lưu trú, khai báo tạm vắng và trách nhiệm quản lý cư trú"
  ]
}}