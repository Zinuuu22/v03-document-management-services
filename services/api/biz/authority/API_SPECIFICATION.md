# Authority Management API Specification

## 1. Tổng quan
Module Quản lý thông tin giao quyền cung cấp các API để quản lý thông tin ủy quyền giữa các cơ quan nhà nước, bao gồm:

- Quản lý thông tin cơ quan được giao quyền
- Theo dõi các quy định pháp lý liên quan đến ủy quyền
- Quản lý hiệu lực của các giao quyền

## 2. Authentication
Tất cả các API yêu cầu xác thực thông qua JWT token trong header:
```
Authorization: Bearer <token>
```

## 3. Danh sách API

### 3.1. Danh sách giao quyền
**Endpoint:** `GET /api/v1/authorities`

**Mô tả:** Lấy danh sách các nội dung giao quyền với phân trang và lọc

**Query Parameters:**
| Tên | Kiểu | Bắt buộc | Mô tả |
|-----|------|----------|-------|
| `agency_id` | string | Không | Lọc theo ID cơ quan |
| `status` | enum | Không | Trạng thái: `ACTIVE`, `INACTIVE` |
| `keyword` | string | Không | Từ khóa tìm kiếm |
| `page` | integer | Không | Số trang (mặc định: 1) |
| `limit` | integer | Không | Số bản ghi/trang (mặc định: 20, tối đa: 100) |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "total": 120,
    "page": 1,
    "limit": 20,
    "items": [
      {
        "id": "AUTH-2025-0001",
        "document": {
          "id": "DOC-12345",
          "title": "Nghị định số 12/2025/NĐ-CP"
        },
        "article": {
          "id": "ART-6789",
          "title": "Điều 5. Giao quyền quản lý..."
        },
        "agency": {
          "id": "AGY-0001",
          "name": "Bộ Tài chính"
        },
        "status": "ACTIVE",
        "effective_date": "2025-05-01T00:00:00Z",
        "expire_date": null,
        "created_at": "2025-04-01T10:30:00Z",
        "updated_at": "2025-04-01T10:30:00Z"
      }
    ]
  }
}
```

### 3.2. Lấy danh sách cơ quan
**Endpoint:** `GET /api/v1/authorities/agencies`

**Mô tả:** Lấy danh sách tất cả cơ quan có thông tin giao quyền

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "AGY-0001",
      "code": "MOF",
      "name": "Bộ Tài chính",
      "status": "ACTIVE"
    },
    {
      "id": "AGY-0002",
      "code": "MOT",
      "name": "Bộ Giao thông Vận tải",
      "status": "ACTIVE"
    }
  ]
}
```

### 3.3. Chi tiết giao quyền
**Endpoint:** `GET /api/v1/authorities/{id}`

**Mô tả:** Lấy thông tin chi tiết một bản ghi giao quyền

**Path Parameters:**
- `id` (required): ID của bản ghi giao quyền

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "AUTH-2025-0001",
    "document": {
      "id": "DOC-12345",
      "title": "Nghị định số 12/2025/NĐ-CP"
    },
    "article": {
      "id": "ART-6789",
      "title": "Điều 5. Giao quyền quản lý...",
      "content": "Nội dung chi tiết điều luật..."
    },
    "agency": {
      "id": "AGY-0001",
      "name": "Bộ Tài chính"
    },
    "assigned_content": "Khoản 2 - Điều 5 quy định...",
    "assigned_content_detail": "Điểm b - Khoản 2 - Điều 5 quy định...",
    "effective_date": "2025-05-01T00:00:00Z",
    "expire_date": null,
    "status": "ACTIVE",
    "created_by": "user@example.com",
    "created_at": "2025-04-01T10:30:00Z",
    "updated_at": "2025-04-01T10:30:00Z"
  }
}
```

### 3.4. Tạo mới giao quyền
**Endpoint:** `POST /api/v1/authorities`

**Mô tả:** Tạo mới một bản ghi giao quyền

**Request Body:**
```json
{
  "document_id": "DOC-12345",
  "article_id": "ART-6789",
  "agency_id": "AGY-0001",
  "assigned_content": "Khoản 2 - Điều 5 quy định...",
  "assigned_content_detail": "Điểm b - Khoản 2 - Điều 5 quy định...",
  "effective_date": "2025-05-01",
  "expire_date": null,
  "status": "ACTIVE"
}
```

**Response 201:**
```json
{
  "success": true,
  "message": "Tạo mới thông tin giao quyền thành công",
  "data": {
    "id": "AUTH-2025-0102"
  }
}
```

### 3.5. Cập nhật giao quyền
**Endpoint:** `PUT /api/v1/authorities/{id}`

**Mô tả:** Cập nhật thông tin giao quyền

**Path Parameters:**
- `id` (required): ID của bản ghi cần cập nhật

**Request Body:**
```json
{
  "agency_id": "AGY-0003",
  "assigned_content": "Khoản 3 - Điều 5 quy định...",
  "assigned_content_detail": "Điểm a - Khoản 3 - Điều 5...",
  "effective_date": "2025-06-01",
  "expire_date": null,
  "status": "ACTIVE"
}
```

**Response 200:**
```json
{
  "success": true,
  "message": "Cập nhật thông tin giao quyền thành công"
}
```

### 3.6. Xóa giao quyền
**Endpoint:** `DELETE /api/v1/authorities/{id}`

**Mô tả:** Xóa mềm một bản ghi giao quyền

**Path Parameters:**
- `id` (required): ID của bản ghi cần xóa

**Response 200:**
```json
{
  "success": true,
  "message": "Xóa thông tin giao quyền thành công"
}
```

## 4. Mã lỗi chung
| Mã | Mô tả |
|----|-------|
| 400 | Bad Request - Dữ liệu đầu vào không hợp lệ |
| 401 | Unauthorized - Không có quyền truy cập |
| 403 | Forbidden - Không đủ quyền thực hiện thao tác |
| 404 | Not Found - Không tìm thấy tài nguyên |
| 500 | Internal Server Error - Lỗi hệ thống |

## 5. Yêu cầu phi chức năng

### 5.1. Bảo mật
- Tất cả API yêu cầu xác thực JWT
- Phân quyền chi tiết theo từng chức năng
- Ghi nhận lịch sử truy cập

### 5.2. Hiệu năng
- Thời gian phản hồi trung bình < 500ms
- Hỗ trợ phân trang cho các API danh sách
- Tối ưu hóa truy vấn database

### 5.3. Kiểm thử
- Đạt tối thiểu 80% code coverage
- Có đầy đủ unit test và integration test
- Kiểm thử hiệu năng với ít nhất 1000 request đồng thời

### 5.4. Ghi nhật ký (Logging)
- Ghi log tất cả các thao tác thêm/sửa/xóa
- Lưu trữ log ít nhất 1 năm
- Định dạng log thống nhất theo chuẩn JSON

## 6. Versioning
- Sử dụng version trong URL (v1, v2, ...)
- Hỗ trợ tối thiểu 2 phiên bản API song song
- Thông báo trước ít nhất 3 tháng khi ngừng hỗ trợ phiên bản cũ
