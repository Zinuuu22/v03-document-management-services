# Đặc Tả API Danh Mục Tài Liệu (Document Category)

## Tổng Quan
API này cho phép quản lý các danh mục tài liệu (Loại văn bản - Document Types).

## Các Endpoints

### 1. Liệt Kê Tất Cả Loại Văn Bản

*   **URL:** `10.0.0.16:5002/v1/document-category/get`
*   **Phương thức:** `GET`
*   **Mô tả:** Lấy danh sách tất cả các loại văn bản hiện có.
*   **Phản hồi:**
    *   **Mã (Code):** 200 OK
    *   **Nội dung:**
        ```json
        {
            "code": 0,
            "message": "Success",
            "data": [
                {
                    "code": "UUID hoặc Mã",
                    "name": "Tên loại văn bản",
                    "createdBy": "system",
                    "createdDate": "2023-10-27 10:00:00",
                    "lastModifiedBy": "system",
                    "lastModified": "2023-10-27 10:00:00",
                    "status": "ACTIVE"
                }
            ]
        }
        ```

### 2. Lấy Loại Văn Bản Theo ID hoặc Mã

*   **URL:** `10.0.0.16:5002/v1/document-category/<idOrCode>`
*   **Phương thức:** `GET`
*   **Mô tả:** Lấy chi tiết một loại văn bản cụ thể bằng MongoDB ObjectId hoặc `type_id`.
*   **Tham số:**
    *   `idOrCode` (Biến đường dẫn): `_id` hoặc `type_id` của loại văn bản.
*   **Phản hồi:**
    *   **Mã (Code):** 200 OK
    *   **Nội dung:**
        ```json
        {
            "code": 0,
            "message": "Success",
            "data": [
                {
                    "code": "UUID hoặc Mã",
                    "name": "Tên loại văn bản",
                    "description": "Mô tả",
                    "createdBy": "system",
                    "createdDate": "2023-10-27 10:00:00",
                    "lastModifiedBy": "system",
                    "lastModified": "2023-10-27 10:00:00",
                    "status": "ACTIVE"
                }
            ]
        }
        ```

### 3. Tạo Loại Văn Bản Mới

*   **URL:** `10.0.0.16:5002/v1/document-category/create`
*   **Phương thức:** `POST`
*   **Mô tả:** Tạo mới một loại văn bản.
*   **Tham số Body:**
    *   `code` (Chuỗi, Tùy chọn): Mã tùy chỉnh cho loại văn bản. Nếu không cung cấp, hệ thống sẽ tự sinh UUID.
    *   `name` (Chuỗi, Bắt buộc): Tên của loại văn bản.
    *   `description` (Chuỗi, Tùy chọn): Mô tả về loại văn bản.
*   **Phản hồi:**
    *   **Mã (Code):** 201 Created
    *   **Nội dung:**
        ```json
        {
            "code": 0,
            "message": "Success",
            "data": {
                "code": "UUID hoặc Mã",
                "name": "Tên loại văn bản",
                "description": "Mô tả",
                "createdBy": "system",
                "createdDate": "2023-10-27 10:00:00",
                "lastModifiedBy": "system",
                "lastModified": "2023-10-27 10:00:00",
                "status": "ACTIVE"
            }
        }
        ```

### 4. Cập Nhật Loại Văn Bản

*   **URL:** `10.0.0.16:5002/v1/document-category/update/<idOrCode>`
*   **Phương thức:** `PUT`
*   **Mô tả:** Cập nhật thông tin một loại văn bản đã tồn tại.
*   **Tham số:**
    *   `idOrCode` (Biến đường dẫn): `_id` hoặc `type_id` của loại văn bản cần cập nhật.
*   **Tham số Body:**
    *   `code` (Chuỗi, Tùy chọn): Nên khớp với mã hiện tại nếu được cung cấp.
    *   `name` (Chuỗi, Bắt buộc): Tên mới cho loại văn bản.
    *   `description` (Chuỗi, Tùy chọn): Mô tả mới.
*   **Phản hồi:**
    *   **Mã (Code):** 200 OK
    *   **Nội dung:**
        ```json
        {
            "code": 0,
            "message": "Success",
            "data": {
                "code": "UUID hoặc Mã",
                "name": "Tên đã cập nhật",
                "description": "Mô tả đã cập nhật",
                "createdBy": "system",
                "createdDate": "2023-10-27 10:00:00",
                "lastModifiedBy": "system",
                "lastModified": "2023-10-28 12:00:00",
                "status": "ACTIVE"
            }
        }
        ```

### 5. Xóa Loại Văn Bản

*   **URL:** `10.0.0.16:5002/v1/document-category/delete/<idOrCode>`
*   **Phương thức:** `DELETE`
*   **Mô tả:** Xóa một loại văn bản.
*   **Tham số:**
    *   `idOrCode` (Biến đường dẫn): `_id` hoặc `type_id` của loại văn bản cần xóa.
*   **Phản hồi:**
    *   **Mã (Code):** 200 OK
    *   **Nội dung:**
        ```json
        {
            "code": 0,
            "message": "Success",
            "data": null
        }
        ```

### 6. Công Bố (Publish) Loại Văn Bản

*   **URL:** `10.0.0.16:5002/v1/document-category/published/<idOrCode>`
*   **Phương thức:** `PUT`
*   **Mô tả:** Đặt trạng thái của loại văn bản thành `ACTIVE` (Hoạt động).
*   **Tham số:**
    *   `idOrCode` (Biến đường dẫn): `_id` hoặc `type_id`.
*   **Phản hồi:**
    *   **Mã (Code):** 200 OK
    *   **Nội dung:** Trả về chi tiết đối tượng đã cập nhật.

### 7. Hủy Công Bố (Unpublish) Loại Văn Bản

*   **URL:** `10.0.0.16:5002/v1/document-category/unpublished/<idOrCode>`
*   **Phương thức:** `PUT`
*   **Mô tả:** Đặt trạng thái của loại văn bản thành `INACTIVE` (Không hoạt động).
*   **Tham số:**
    *   `idOrCode` (Biến đường dẫn): `_id` hoặc `type_id`.
*   **Phản hồi:**
    *   **Mã (Code):** 200 OK
    *   **Nội dung:** Trả về chi tiết đối tượng đã cập nhật.

### 8. Tìm Kiếm Loại Văn Bản

*   **URL:** `10.0.0.16:5002/v1/document-category/<page>/<quantity>`
*   **Phương thức:** `POST`
*   **Mô tả:** Tìm kiếm loại văn bản có phân trang.
*   **Tham số:**
    *   `page` (Biến đường dẫn, Số nguyên): Số trang (bắt đầu từ 1).
    *   `quantity` (Biến đường dẫn, Số nguyên): Số lượng mục trên mỗi trang.
*   **Tham số Body:**
    *   `text` (Chuỗi, Tùy chọn): Từ khóa tìm kiếm cho mã, tên hoặc mô tả.
    *   `status` (Chuỗi, Tùy chọn): Lọc theo trạng thái (ví dụ: "ACTIVE", "INACTIVE").
*   **Phản hồi:**
    *   **Mã (Code):** 200 OK
    *   **Nội dung:**
        ```json
        {
            "code": 0,
            "message": "Document types retrieved successfully",
            "data": {
                "count": 100,
                "models": [
                    {
                        "code": "UUID",
                        "name": "Tên",
                        "description": "Mô tả",
                        "createdBy": "admin",
                        "createdDate": "2023-10-27 10:00:00",
                        "lastModifiedBy": "admin",
                        "lastModified": "2023-10-27 10:00:00",
                        "status": "ACTIVE",
                        "text": "từ khóa đã dùng để tìm"
                    }
                ]
            }
        }
        ```
