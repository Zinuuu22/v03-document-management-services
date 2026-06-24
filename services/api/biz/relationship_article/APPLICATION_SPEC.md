# Tài liệu URD - RelationshipDraft API

## 1. Tổng quan
Tài liệu này mô tả các API quản lý mối quan hệ giữa các bản nháp tài liệu pháp luật. Các API này cho phép thêm, cập nhật, xem và xóa các mối quan hệ giữa các tài liệu.

## 2. Danh sách API

### 2.1. Thêm mối quan hệ vào bản nháp
- **Endpoint**: `POST /relationship-draft/add/<idOrCode>`
- **Mô tả**: Thêm các mối quan hệ mới vào một bản nháp tài liệu
- **Request Body**:
  ```json
  {
    "replace": ["DOC001", "DOC002"],
    "amend": ["DOC003"],
    "repeal_full": ["DOC004"]
  }
  ```
- **Response thành công (200)**:
  ```json
  {
    "data": null,
    "code": "200",
    "message": "Added relationships to draft and updated law references successfully"
  }
  ```
- **Mã lỗi**:
  - 400: Dữ liệu đầu vào không hợp lệ
  - 404: Không tìm thấy bản nháp
  - 500: Lỗi server

### 2.2. Cập nhật mối quan hệ của bản nháp
- **Endpoint**: `POST /relationship-draft/update/<idOrCode>`
- **Mô tả**: Cập nhật toàn bộ mối quan hệ của một bản nháp
- **Request Body**:
  ```json
  {
    "replace": ["DOC001", "DOC005"],
    "amend": ["DOC003", "DOC006"],
    "repeal_full": []
  }
  ```
- **Response thành công (200)**:
  ```json
  {
    "data": null,
    "code": "200",
    "message": "Updated relationships in draft and updated law references successfully"
  }
  ```
- **Mã lỗi**:
  - 400: Dữ liệu đầu vào không hợp lệ
  - 404: Không tìm thấy bản nháp
  - 500: Lỗi server

### 2.3. Xem mối quan hệ của bản nháp
- **Endpoint**: `GET /relationship-draft/get/<idOrCode>`
- **Mô tả**: Lấy thông tin mối quan hệ của một bản nháp
- **Response thành công (200)**:
  ```json
  {
    "data": {
      "record_id": "DOC001",
      "replace": ["DOC002", "DOC003"],
      "amend": ["DOC004"],
      "repeal_full": [],
      "last_modified": "2025-10-22 10:30:45"
    },
    "code": "200",
    "message": "Success"
  }
  ```
- **Mã lỗi**:
  - 404: Không tìm thấy bản nháp
  - 500: Lỗi server

### 2.4. Xóa bản nháp
- **Endpoint**: `POST /relationship-draft/delete/<idOrCode>`
- **Mô tả**: Xóa hoàn toàn một bản nháp và các mối quan hệ liên quan
- **Response thành công (200)**:
  ```json
  {
    "data": null,
    "code": "200",
    "message": "Draft and its relationships deleted successfully"
  }
  ```
- **Mã lỗi**:
  - 404: Không tìm thấy bản nháp
  - 500: Lỗi server

## 3. Các loại mối quan hệ (VALID_RELATION_TYPES)
- `replace`: Thay thế
- `repeal_full`: Bãi bỏ toàn bộ
- `repeal_apart`: Bãi bỏ một phần
- `amend`: Sửa đổi
- `add`: Bổ sung
- `base`: Căn cứ
- `detail`: Chi tiết

## 4. Lưu ý
- Tất cả các thời gian đều được lưu trữ dưới định dạng `YYYY-MM-DD HH:MM:SS`
- Các API đều yêu cầu xác thực
- Các trường dữ liệu liên quan đến tài liệu đều được lưu dưới dạng mảng các ID tài liệu
- Khi một tài liệu bị xóa, tất cả các mối quan hệ liên quan cũng sẽ bị xóa tự động
