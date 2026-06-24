# **API Quản Lý Đối Tượng Điều Chỉnh Trong Văn Bản Pháp Luật**

**Tác giả**: xAI Generated Document

**Ngày**: Tháng 10, 2025

## **1\. Giới Thiệu**

### **1.1 Mục Đích**

Tài liệu này mô tả các API hỗ trợ quản lý đối tượng điều chỉnh trong văn bản pháp luật, với các tính năng:

* Liệt kê đối tượng điều chỉnh (hỗ trợ lọc theo các tiêu chí).  
* Thêm, sửa, xóa đối tượng điều chỉnh và liên kết với văn bản/điều luật. Hệ thống lưu trữ dữ liệu trong MongoDB, đảm bảo tính chính xác và nhất quán.

### **1.2 Phạm Vi**

Hệ thống tập trung vào:

* Liệt kê đối tượng điều chỉnh với khả năng lọc (theo tên, trạng thái, ngày tạo, v.v.).  
* Thêm mới, sửa đổi, xóa đối tượng điều chỉnh trong collection law\_regulated\_object.  
* Thêm mới, sửa đổi, xóa liên kết đối tượng điều chỉnh trong collection law\_regulated\_object\_mapping.

## **2\. Tổng Quan Hệ Thống**

Hệ thống cho phép người dùng quản lý đối tượng điều chỉnh trong văn bản pháp luật thông qua API. Dữ liệu được lưu trữ trong hai collection MongoDB:

* law\_regulated\_object: Lưu thông tin chi tiết về đối tượng điều chỉnh.  
* law\_regulated\_object\_mapping: Lưu liên kết giữa văn bản và đối tượng điều chỉnh.

## **3\. Biểu Đồ Use Case**

### **3.1 Mô Tả**

**Actor**:

* **Người dùng (User)**: Thực hiện các thao tác liệt kê, thêm, sửa, xóa đối tượng điều chỉnh và liên kết.  
* **Hệ thống (System)**: Xử lý yêu cầu API và lưu trữ dữ liệu.

**Use Cases**:

* **Liệt kê Đối Tượng Điều Chỉnh**: Liệt kê đối tượng điều chỉnh với bộ lọc (tên, trạng thái, ngày tạo, v.v.).  
* **Liệt kê Liên Kết Đối Tượng Điều Chỉnh**: Liệt kê liên kết với bộ lọc (theo văn bản, loại quan hệ).  
* **Thêm Đối Tượng Điều Chỉnh**: Thêm đối tượng điều chỉnh mới vào law\_regulated\_object.  
* **Thêm Liên Kết Đối Tượng Điều Chỉnh**: Tạo liên kết giữa văn bản và đối tượng điều chỉnh.  
* **Sửa Đối Tượng Điều Chỉnh**: Cập nhật thông tin đối tượng điều chỉnh.  
* **Sửa Liên Kết Đối Tượng Điều Chỉnh**: Cập nhật thông tin liên kết (ví dụ: relation\_type).  
* **Xóa Đối Tượng Điều Chỉnh**: Xóa đối tượng điều chỉnh và các liên kết liên quan.  
* **Xóa Liên Kết Đối Tượng Điều Chỉnh**: Xóa một liên kết cụ thể.  
* **Xác Thực Dữ Liệu**: Kiểm tra tính hợp lệ của dữ liệu trước khi lưu.

**Mối Quan Hệ**:

* **Include**:  
  * "Thêm/Sửa Liên Kết Đối Tượng Điều Chỉnh" bao gồm "Xác Thực Dữ Liệu" (kiểm tra ID hợp lệ).  
  * "Xóa Đối Tượng Điều Chỉnh" bao gồm "Xóa Liên Kết Đối Tượng Điều Chỉnh" (xóa tất cả liên kết liên quan).

## **4\. Yêu Cầu Chức Năng**

### **4.1 Liệt Kê Đối Tượng Điều Chỉnh**

* **Mô tả**: Liệt kê danh sách đối tượng điều chỉnh với bộ lọc (tên, trạng thái, ngày tạo, v.v.).  
* **Input**:  
  * Bộ lọc: regulated\_object\_name, status, created\_date, regulated\_object\_id.  
  * Phân trang: page, limit.  
* **Output**: Danh sách đối tượng điều chỉnh, trả về JSON với thông tin chi tiết.  
* **Quy trình**: Gửi yêu cầu API, hệ thống truy vấn law\_regulated\_object và trả về kết quả.

### **4.2 Liệt Kê Liên Kết Đối Tượng Điều Chỉnh**

* **Mô tả**: Liệt kê liên kết với bộ lọc (theo văn bản, loại quan hệ).  
* **Input**:  
  * Bộ lọc: doc\_id, regulated\_object\_id, relation\_type.  
  * Phân trang: page, limit.  
* **Output**: Danh sách liên kết, trả về JSON với thông tin chi tiết.  
* **Quy trình**: Gửi yêu cầu API, hệ thống truy vấn law\_regulated\_object\_mapping và trả về kết quả.

### **4.3 Thêm Đối Tượng Điều Chỉnh**

* **Mô tả**: Thêm đối tượng điều chỉnh mới vào law\_regulated\_object.  
* **Input**: Thông tin đối tượng điều chỉnh (regulated\_object\_id, regulated\_object\_name, description, regulated\_object\_name\_norm, status, created\_by).  
* **Output**: Đối tượng điều chỉnh được lưu, trả về thông báo thành công.  
* **Quy trình**: Gửi yêu cầu API, hệ thống kiểm tra tính hợp lệ và lưu dữ liệu.

### **4.4 Thêm Liên Kết Đối Tượng Điều Chỉnh**

* **Mô tả**: Thêm liên kết giữa văn bản và đối tượng điều chỉnh vào law\_regulated\_object\_mapping.  
* **Input**: doc\_id, regulated\_object\_id, relation\_type, created\_by.  
* **Output**: Liên kết được lưu, trả về thông báo thành công.  
* **Quy trình**: Gửi yêu cầu API, hệ thống kiểm tra ID hợp lệ và lưu.

### **4.5 Sửa Đối Tượng Điều Chỉnh**

* **Mô tả**: Cập nhật thông tin đối tượng điều chỉnh trong law\_regulated\_object.  
* **Input**: regulated\_object\_id, các trường cần cập nhật (regulated\_object\_name, description, regulated\_object\_name\_norm, status, last\_modified\_by).  
* **Output**: Dữ liệu được cập nhật, trả về thông báo thành công.

### **4.6 Sửa Liên Kết Đối Tượng Điều Chỉnh**

* **Mô tả**: Cập nhật liên kết trong law\_regulated\_object\_mapping.  
* **Input**: ID liên kết, các trường cần cập nhật (relation\_type, last\_modified\_by).  
* **Output**: Liên kết được cập nhật, trả về thông báo thành công.

### **4.7 Xóa Đối Tượng Điều Chỉnh**

* **Mô tả**: Xóa đối tượng điều chỉnh khỏi law\_regulated\_object và các liên kết liên quan.  
* **Input**: regulated\_object\_id.  
* **Output**: Đối tượng điều chỉnh và liên kết được xóa, trả về thông báo thành công.

### **4.8 Xóa Liên Kết Đối Tượng Điều Chỉnh**

* **Mô tả**: Xóa một liên kết khỏi law\_regulated\_object\_mapping.  
* **Input**: ID liên kết.  
* **Output**: Liên kết được xóa, trả về thông báo thành công.

## **5\. Yêu Cầu Phi Chức Năng**

* **Hiệu suất**: Xử lý yêu cầu trong vòng 1 giây với dữ liệu dưới 10,000 bản ghi.  
* **Bảo mật**: Yêu cầu xác thực người dùng (JWT token).  
* **Tính toàn vẹn dữ liệu**: Kiểm tra tính hợp lệ của doc\_id, regulated\_object\_id trước khi lưu.

## **6\. Mô Hình Dữ Liệu**

### **6.1 Collection: law\_regulated\_object**

| Field Name | Data Type | Description | Constraints/Notes |
| ----- | ----- | ----- | ----- |
| \_id | ObjectId | Khóa chính tự động sinh | Tự động sinh, không thể sửa |
| regulated\_object\_id | String | Mã định danh duy nhất | Required, unique index |
| regulated\_object\_name | String | Tên đối tượng điều chỉnh | Required, max 255 ký tự |
| description | String | Mô tả chi tiết | Optional, hỗ trợ văn bản dài |
| regulated\_object\_name\_norm | Array of Strings | Tên chuẩn hóa | Required, max 255 ký tự |
| status | String | Trạng thái (Active, Inactive) | Optional, default "Active" |
| created\_date | String or ISODate | Ngày tạo | Required, mặc định thời gian hệ thống |
| created\_by | String | Người tạo | Required, max 100 ký tự |
| last\_modified | String or ISODate | Ngày sửa cuối | Optional, cập nhật tự động |
| last\_modified\_by | String | Người sửa cuối | Optional, max 100 ký tự |

### **6.2 Collection: law\_regulated\_object\_mapping**

| Field Name | Data Type | Description | Constraints/Notes |
| ----- | ----- | ----- | ----- |
| \_id | ObjectId | Khóa chính tự động sinh | Tự động sinh, không thể sửa |
| doc\_id | String | Mã định danh văn bản | Required, khớp với Documents |
| regulated\_object\_id | String | Mã định danh đối tượng điều chỉnh | Required, khớp với law\_regulated\_object |
| relation\_type | String | Loại quan hệ (Primary, Secondary) | Optional, default "Primary" |
| created\_date | String or ISODate | Ngày tạo | Required, mặc định thời gian hệ thống |
| created\_by | String | Người tạo | Required, max 100 ký tự |
| last\_modified | String or ISODate | Ngày sửa cuối | Optional, cập nhật tự động |
| last\_modified\_by | String | Người sửa cuối | Optional, max 100 ký tự |

## **7\. Đặc Tả API**

### **7.1 API Liệt Kê Đối Tượng Điều Chỉnh**

* **Endpoint**: GET /api/regulated-objects  
* **Description**: Liệt kê đối tượng điều chỉnh với bộ lọc và phân trang.  
* **Query Parameters**:  
  * regulated\_object\_name: Tên đối tượng (hỗ trợ tìm kiếm gần đúng bằng regex).  
  * status: Trạng thái (Active, Inactive, Archived).  
  * created\_date\_from, created\_date\_to: Khoảng thời gian tạo (định dạng YYYY-MM-DD).  
  * regulated\_object\_id: Mã định danh đối tượng.  
  * page: Trang hiện tại (mặc định: 1).  
  * limit: Số bản ghi mỗi trang (mặc định: 10, tối đa: 100).  
* **Response**:

json  
`{`

 `"status": "success",`

 `"data": [`

   `{`

     `"_id": "680c7e5fc9b0edc6b7e236e8",`

     `"regulated_object_id": "RO-001-2024",`

     `"regulated_object_name": "Tình hình kinh tế xã hội tỉnh Quảng Nam",`

     `"description": "Đối tượng điều chỉnh liên quan đến dân số, kế hoạch hóa gia đình và phát triển kinh tế - xã hội tại địa phương.",`

     `"regulated_object_name_norm": ["Tình hình kinh tế xã hội tỉnh Quảng Nam"],`

     `"status": "Active",`

     `"created_date": "2025-03-07T16:27:38.000Z",`

     `"created_by": "system",`

     `"last_modified": "2025-05-30T08:08:50.000Z",`

     `"last_modified_by": "admin"`

   `}`

 `],`

 `"pagination": {`

   `"page": 1,`

   `"limit": 10,`

   `"total": 100,`

   `"total_pages": 10`

 `}`

`}`  
---

### **7.2 API Liệt Kê Liên Kết Đối Tượng Điều Chỉnh**

* **Endpoint**: GET /api/regulated-object-mappings  
* **Description**: Liệt kê các liên kết giữa văn bản và đối tượng điều chỉnh với bộ lọc.  
* **Query Parameters**:  
  * doc\_id: Mã định danh văn bản.  
  * regulated\_object\_id: Mã định danh đối tượng điều chỉnh.  
  * relation\_type: Loại quan hệ (Primary, Secondary, Reference).  
  * page, limit: Phân trang.  
* **Response**:

json  
`{`

 `"status": "success",`

 `"data": [`

   `{`

     `"_id": "680c7e5fc9b0edc6b7e236e9",`

     `"doc_id": "635289",`

     `"regulated_object_id": "RO-001-2024",`

     `"relation_type": "Primary",`

     `"created_date": "2025-03-07T16:27:38.000Z",`

     `"created_by": "system",`

     `"last_modified": "2025-05-30T08:08:50.000Z",`

     `"last_modified_by": "admin"`

   `}`

 `],`

 `"pagination": {`

   `"page": 1,`

   `"limit": 10,`

   `"total": 50,`

   `"total_pages": 5`

 `}`

`}`  
---

### **7.3 API Thêm Đối Tượng Điều Chỉnh**

* **Endpoint**: POST /api/regulated-objects  
* **Description**: Thêm mới một đối tượng điều chỉnh vào hệ thống.  
* **Request Body** *(JSON)*:

json  
`{`

 `"regulated_object_id": "RO-001-2024",`

 `"regulated_object_name": "Tình hình kinh tế xã hội tỉnh Quảng Nam",`

 `"description": "Đối tượng điều chỉnh liên quan đến dân số, kế hoạch hóa gia đình và phát triển kinh tế - xã hội tại địa phương.",`

 `"regulated_object_name_norm": ["Tình hình kinh tế xã hội tỉnh Quảng Nam"],`

 `"status": "Active",`

 `"created_by": "system"`

`}`

* **Response**:

json  
`{`

 `"status": "success",`

 `"data": {`

   `"_id": "680c7e5fc9b0edc6b7e236e8",`

   `"regulated_object_id": "RO-001-2024",`

   `"regulated_object_name": "Tình hình kinh tế xã hội tỉnh Quảng Nam",`

   `"description": "Đối tượng điều chỉnh liên quan đến dân số, kế hoạch hóa gia đình và phát triển kinh tế - xã hội tại địa phương.",`

   `"regulated_object_name_norm": ["Tình hình kinh tế xã hội tỉnh Quảng Nam"],`

   `"status": "Active",`

   `"created_date": "2025-03-07T16:27:38.000Z",`

   `"created_by": "system"`

 `},`

 `"message": "Đối tượng điều chỉnh đã được tạo thành công."`

`}`  
---

### **7.4 API Thêm Liên Kết Đối Tượng Điều Chỉnh**

* **Endpoint**: POST /api/regulated-object-mappings  
* **Description**: Tạo liên kết giữa một văn bản và một đối tượng điều chỉnh.  
* **Request Body**:

json  
`{`

 `"doc_id": "635289",`

 `"regulated_object_id": "RO-001-2024",`

 `"relation_type": "Secondary",`

 `"created_by": "system"`

`}`

* **Response**:

json  
`{`

 `"status": "success",`

 `"data": {`

   `"_id": "680c7e5fc9b0edc6b7e236e9",`

   `"doc_id": "635289",`

   `"regulated_object_id": "RO-001-2024",`

   `"relation_type": "Secondary",`

   `"created_date": "2025-03-07T16:27:38.000Z",`

   `"created_by": "system"`

 `},`

 `"message": "Liên kết đối tượng điều chỉnh đã được tạo thành công."`

`}`  
---

### **7.5 API Sửa Đối Tượng Điều Chỉnh**

* **Endpoint**: PUT /api/regulated-objects/:regulated\_object\_id  
* **Description**: Cập nhật thông tin một đối tượng điều chỉnh theo mã định danh.  
* **Request Body** *(chỉ gửi các trường cần cập nhật)*:

json  
`{`

 `"regulated_object_name": "Tình hình kinh tế xã hội tỉnh Quảng Nam (cập nhật)",`

 `"description": "Cập nhật mô tả chi tiết hơn về phát triển kinh tế địa phương.",`

 `"status": "Active",`

 `"last_modified_by": "admin"`

`}`

* **Response**:

json  
`{`

 `"status": "success",`

 `"data": {`

   `"regulated_object_id": "RO-001-2024",`

   `"regulated_object_name": "Tình hình kinh tế xã hội tỉnh Quảng Nam (cập nhật)",`

   `"last_modified": "2025-05-30T08:08:50.000Z",`

   `"last_modified_by": "admin"`

 `},`

 `"message": "Đối tượng điều chỉnh đã được cập nhật thành công."`

`}`  
---

### **7.6 API Sửa Liên Kết Đối Tượng Điều Chỉnh**

* **Endpoint**: PUT /api/regulated-object-mappings/:id  
* **Description**: Cập nhật loại quan hệ hoặc thông tin liên kết.  
* **Request Body**:

json  
`{`

 `"relation_type": "Primary",`

 `"last_modified_by": "admin"`

`}`

* **Response**:

json  
`{`

 `"status": "success",`

 `"data": {`

   `"_id": "680c7e5fc9b0edc6b7e236e9",`

   `"relation_type": "Primary",`

   `"last_modified": "2025-05-30T08:08:50.000Z",`

   `"last_modified_by": "admin"`

 `},`

 `"message": "Liên kết đã được cập nhật thành công."`

`}`  
---

### **7.7 API Xóa Đối Tượng Điều Chỉnh**

* **Endpoint**: DELETE /api/regulated-objects/:regulated\_object\_id  
* **Description**: Xóa đối tượng điều chỉnh và **tất cả liên kết liên quan** trong law\_regulated\_object\_mapping.  
* **Response**:

json  
`{`

 `"status": "success",`

 `"message": "Đối tượng điều chỉnh RO-001-2024 và các liên kết liên quan đã được xóa thành công."`

`}`  
---

### **7.8 API Xóa Liên Kết Đối Tượng Điều Chỉnh**

* **Endpoint**: DELETE /api/regulated-object-mappings/:id  
* **Description**: Xóa một liên kết cụ thể giữa văn bản và đối tượng điều chỉnh.  
* **Response**:

json  
`{`

 `"status": "success",`

 `"message": "Liên kết đã được xóa thành công."`

`}`  
---

### **7.9 Xử Lý Lỗi Chung (Error Responses)**

Tất cả API đều trả về lỗi theo định dạng chuẩn:

json  
`{`

 `"status": "error",`

 `"code": "VALIDATION_ERROR",`

 `"message": "regulated_object_id đã tồn tại.",`

 `"details": [`

   `{`

     `"field": "regulated_object_id",`

     `"issue": "duplicate"`

   `}`

 `]`

`}`

**Các mã lỗi phổ biến**:

| Code | Mô tả |
| ----- | ----- |
| NOT\_FOUND | Không tìm thấy tài nguyên |
| VALIDATION\_ERROR | Dữ liệu đầu vào không hợp lệ |
| INVALID\_REFERENCE | doc\_id hoặc regulated\_object\_id không tồn tại |
| UNAUTHORIZED | Thiếu hoặc token không hợp lệ |
| FORBIDDEN | Không có quyền thực hiện |
