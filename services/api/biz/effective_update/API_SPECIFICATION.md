# Tài Liệu Đặc Tả API Cập Nhật Hiệu Lực (Effective Update)

## Tổng Quan
Tài liệu này mô tả các API được sử dụng để truy xuất thông tin cập nhật hiệu lực cho văn bản và điều khoản luật, dựa trên các mối quan hệ như sửa đổi, thay thế, bãi bỏ, v.v.

## Các Endpoints

### 1. Lấy Danh Sách Văn Bản Cập Nhật Hiệu Lực

*   **URL:** `/effective-update/document/list`
*   **Phương thức:** `GET`
*   **Mô tả:** Lấy danh sách các văn bản có mối quan hệ sửa đổi (`AMEND`) hoặc thay thế (`REPLACE`) với văn bản nguồn được chỉ định.
*   **Tham số Query (Query Parameters):**
    *   `doc_id` (Chuỗi, Bắt buộc): ID của văn bản nguồn (source document) cần tra cứu.
*   **Phản hồi thành công (200 OK):**
    *   **Cấu trúc JSON:**
        ```json
        {
            "code": "200",
            "message": "Success",
            "data": [
                {
                    "target_id": "ID văn bản đích",
                    "reference_type": "Loại mối quan hệ (AMEND hoặc REPLACE)",
                    "doc_name": "Tên văn bản đích"
                }
            ]
        }
        ```
*   **Phản hồi lỗi:**
    *   **400 Bad Request:** Khi thiếu tham số `doc_id` hoặc lỗi dữ liệu.
        ```json
        {
            "code": "400",
            "message": "doc_id is required",
            "data": null
        }
        ```
    *   **500 Internal Server Error:** Lỗi hệ thống.

### 2. Lấy Danh Sách Điều Khoản Cập Nhật Hiệu Lực

*   **URL:** `/effective-update/article/list`
*   **Phương thức:** `GET`
*   **Mô tả:** Lấy danh sách các điều khoản có mối quan hệ liên quan đến hiệu lực (bãi bỏ, thay thế, sửa đổi, bổ sung) với điều khoản nguồn được chỉ định.
*   **Tham số Query (Query Parameters):**
    *   `article_id` (Chuỗi, Bắt buộc): ID của điều khoản nguồn (source article) cần tra cứu.
*   **Logic lọc:** API chỉ trả về các mối quan hệ mà `reference_type` (không phân biệt hoa thường) chứa một trong các từ khóa:
    *   "bãi bỏ"
    *   "thay thế"
    *   "sửa đổi"
    *   "bổ sung"
*   **Phản hồi thành công (200 OK):**
    *   **Cấu trúc JSON:**
        ```json
        {
            "code": "200",
            "message": "Success",
            "data": [
                {
                    "target_id": "ID điều khoản đích",
                    "article_title": "Tiêu đề điều khoản đích",
                    "reference_type": "Loại mối quan hệ gốc",
                    "doc_id": "ID văn bản chứa điều khoản đích",
                    "doc_name": "Tên văn bản chứa điều khoản đích"
                }
            ]
        }
        ```
*   **Phản hồi lỗi:**
    *   **400 Bad Request:** Khi thiếu tham số `article_id`.
        ```json
        {
            "code": "400",
            "message": "article_id is required",
            "data": null
        }
        ```
    *   **500 Internal Server Error:** Lỗi hệ thống.
