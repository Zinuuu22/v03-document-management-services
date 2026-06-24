# **API Quản Lý Quan Hệ Xã Hội Trong Văn Bản Pháp Luật**

**Tác giả**: xAI Generated Document  
**Ngày**: Tháng 10, 2025

## **1\. Giới Thiệu**

### **1.1 Mục Đích**

Tài liệu này mô tả các API hỗ trợ quản lý quan hệ xã hội trong văn bản pháp luật, với các tính năng:

* Liệt kê quan hệ xã hội (hỗ trợ lọc theo các tiêu chí).  
* Thêm, sửa, xóa quan hệ xã hội và liên kết với văn bản/điều luật.  
  Hệ thống lưu trữ dữ liệu trong MongoDB, đảm bảo tính chính xác và nhất quán.

### **1.2 Phạm Vi**

Hệ thống tập trung vào:

* Liệt kê quan hệ xã hội với khả năng lọc (theo tên, trạng thái, ngày tạo, v.v.).  
* Thêm mới, sửa đổi, xóa quan hệ xã hội trong collection `law_social_relation`.  
* Thêm mới, sửa đổi, xóa liên kết quan hệ xã hội trong collection `law_social_relation_mapping`.

## **2\. Tổng Quan Hệ Thống**

Hệ thống cho phép người dùng quản lý quan hệ xã hội trong văn bản pháp luật thông qua API. Dữ liệu được lưu trữ trong hai collection MongoDB:

* `law_social_relation`: Lưu thông tin chi tiết về quan hệ xã hội.  
* `law_social_relation_mapping`: Lưu liên kết giữa văn bản, điều luật và quan hệ xã hội.

## **3\. Biểu Đồ Use Case**

### **3.1 Mô Tả**

**Actor**:

* **Người dùng (User)**: Thực hiện các thao tác liệt kê, thêm, sửa, xóa quan hệ xã hội và liên kết.  
* **Hệ thống (System)**: Xử lý yêu cầu API và lưu trữ dữ liệu.

**Use Cases**:

* **Liệt kê Quan Hệ Xã Hội**: Liệt kê quan hệ xã hội với bộ lọc (tên, trạng thái, ngày tạo, v.v.).  
* **Liệt kê Liên Kết Quan Hệ Xã Hội**: Liệt kê liên kết với bộ lọc (theo văn bản, điều luật, loại quan hệ).  
* **Thêm Quan Hệ Xã Hội**: Thêm quan hệ xã hội mới vào `law_social_relation`.  
* **Thêm Liên Kết Quan Hệ Xã Hội**: Tạo liên kết giữa văn bản, điều luật và quan hệ xã hội.  
* **Sửa Quan Hệ Xã Hội**: Cập nhật thông tin quan hệ xã hội.  
* **Sửa Liên Kết Quan Hệ Xã Hội**: Cập nhật thông tin liên kết (ví dụ: `relation_type`).  
* **Xóa Quan Hệ Xã Hội**: Xóa quan hệ xã hội và các liên kết liên quan.  
* **Xóa Liên Kết Quan Hệ Xã Hội**: Xóa một liên kết cụ thể.  
* **Xác Thực Dữ Liệu**: Kiểm tra tính hợp lệ của dữ liệu trước khi lưu.

**Mối Quan Hệ**:

* **Include**:  
  * "Thêm/Sửa Liên Kết Quan Hệ Xã Hội" bao gồm "Xác Thực Dữ Liệu" (kiểm tra ID hợp lệ).  
  * "Xóa Quan Hệ Xã Hội" bao gồm "Xóa Liên Kết Quan Hệ Xã Hội" (xóa tất cả liên kết liên quan).

## **4\. Yêu Cầu Chức Năng**

### **4.1 Liệt Kê Quan Hệ Xã Hội**

* **Mô tả**: Liệt kê danh sách quan hệ xã hội với bộ lọc (tên, trạng thái, ngày tạo, v.v.).  
* **Input**:  
  * Bộ lọc: `social_relation_name`, `status`, `created_date`, `social_relation_id`.  
  * Phân trang: `page`, `limit`.  
* **Output**: Danh sách quan hệ xã hội, trả về JSON với thông tin chi tiết.  
* **Quy trình**: Gửi yêu cầu API, hệ thống truy vấn `law_social_relation` và trả về kết quả.

### **4.2 Liệt Kê Liên Kết Quan Hệ Xã Hội**

* **Mô tả**: Liệt kê liên kết với bộ lọc (theo văn bản, điều luật, loại quan hệ).  
* **Input**:  
  * Bộ lọc: `doc_id`, `article_id`, `social_relation_id`, `relation_type`.  
  * Phân trang: `page`, `limit`.  
* **Output**: Danh sách liên kết, trả về JSON với thông tin chi tiết.  
* **Quy trình**: Gửi yêu cầu API, hệ thống truy vấn `law_social_relation_mapping` và trả về kết quả.

### **4.3 Thêm Quan Hệ Xã Hội**

* **Mô tả**: Thêm quan hệ xã hội mới vào `law_social_relation`.  
* **Input**: Thông tin quan hệ xã hội (`social_relation_id`, `social_relation_name`, `description`, `status`, `created_by`).  
* **Output**: Quan hệ xã hội được lưu, trả về thông báo thành công.  
* **Quy trình**: Gửi yêu cầu API, hệ thống kiểm tra tính hợp lệ và lưu dữ liệu.

### **4.4 Thêm Liên Kết Quan Hệ Xã Hội**

* **Mô tả**: Thêm liên kết giữa văn bản, điều luật và quan hệ xã hội vào `law_social_relation_mapping`.  
* **Input**: `doc_id`, `article_id`, `social_relation_id`, `relation_type`, `created_by`.  
* **Output**: Liên kết được lưu, trả về thông báo thành công.  
* **Quy trình**: Gửi yêu cầu API, hệ thống kiểm tra ID hợp lệ và lưu.

### **4.5 Sửa Quan Hệ Xã Hội**

* **Mô tả**: Cập nhật thông tin quan hệ xã hội trong `law_social_relation`.  
* **Input**: `social_relation_id`, các trường cần cập nhật (`social_relation_name`, `description`, `status`, `last_modified_by`).  
* **Output**: Dữ liệu được cập nhật, trả về thông báo thành công.

### **4.6 Sửa Liên Kết Quan Hệ Xã Hội**

* **Mô tả**: Cập nhật liên kết trong `law_social_relation_mapping`.  
* **Input**: ID liên kết, các trường cần cập nhật (`relation_type`, `last_modified_by`).  
* **Output**: Liên kết được cập nhật, trả về thông báo thành công.

### **4.7 Xóa Quan Hệ Xã Hội**

* **Mô tả**: Xóa quan hệ xã hội khỏi `law_social_relation` và các liên kết liên quan.  
* **Input**: `social_relation_id`.  
* **Output**: Quan hệ xã hội và liên kết được xóa, trả về thông báo thành công.

### **4.8 Xóa Liên Kết Quan Hệ Xã Hội**

* **Mô tả**: Xóa một liên kết khỏi `law_social_relation_mapping`.  
* **Input**: ID liên kết.  
* **Output**: Liên kết được xóa, trả về thông báo thành công.

## **5\. Yêu Cầu Phi Chức Năng**

* **Hiệu suất**: Xử lý yêu cầu trong vòng 1 giây với dữ liệu dưới 10,000 bản ghi.  
* **Bảo mật**: Yêu cầu xác thực người dùng (JWT token).  
* **Tính toàn vẹn dữ liệu**: Kiểm tra tính hợp lệ của `doc_id`, `article_id`, `social_relation_id` trước khi lưu.

## **6\. Mô Hình Dữ Liệu**

### **6.1 Collection: `law_social_relation`**

| Field Name | Data Type | Description | Constraints/Notes |
| ----- | ----- | ----- | ----- |
| `_id` | ObjectId | Khóa chính tự động sinh | Tự động sinh, không thể sửa |
| `social_relation_id` | String | Mã định danh duy nhất | Required, unique index |
| `social_relation_name` | String | Tên quan hệ xã hội | Required, max 255 ký tự |
| `description` | String | Mô tả chi tiết | Optional, hỗ trợ văn bản dài |
| `social_relation_name_norm` | String | Tên chuẩn hóa | Required, max 255 ký tự |
| `status` | String | Trạng thái (Active, Inactive) | Optional, default "Active" |
| `created_date` | ISODate | Ngày tạo | Required, mặc định thời gian hệ thống |
| `created_by` | String | Người tạo | Required, max 100 ký tự |
| `last_modified` | ISODate | Ngày sửa cuối | Optional, cập nhật tự động |
| `last_modified_by` | String | Người sửa cuối | Optional, max 100 ký tự |

### **6.2 Collection: `law_social_relation_mapping`**

| Field Name | Data Type | Description | Constraints/Notes |
| ----- | ----- | ----- | ----- |
| `_id` | ObjectId | Khóa chính tự động sinh | Tự động sinh, không thể sửa |
| `doc_id` | String | Mã định danh văn bản | Required, khớp với Documents |
| `article_id` | String | Mã định danh điều luật | Required, khớp với Articles |
| `social_relation_id` | String | Mã định danh quan hệ xã hội | Required, khớp với `law_social_relation` |
| `relation_type` | String | Loại quan hệ (Primary, Secondary) | Optional, default "Primary" |
| `created_date` | ISODate | Ngày tạo | Required, mặc định thời gian hệ thống |
| `created_by` | String | Người tạo | Required, max 100 ký tự |
| `last_modified` | ISODate | Ngày sửa cuối | Optional, cập nhật tự động |
| `last_modified_by` | String | Người sửa cuối | Optional, max 100 ký tự |

## **7\. Đặc Tả API**

### **7.1 API Liệt Kê Quan Hệ Xã Hội**

* **Endpoint**: `GET /api/social-relations`  
* **Description**: Liệt kê quan hệ xã hội với bộ lọc.  
* **Query Parameters**:  
  * `social_relation_name`: Tên quan hệ (hỗ trợ tìm kiếm gần đúng).  
  * `status`: Trạng thái (`Active`, `Inactive`).  
  * `created_date_from`, `created_date_to`: Khoảng thời gian tạo.  
  * `page`, `limit`: Phân trang.  
* **Response**:

{  
  "status": "success",  
  "data": \[  
    {  
      "\_id": "680c7e5fc9b0edc6b7e236ec",  
      "social\_relation\_id": "SR-002-2024",  
      "social\_relation\_name": "Quan hệ giáo dục và phát triển xã hội",  
      ...  
    }  
  \],  
  "pagination": { "page": 1, "limit": 10, "total": 100 }  
}

### **7.2 API Liệt Kê Liên Kết Quan Hệ Xã Hội**

* **Endpoint**: `GET /api/social-relation-mappings`  
* **Description**: Liệt kê liên kết quan hệ xã hội với bộ lọc.  
* **Query Parameters**:  
  * `doc_id`, `article_id`, `social_relation_id`, `relation_type`.  
  * `page`, `limit`: Phân trang.  
* **Response**:

{  
  "status": "success",  
  "data": \[  
    {  
      "\_id": "680c7e5fc9b0edc6b7e236ed",  
      "doc\_id": "635289",  
      "article\_id": "ART-002",  
      ...  
    }  
  \],  
  "pagination": { "page": 1, "limit": 10, "total": 50 }  
}

### **7.3 API Thêm Quan Hệ Xã Hội**

* **Endpoint**: `POST /api/social-relations`  
* **Description**: Thêm quan hệ xã hội mới.  
* **Request Body**:

{  
  "social\_relation\_id": "SR-002-2024",  
  "social\_relation\_name": "Quan hệ giáo dục và phát triển xã hội",  
  "description": "Mối quan hệ liên quan đến giáo dục và phát triển cộng đồng.",  
  "social\_relation\_name\_norm": "Quan he giao duc va phat trien xa hoi",  
  "status": "Active",  
  "created\_by": "user1"  
}

* **Response**:

{  
  "status": "success",  
  "data": {  
    "\_id": "680c7e5fc9b0edc6b7e236ec",  
    "social\_relation\_id": "SR-002-2024",  
    ...  
  }  
}

### **7.4 API Thêm Liên Kết Quan Hệ Xã Hội**

* **Endpoint**: `POST /api/social-relation-mappings`  
* **Description**: Thêm liên kết quan hệ xã hội.  
* **Request Body**:

{  
  "doc\_id": "635289",  
  "article\_id": "ART-002",  
  "social\_relation\_id": "SR-002-2024",  
  "relation\_type": "Secondary",  
  "created\_by": "user1"  
}

* **Response**:

{  
  "status": "success",  
  "data": {  
    "\_id": "680c7e5fc9b0edc6b7e236ed",  
    ...  
  }  
}

### **7.5 API Sửa Quan Hệ Xã Hội**

* **Endpoint**: `PUT /api/social-relations/:social_relation_id`  
* **Description**: Cập nhật quan hệ xã hội.  
* **Request Body**:

{  
  "social\_relation\_name": "Quan hệ giáo dục và phát triển xã hội (cập nhật)",  
  "description": "Cập nhật mô tả.",  
  "last\_modified\_by": "user1"  
}

* **Response**:

{  
  "status": "success",  
  "data": {  
    "social\_relation\_id": "SR-002-2024",  
    ...  
  }  
}

### **7.6 API Sửa Liên Kết Quan Hệ Xã Hội**

* **Endpoint**: `PUT /api/social-relation-mappings/:id`  
* **Description**: Cập nhật liên kết quan hệ xã hội.  
* **Request Body**:

{  
  "relation\_type": "Primary",  
  "last\_modified\_by": "user1"  
}

* **Response**:

{  
  "status": "success",  
  "data": {  
    "\_id": "680c7e5fc9b0edc6b7e236ed",  
    ...  
  }  
}

### **7.7 API Xóa Quan Hệ Xã Hội**

* **Endpoint**: `DELETE /api/social-relations/:social_relation_id`  
* **Description**: Xóa quan hệ xã hội và liên kết liên quan.  
* **Response**:

{  
  "status": "success",  
  "message": "Quan hệ xã hội SR-002-2024 đã được xóa."  
}

### **7.8 API Xóa Liên Kết Quan Hệ Xã Hội**

* **Endpoint**: `DELETE /api/social-relation-mappings/:id`  
* **Description**: Xóa một liên kết quan hệ xã hội.  
* **Response**:

{  
  "status": "success",  
  "message": "Liên kết đã được xóa."  
}

## **8\. Giả Định và Ràng Buộc**

* **Giả định**:  
  * Collection `Documents` và `Articles` đã tồn tại với `doc_id` và `article_id`.  
  * Hệ thống xác thực người dùng đã được triển khai.  
* **Ràng buộc**:  
  * Các field `doc_id`, `article_id`, `social_relation_id` phải được kiểm tra tính hợp lệ trước khi lưu.
