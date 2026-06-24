# Prompt 1: Trích xuất mối quan hệ sửa đổi, bổ sung từ văn bản
## VAI TRÒ
Chuyên gia phân tích pháp lý - trích xuất các văn bản pháp luật **bị sửa đổi/bổ sung bởi chính văn bản đầu vào**.

## NGUYÊN TẮC CỐT LÕI (Ưu tiên Loại trừ)
- **QUY TẮC CHUNG:** Văn bản chỉ được xác định là bị sửa đổi/bổ sung khi chính văn bản đầu vào {document_name} là chủ thể thực hiện hành động sửa đổi/bổ sung. Nếu như chủ thể sửa đổi không phải là {document_name} thì không được coi là hành động sửa đổi/bổ sung.
- **CHỈ** xác định các văn bản bị sửa đổi/bổ sung **DO CHÍNH VĂN BẢN ĐẦU VÀO NÀY THỰC HIỆN.**
**Loại bỏ các thuật ngữ CẤM:** **Khi gặp các thuật ngữ sau, bỏ qua ngay lập tức**:
- "hết hiệu lực", "<văn bản> hết hiệu lực kể từ ngày <văn bản> này có hiệu lực thi hành"
- "thay thế <văn bản>"
- "bãi bỏ <văn bản>"

- **QUY TẮC BẮC CẦU:** Nếu văn bản đầu vào sửa đổi, bổ sung văn bản A và văn bản A đã được sửa đổi, bổ sung văn bản B, liệt kê cả A và B. (Ví dụ: "Sửa đổi, bổ sung một số Điều của <văn bản> A đã được sửa đổi bổ sung theo <văn bản> B" -> Trả về cả "<văn bản> A" và "<văn bản> B")
- **TUYỆT ĐỐI KHÔNG** được trả về các văn bản không có trong nội dung điều luật
- **Bắt buộc phải trả về đúng cấu trúc JSON OUTPUT, không giải thích thêm.**

## INPUT:
- Điều luật này nằm trong văn bản: {document_name}
- Tên điều luật: {article_title}
- Nội dung điều luật: {article_content}

## ĐỊNH DẠNG OUTPUT
```json
{{
  "amend": [],
  "add": []
}}
```

## QUY TRÌNH PHÂN TÍCH (LOGIC CHẶT CHẼ)
**BƯỚC 1: KIỂM TRA MÔ HÌM "TRÍCH YẾU VĂN BẢN" (QUAN TRỌNG NHẤT)**
Trước khi lấy bất cứ văn bản nào, hãy kiểm tra xem cụm từ "sửa đổi/bổ sung" có phải là **một phần của tên gọi/mô tả văn bản khác** hay không.
- **Quy tắc nhận diện (Pattern Matching):**
  Nếu cấu trúc câu là: `[<Tên văn bản X> + (có thể kèm Ngày tháng/Số hiệu) + [sửa đổi, bổ sung] + <Tên văn bản Y>]`
  -> **KẾT LUẬN:** Đây là tên/mô tả của "Văn Bản Khác". Hành động sửa đổi này do "Văn Bản Khác" thực hiện.
  -> **HÀNH ĐỘNG:** **BỎ QUA TOÀN BỘ**, không trích xuất gì cả.
- **Ví dụ BẮT BUỘC LOẠI BỎ:**
  + "...<văn bản X> **sửa đổi, bổ sung**..." -> BỎ QUA (Vì <văn bản X> là chủ thể).
  + "...<văn bản Y> về việc **sửa đổi, bổ sung**..." -> BỎ QUA (Vì <văn bản Y> là chủ thể).

**BƯỚC 2: BẮT BUỘC LOẠI TRỪ TỪ KHÓA CẤM (PHẠM VI CÂU)**
Nếu nội dung chứa các từ sau, **BẮT BUỘC PHẢI BỎ QUA** việc trích xuất trong nội dung đó:
1.  **Dẫn chiếu:** "theo quy định tại", "căn cứ", "thực hiện theo".
    * **Lưu ý:** Phạm vi ảnh hưởng của từ "theo quy định tại" bao trùm lên toàn bộ danh sách văn bản liệt kê phía sau nó.
2.  **Trạng thái:** "bãi bỏ", "hết hiệu lực", "thay thế".

**BƯỚC 3: XÁC ĐỊNH HÀNH ĐỘNG CỦA VĂN BẢN ĐẦU VÀO**
Chỉ trích xuất khi thỏa mãn:
- Cụm "Sửa đổi, bổ sung" đứng ở đầu dòng/đầu câu.
- Hoặc cấu trúc: "Điều này sửa đổi, bổ sung [Văn bản X]".
- Hoặc cấu trúc: "Sửa đổi, bổ sung [Văn bản X] quy định tại..."

**BƯỚC 4: TRÍCH XUẤT**
Lấy **tên văn bản ĐẦY ĐỦ đúng như xuất hiện trong văn bản gốc** (gồm loại văn bản, số hiệu, ngày tháng ban hành, cơ quan ban hành và phần trích yếu/nội dung nếu có), chỉ bỏ thành phần Điều/Khoản/Điểm bị sửa đổi. **KHÔNG** được rút gọn tên về dạng "Tên + Số hiệu". Ví dụ: trả về `"Thông tư số 30/2014/TT-BTNMT ngày 02 tháng 6 năm 2014 của Bộ trưởng Bộ Tài nguyên và Môi trường quy định về hồ sơ giao đất, cho thuê đất"`, KHÔNG trả về `"Thông tư số 30/2014/TT-BTNMT"`.

## VÍ DỤ HƯỚNG DẪN
Ví dụ 1 (Lỗi phổ biến - Dẫn chiếu):
Input: "Thực hiện theo <văn bản X> sửa đổi, bổ sung <văn bản Y>."
Phân tích:
- Có "Thực hiện theo" -> Dẫn chiếu -> LOẠI.
- Trước chữ "sửa đổi" là "<văn bản X>" -> Đây là mô tả <văn bản X> -> LOẠI.
Output: `{{ "amend": [], "add": [] }}`

Ví dụ 2 (Đúng - Hành động trực tiếp):
Input: "Sửa đổi, bổ sung khoản 1 Điều 2 <văn bản X>"
Phân tích: Đứng đầu câu, không có tên văn bản khác đứng trước.
Output: `{{ "amend": ["<văn bản X>"], "add": [] }}`

Ví dụ 3 (Phức tạp - Vừa dẫn chiếu vừa sửa đổi):
Input: "Căn cứ <văn bản X> sửa đổi <văn bản Y>. Điều này sửa đổi <văn bản Z>."
Phân tích:
- Mệnh đề 1: "Căn cứ <văn bản X> sửa đổi <văn bản Y>" -> BỎ (Do "Căn cứ" và <văn bản X> làm chủ thể).
- Mệnh đề 2: "Điều này sửa đổi <văn bản Z>" -> LẤY (Do văn bản hiện tại làm chủ thể).
Output: `{{ "amend": ["<văn bản Z>"], "add": [] }}`

Ví dụ 4 (Bắc cầu):
Input: "Sửa đổi, bổ sung một số Điều của <văn bản X> đã được sửa đổi bổ sung theo <văn bản Y>"
Phân tích: Nội dung chứa từ khóa "đã được sửa đổi bổ sung" -> **LẤY CẢ VĂN BẢN X VÀ Y**.
Output: `{{ "amend": ["<văn bản X>", "<văn bản Y>"], "add": [] }}`

Ví dụ 5 (Thuật ngữ cấm):
Input: "<văn bản X> hết hiệu lực kể từ ngày <văn bản Y> này có hiệu lực thi hành"
Phân tích: Nội dung chứa từ khóa "hết hiệu lực" -> **LOẠI**.
Output: `{{ "amend": [], "add": [] }}`

Ví dụ 6 (Thay thế - **Thuật ngữ cấm, phải loại bỏ ngay lập tức**):
Input: "Thay thế <văn bản X>, thay thế điều 1 <văn bản Y>"
Phân tích: Nội dung chứa từ khóa "Thay thế" -> **LOẠI BỎ**.
Output: `{{ "amend": [], "add": [] }}`

Ví dụ 7 (Bãi bỏ - **Thuật ngữ cấm, phải loại bỏ ngay lập tức**):
Input: "Bãi bỏ <văn bản X> được sửa đổi, bổ sung một số điều theo <văn bản Y>"
Phân tích: Nội dung chứa từ khóa "Bãi bỏ" -> **LOẠI BỎ**.
Output: `{{ "amend": [], "add": [] }}`

# Prompt 2: Trích xuất mối quan hệ căn cứ từ văn bản
**Vai trò:** Chuyên gia phân tích pháp lý - trích xuất các mối quan hệ **căn cứ**.

**Nhiệm vụ:**
Dựa vào tên văn bản và nội dung phần mô tả quan hệ văn bản, hãy xác định chính xác văn bản luật đầu vào có quan hệ **căn cứ** với văn bản luật nào

**Input:**
1. Tên văn bản đầu vào: '{document_title}'
2. Nội dung mô tả quan hệ của văn bản đầu vào: '{document_brief}'

**Format of Output:**
{{'base': [<Danh sách các văn bản căn cứ>]}}

**Phân tích**: Tìm kiếm các cấu trúc `Căn cứ + (Điều) + <văn bản>` trong nội dung mô tả quan hệ của văn bản đầu vào và trả về danh sách các văn bản căn cứ.
- Ví dụ: 
    + 'Căn cứ Luật A'
    + 'Căn cứ Nghị định B'
    + 'Căn cứ Điều 1 Luật C'
    + 'Căn cứ Điều 2 và Điều 3 Nghị định D'
    
**Note:**
1. Trả ra câu hỏi như format output yêu cầu và không giải thích, phân tích gì thêm.
2. **QUY TẮC VỀ "LUẬT SỬA ĐỔI, BỔ SUNG" (Văn bản độc lập)**:
   - "Luật sửa đổi, bổ sung một số điều của..." là một văn bản duy nhất, không được tách nhỏ
   - Phải trả về đầy đủ tên văn bản này (thường trong 'base')
   - **Ví dụ**: "Luật sửa đổi, bổ sung một số điều của Luật A, Luật B" → trả về nguyên văn
3. **QUY TẮC "ĐÃ ĐƯỢC SỬA ĐỔI, BỔ SUNG" (Bắc cầu - QUAN TRỌNG)**:
   - **Pattern nhận diện**: "[Văn bản A] + [số hiệu A] + [đã] được sửa đổi, bổ sung... + theo + [Văn bản B] + [số hiệu B]"
   - **Cách xử lý**: BẮT BUỘC tách thành CÁC văn bản RIÊNG BIỆT:
     * Văn bản A (tên + số hiệu A)
     * Văn bản B (tên + số hiệu B)
     * Nếu có nhiều văn bản sửa đổi (Luật số X, Luật số Y), tách TỪNG văn bản với số hiệu riêng
   - **Lưu ý**: 
     * KHÔNG trả về cụm gộp chứa "[đã] được sửa đổi"
     * CÁC văn bản này đều là căn cứ ('base') của văn bản đầu vào
4. **QUY TẮC XỬ LÝ SỐ HIỆU VÀ NGÀY THÁNG**:
   - Nếu văn bản có số hiệu (số .../năm/QH...), phải ghi đầy đủ
   - Nếu có thông tin ngày tháng năm, phải trả về đầy đủ
5. **QUY TẮC "THỰC HIỆN"**:
   - Văn bản có cụm "Thực hiện" hoặc "Thực hiện theo" KHÔNG được coi là căn cứ
   - Chỉ ghi nhận văn bản trước cụm "Thực hiện"
6. **QUY TẮC "BAN HÀNH VĂN BẢN SỬA ĐỔI, BỔ SUNG"**:
   - Nếu ban hành <văn bản> sửa đổi, bổ sung một số điều của <văn bản khác> → KHÔNG coi là căn cứ
7. **QUY TẮC ĐẦU RA**:
   - Đầu ra phải đủ 1 trường: 'base'
   - Chỉ trả ra kết quả nếu nội dung mô tả RÕ RÀNG là loại quan hệ đó
   - Nếu không có quan hệ nào, trả về mảng rỗng []

**VÍ DỤ HƯỚNG DẪN:**
**Ví dụ 1 (Căn cứ Luật sửa đổi, bổ sung):**
- Nội dung văn bản đầu vào: "Căn cứ Luật sửa đổi, bổ sung một số điều của Luật A, Luật B"
- Kết quả trả về:
"base" : ["Luật sửa đổi, bổ sung một số điều của Luật A, Luật B"]

**Ví dụ 2 (Căn cứ Luật đã được sửa đổi, bổ sung):**
- Nội dung văn bản đầu vào: "Căn cứ Luật A **đã được sửa đổi, bổ sung một số điều** theo Luật B"
- Kết quả trả về:
"base" : ["Luật A", "Luật B"]
**Lưu ý:** Luật A khi đó không phải văn bản sửa đổi, bổ sung

**Ví dụ 3:**
- Nội dung văn bản đầu vào: "Căn cứ Luật Doanh nghiệp"
- Kết quả trả về:
"base" : ["Luật Doanh nghiệp"]

**Ví dụ 4:**
- Nội dung văn bản đầu vào: "Căn cứ Luật A **đã được sửa đổi, bổ sung một số điều** theo Luật số B, Luật số C"
- Kết quả trả về:
"base" : ["Luật A", "Luật B", "Luật C"]
**Lưu ý:** Luật A khi đó không phải văn bản sửa đổi, bổ sung

**Ví dụ 5 (Trường hợp `Thực hiện`):**
- Nội dung văn bản đầu vào: "Căn cứ Nghị định A. Thực hiện Quyết định số A"
- Kết quả trả về:
"base" : ["Nghị định A"]
**Lưu ý:** Quyết định A **chỉ được thực hiện**, không phải căn cứ của văn bản đầu vào

**Ví dụ 6 (Trường hợp `ban hành văn bản sửa đổi, bổ sung`):**
- Nội dung văn bản đầu vào: "Bộ trưởng Bộ Tài chính ban hành Thông tư sửa đổi, bổ sung một số điều của Thông tư A; Thông tư B"
- Kết quả trả về:
"base" : []
**Lưu ý:** nội dung có chứa cụm từ "ban hành Thông tư sửa đổi, bổ sung" nên KHÔNG PHẢI căn cứ của văn bản đầu vào

# Prompt 3: Trích xuất mối quan hệ hướng dẫn chi tiết từ văn bản
Bạn là chuyên gia pháp lý. Văn bản đầu vào và điều luật đầu vào quy định chi tiết, quy định cụ thể văn bản pháp luật nào?

## NGUYÊN TẮC CỐT LÕI (BẮT BUỘC)
- Quan hệ "quy định chi tiết / hướng dẫn thi hành" là quan hệ **MỘT CHIỀU, HƯỚNG LÊN**: văn bản đầu vào {document_name} (cấp dưới) quy định chi tiết / hướng dẫn thi hành cho văn bản **CẤP TRÊN** (Hiến pháp, Bộ luật, Luật, Pháp lệnh, Nghị định...).
- Một văn bản **KHÔNG** quy định chi tiết cho văn bản **cùng cấp hoặc thấp hơn**. Ví dụ: một Thông tư KHÔNG thể quy định chi tiết cho một Thông tư hoặc Thông tư liên tịch khác.
- Chỉ những văn bản mà chính {document_name} **triển khai chi tiết** mới được liệt kê. Văn bản chỉ được **dẫn chiếu / áp dụng / thay thế / bãi bỏ** thì KHÔNG thuộc nhóm này.

**Đầu vào:**
- Điều luật này nằm trong văn bản: '{document_name}'
- Tên điều luật: '{article_title}'
- Nội dung điều luật: '{article_content}'

**Format of Output as json:**
{{
    "detail": ["Tên văn bản pháp luật được quy định chi tiết hoặc quy định bởi {document_name}"]
}}

**Example:**
{{
    "detail": ["Luật Doanh nghiệp 2020"]
}}

**Important Note:**
1. Chỉ trả về danh sách các văn bản pháp luật được quy định chi tiết, quy định cụ thể bởi văn bản luật đầu vào.
2. Không giải thích dài dòng và không trả về mã Python hoặc bất kỳ đoạn mã nào khác, không tự ý thu gọn, viết tắt, hãy sửa đổi nội dung của văn bản.
3. Nếu không phát hiện trường hợp văn bản pháp luật được quy định chi tiết, hãy trả về danh sách rỗng.
4. **Trong trường hợp**: `quy định tại <văn bản>` thì đây không phải là quy định chi tiết. Phải bỏ qua.
5. Nếu văn bản quy định chi tiết **đã được sửa đổi, bổ sung** bởi văn bản khác thì phải trả về cả 2 văn bản.
6. **LOẠI BỎ NGAY** các văn bản xuất hiện trong ngữ cảnh **dẫn chiếu / áp dụng**: "theo quy định tại", "căn cứ", "thực hiện theo", "áp dụng theo", "dẫn chiếu". Đây là văn bản được tham chiếu, KHÔNG phải văn bản được quy định chi tiết.
7. **LOẠI BỎ NGAY** các văn bản xuất hiện trong ngữ cảnh **thay thế / bãi bỏ / hết hiệu lực**: "thay thế <văn bản>", "bãi bỏ <văn bản>", "<văn bản> hết hiệu lực". Đây là quan hệ thay thế/bãi bỏ, KHÔNG phải quy định chi tiết.
8. **Mô hình "trích yếu / tên gọi văn bản khác":** Nếu một cụm từ (ví dụ "tạm giữ, tạm giam", "quy hoạch"...) chỉ là **một phần trong TÊN GỌI dài của một văn bản khác** đang được nhắc tới, **KHÔNG** được tách cụm đó ra thành một văn bản độc lập để trả về. Chỉ trả về đúng tên văn bản hoàn chỉnh, và chỉ khi văn bản đó thực sự được {document_name} quy định chi tiết.
9. **Kiểm tra hướng quan hệ:** Trước khi trả về, đối chiếu cấp của văn bản đầu vào {document_name} với từng văn bản ứng viên. Nếu văn bản ứng viên **cùng cấp hoặc thấp hơn** {document_name} (ví dụ {document_name} là Thông tư và ứng viên cũng là Thông tư / Thông tư liên tịch) thì **LOẠI BỎ**.
10. **NHẬN DIỆN CHỦ THỂ (QUAN TRỌNG NHẤT):** Cụm "quy định chi tiết / hướng dẫn thi hành" CHỈ được tính khi **chính {document_name} là chủ thể thực hiện** (thường có dạng "<Văn bản> này quy định chi tiết...", hoặc cụm đứng đầu câu nói về văn bản đầu vào). Nếu cụm "quy định chi tiết / hướng dẫn thi hành" là **một phần trong TÊN GỌI / mô tả của MỘT VĂN BẢN KHÁC** (tức là ngay trước cụm đó là tên + số hiệu của một văn bản khác: "Nghị định số .../NĐ-CP ... quy định chi tiết...", "Thông tư số ... quy định chi tiết thi hành..."), thì chủ thể là VĂN BẢN KHÁC, KHÔNG phải {document_name} → **BỎ QUA TOÀN BỘ cụm này**, không trích xuất văn bản nào trong đó.

**Ví dụ:**
- Văn bản đầu vào: "Luật Doanh nghiệp 2020"
- Điều luật đầu vào: "Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng"
- Nội dung điều luật: "1. Phạm vi điều chỉnh
a) Nghị định này quy định chi tiết về thủ tục đầu tư đặc biệt quy định tại Điều 36a của Luật Đầu tư, được sửa đổi, bổ sung tại khoản 8 Điều 2 của Luật số 57/2024/QH15 sửa đổi, bổ sung một số điều của Luật Quy hoạch, Luật Đầu tư, Luật Đầu tư theo phương thức đối tác công tư và Luật Đấu thầu;
- Kết quả trả về:
```
{{
    "detail": ["Luật Đầu tư", "Luật số 57/2024/QH15 sửa đổi, bổ sung một số điều của Luật Quy hoạch, Luật Đầu tư, Luật Đầu tư theo phương thức đối tác công tư và Luật Đấu thầu"]
}}
```

**Ví dụ (Thông tư quy định chi tiết Bộ luật, có dẫn chiếu và thay thế cần loại bỏ):**
- Văn bản đầu vào: "Thông tư 46/2019/TT-BCA"
- Điều luật đầu vào: "Điều 1. Phạm vi điều chỉnh"
- Nội dung điều luật: "Thông tư này quy định chi tiết trách nhiệm của lực lượng Công an nhân dân trong việc thực hiện các quy định của Bộ luật Tố tụng hình sự năm 2015 về bảo đảm quyền bào chữa... Việc tổ chức cho người bào chữa gặp người bị tạm giữ, tạm giam thực hiện theo quy định tại Điều 10 Thông tư liên tịch số 01/2018/TTLT-BCA-BQP-TANDTC-VKSNDTC về quan hệ phối hợp trong việc thực hiện quy định của Luật Thi hành tạm giữ, tạm giam năm 2015. Thông tư này thay thế Thông tư số 70/2011/TT-BCA."
- Phân tích:
  + "Bộ luật Tố tụng hình sự năm 2015" → là văn bản CẤP TRÊN được Thông tư 46 quy định chi tiết → **GIỮ**.
  + "Thông tư liên tịch số 01/2018/TTLT-BCA-BQP-TANDTC-VKSNDTC" → xuất hiện sau "thực hiện theo quy định tại" (dẫn chiếu) và cùng cấp Thông tư → **LOẠI** (note 6, 9).
  + "Luật Thi hành tạm giữ, tạm giam năm 2015" → chỉ là một phần trong TÊN GỌI/mô tả của Thông tư liên tịch 01/2018, không phải đối tượng được Thông tư 46 quy định chi tiết → **LOẠI** (note 8).
  + "Thông tư số 70/2011/TT-BCA" → xuất hiện sau "thay thế" → quan hệ thay thế, cùng cấp → **LOẠI** (note 7, 9).
- Kết quả trả về:
```
{{
    "detail": ["Bộ luật Tố tụng hình sự năm 2015"]
}}
```

**Ví dụ (Cụm "quy định chi tiết" thuộc TÊN của văn bản khác — BẮT BUỘC bỏ qua):**
- Văn bản đầu vào: "Thông tư A"
- Điều luật đầu vào: "Điều X. Nội quy lao động"
- Nội dung điều luật: "Nội dung nội quy lao động thực hiện theo quy định tại khoản 2 Điều 69 Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm 2020 của Chính phủ quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về điều kiện lao động và quan hệ lao động."
- Phân tích:
  + Toàn bộ nằm sau "thực hiện theo quy định tại" → đây là DẪN CHIẾU (note 6) → bỏ qua.
  + Cụm "quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động" là **mô tả/tên gọi của Nghị định số 145/2020/NĐ-CP** (chủ thể là Nghị định 145, không phải Thông tư A) (note 10) → KHÔNG trích "Bộ luật Lao động", KHÔNG trích "Nghị định số 145/2020/NĐ-CP".
- Kết quả trả về:
```
{{
    "detail": []
}}
```

# Prompt 4: Trích xuất mối quan hệ bãi bỏ từ văn bản
## VAI TRÒ
Bạn là một chuyên gia phân tích pháp lý Việt Nam chuyên trích xuất mối quan hệ `bãi bỏ` giữa các văn bản pháp luật.

## MỤC TIÊU
Từ nội dung của một điều luật, xác định và trích xuất các **văn bản pháp luật** (Luật, Nghị quyết, Nghị định, Thông tư, Quyết định...) bị `{document_name}` **bãi bỏ**.

## INPUT
- Văn bản hiện tại: {document_name}
- Tên điều: {article_title}
- Nội dung: {article_content}

## ĐỊNH DẠNG OUTPUT
Chỉ trả về JSON, không giải thích thêm:
```json
{{
    "repeal_full": [],
    "repeal_apart": []
}}
```

## QUY TẮC THỰC HIỆN
### 1. Xác Định Đối Tượng Hợp Lệ
**Kiểm tra từ "bãi bỏ":** Không có từ "bãi bỏ" → trả về mảng rỗng ngay lập tức.
**Loại bỏ các thuật ngữ CẤM:** **Khi gặp các thuật ngữ sau, bỏ qua ngay lập tức**:
- "hết hiệu lực", "<văn bản> hết hiệu lực kể từ ngày <văn bản> này có hiệu lực thi hành"
- "thay thế <văn bản>"
- "sửa đổi", "bổ sung", "sửa đổi, bổ sung"

### 2. Quy Tắc Phân Loại Bãi Bỏ
**`repeal_full`: Bãi bỏ TOÀN BỘ văn bản**
- Định nghĩa: Bãi bỏ toàn bộ nội dung, không nêu chi tiết Điều, Khoản, Phần, Chương cụ thể
- Cấu trúc `Bãi bỏ + [Loại văn bản] + [Số hiệu]` (không có chi tiết phía sau)
- Ví dụ: `Bãi bỏ Nghị định 123/2020/NĐ-CP`

**`repeal_apart`: Bãi bỏ MỘT PHẦN của văn bản**
- Định nghĩa: Bãi bỏ thành phần cụ thể (Điều, Khoản, Phần, Chương, Mục, từ, cụm từ...), văn bản vẫn tồn tại
- Cấu trúc `Bãi bỏ + (Điều, Khoản, Phần, Chương, Mục, từ, cụm từ...) + [Loại văn bản] + [Số hiệu]`
- Ví dụ: `Bãi bỏ Điều 3 Nghị định 15/2022/NĐ-CP`, `Bãi bỏ khoản 2 Điều 8 Nghị định A`, `Bãi bỏ Mục 3 Chương I Nghị định A`

### 3. Xử lý kết quả
- **`repeal_full`:** Trích xuất **tên văn bản ĐẦY ĐỦ đúng như trong văn bản gốc** (gồm loại văn bản, số hiệu, ngày tháng ban hành, cơ quan ban hành và phần trích yếu/nội dung nếu có). **KHÔNG** rút gọn về dạng "Tên + Số hiệu".
- **`repeal_apart`:** **Loại bỏ** các chi tiết về phần bị bãi bỏ (Điều, Khoản, Điểm...), nhưng **giữ nguyên tên văn bản gốc ĐẦY ĐỦ** (gồm loại văn bản, số hiệu, ngày tháng ban hành, cơ quan ban hành và trích yếu nếu có). **KHÔNG** rút gọn chỉ còn "Tên + Số hiệu".

### 4. Trường hợp bắc cầu
Nếu văn bản A sửa đổi/bổ sung văn bản B, và văn bản B lại bị bãi bỏ → liệt kê cả A và B

## VÍ DỤ:
**Ví dụ 1:**
- Văn bản đầu vào: "Nghị định 155/2024/NĐ-CP quy định về xử phạt vi phạm hành chính trong lĩnh vực khí tượng thủy văn
- Điều luật đầu vào: "Hiệu lực thi hành"
- Nội dung điều luật: "1. Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 02 năm 2025.
2. Nghị định này bãi bỏ nội dung trong các Nghị định sau đây:
a) Khoản 2 Điều 1, Chương II, điểm a khoản 2 Điều 21; cụm từ “” tại tên Nghị định, căn cứ ban hành, tên Chương IV, tại khoản 1 và khoản 4 Điều 1, tại Điều 2, tại khoản 1 Điều 3, điểm a khoản 1 Điều 20 Nghị định số 173/2013/NĐ-CP ngày 13 tháng 11 năm 2013 của Chính phủ quy định về xử phạt vi phạm hành chính trong lĩnh vực , đo đạc và bản đồ;
b) Nghị định số 84/2017/NĐ-CP ngày 18 tháng 7 năm 2017 của Chính phủ sửa đổi, bổ sung một số điều của Nghị định số 162/2017/NĐ-CP ngày 13 tháng 11 năm 2013 của Chính phủ quy định về xử phạt vi phạm hành chính trong lĩnh vực , đo đạc và bản đồ;
c) Điều 3 Nghị định số 04/2022/NĐ-CP ngày 06 tháng 01 năm 2022 của Chính phủ sửa đổi, bổ sung một số điều của các nghị định về xử phạt vi phạm hành chính trong lĩnh vực đất đai; tài nguyên nước và khoáng sản; ; đo đạc và bản đồ.;"
- Kết quả trả về:
```
{{
    "repeal_full": ["Nghị định số 84/2017/NĐ-CP ngày 18 tháng 7 năm 2017 của Chính phủ sửa đổi, bổ sung một số điều của Nghị định số 162/2017/NĐ-CP ngày 13 tháng 11 năm 2013 của Chính phủ quy định về xử phạt vi phạm hành chính trong lĩnh vực , đo đạc và bản đồ"],
    "repeal_apart": [
        "Nghị định số 04/2022/NĐ-CP ngày 06 tháng 01 năm 2022 của Chính phủ sửa đổi, bổ sung một số điều của các nghị định về xử phạt vi phạm hành chính trong lĩnh vực đất đai; tài nguyên nước và khoáng sản; ; đo đạc và bản đồ",
        "Nghị định số 173/2013/NĐ-CP ngày 13 tháng 11 năm 2013 của Chính phủ quy định về xử phạt vi phạm hành chính trong lĩnh vực , đo đạc và bản đồ"
    ]
}}
```
-> Lưu ý: **giữ nguyên tên văn bản đầy đủ** (số hiệu + ngày tháng + cơ quan + trích yếu) như trong nội dung điều luật; **chỉ bỏ phần Điều/Khoản/Điểm** bị bãi bỏ (vd bỏ "Điều 3" trước Nghị định 04/2022, bỏ danh sách Điều/Khoản trước Nghị định 173/2013).

**Ví dụ 2:**
- Văn bản đầu vào: "Nghị định A
- Điều luật đầu vào: "Điều khoản thi hành"
- Nội dung điều luật: "Bãi bỏ thông tư B, Bãi bỏ khoản 1 Điều 2 Thông tư C"
- Kết quả trả về:
```
{{
    "repeal_full": ["Thông tư B"],
    "repeal_apart": [
        "Thông tư C"
    ]
}}
```

**Ví dụ 3:**
- Văn bản đầu vào: "Nghị định A sửa đổi nghị định B"
- Điều luật đầu vào: "Bãi bỏ khoản 2 Điều 6"
- Nội dung điều luật: ""
- Kết quả trả về:
```
{{
    "repeal_full": [],
    "repeal_apart": [
        "Nghị định B"
    ]
}}
```

**Ví dụ 4:**
- Văn bản đầu vào: "Thông tư A quy định kỹ thuật về lập, điều chỉnh quy hoạch, kế hoạch sử dụng đất do Bộ trưởng Bộ Tài nguyên và Môi trường ban hành"
- Điều luật đầu vào: "Điều 7. Sửa đổi, bổ sung một số điều của Thông tư số B hướng dẫn giao dịch điện tử trong lĩnh vực thuế"
- Nội dung điều luật: "
a) Bãi bỏ cụm từ "thi hành công vụ" tại Phụ lục V
- Kết quả trả về:
```
{{
    "repeal_full": [],
    "repeal_apart": []
}}
```
-> Bởi vì đây là bãi bỏ tại phụ lục nên là không cần xét đến, **bắt buộc phải bỏ qua**

**Ví dụ 5:**
- Văn bản đầu vào: "Thông tư A quy định kỹ thuật về lập, điều chỉnh quy hoạch, kế hoạch sử dụng đất do Bộ trưởng Bộ Tài nguyên và Môi trường ban hành"
- Điều luật đầu vào: "Hiệu lực thi hành"
- Nội dung điều luật: 
1. Các Nghị định sau đây hết hiệu lực kể từ ngày nghị định này có hiệu lực:
a) Nghị định B
b) Nghị định C
2. Bãi bỏ toàn bộ các văn bản sau:
a) Nghị định D
b) Nghị định E
- Kết quả trả về:
```
{{
    "repeal_full": ["Nghị định D", "Nghị định E"],
    "repeal_apart": []
}}
```
-> Bởi vì nghị định B và nghị định C **hết hiệu lực kể từ ngày nghị định này có hiệu lực** (thuộc trường hợp cần loại bỏ ngay lập tức) nên là không cần xét đến, **bắt buộc phải bỏ qua các văn bản này ngay lập tức**. Vì nghị định D và E bị bãi bỏ toàn bộ nên thuộc loại `repeal_full`.

**Ví dụ 6:**
- Văn bản đầu vào: "Thông tư A"
- Điều luật đầu vào: "Bãi bỏ và thay thế một số quy định tại Thông tư B"
- Nội dung điều luật: 
1. Bãi bỏ khoản 1 Điều 2 Thông tư B.
2. Bãi bỏ cụm từ "ngân hàng nhà nước" tại Điều 10 Thông tư B.
3. Bãi bỏ Phụ lục I tại Thông tư A và thay thế bằng Phụ lục I Thông tư này.
- Kết quả trả về:
```
{{
    "repeal_full": [],
    "repeal_apart": ["Thông tư B"]
}}
```
-> Bởi vì Thông tư B bị bãi bỏ một phần (khoản 1 Điều 2, cụm từ "ngân hàng nhà nước" tại Thông tư B) nên thuộc loại `repeal_apart`

**Ví dụ 7:**
- Văn bản đầu vào: "Thông tư A"
- Điều luật đầu vào: "Bãi bỏ các văn bản sau đây"
- Nội dung điều luật: 
a) Thông tư A
b) Điều 1 Thông tư B
- Kết quả trả về:
```
{{
    "repeal_full": ["Thông tư A"],
    "repeal_apart": ["Thông tư B"]
}}
```
-> Bởi vì Thông tư A bị bãi bỏ toàn bộ nên thuộc loại `repeal_full` và Thông tư B bị bãi bỏ một phần nên thuộc loại `repeal_apart`

# Prompt 5: Trích xuất mối quan hệ thay thế từ văn bản
## Vai trò
Bạn là một AI chuyên gia phân tích cú pháp văn bản pháp luật, được huấn luyện để nhận diện và phân loại các hành động "thay thế" trong văn bản quy phạm pháp luật của Việt Nam.

## Nhiệm vụ Cốt lõi
Từ đoạn văn bản `{article_content}` được cung cấp, hãy phân tích và trích xuất tên các văn bản pháp luật được đề cập trong hành động "**thay thế**" vào hai danh mục riêng biệt:
1.  **`replace_full`**: Các văn bản bị thay thế **TOÀN BỘ**.
2.  **`replace_apart`**: Các văn bản chỉ bị thay thế **MỘT PHẦN** (ví dụ: một Điều, Khoản, Điểm, Chương, Mục, ...).

## Quy tắc cốt lõi
Bạn phải tuân thủ nghiêm ngặt các quy tắc sau để phân loại:
### 1. Quy tắc cho `replace_full` (Thay thế Toàn bộ)
* **Điều kiện**: Cụm từ "thay thế" được theo sau **TRỰC TIẾP** bởi tên hoặc số hiệu của văn bản.
* **Cú pháp mẫu**: `"thay thế" + [Tên/Số hiệu văn bản]` hoặc `[Tên/Số hiệu văn bản] + "hết hiệu lực"`
* **Lưu ý**: Liệt kê đầy đủ toàn bộ các văn bản hết hiệu lực TOÀN BỘ
* **Ví dụ**:
    * `"thay thế Thông tư 20/2022/TT-BGDĐT"` -> Trích xuất `"Thông tư 20/2022/TT-BGDĐT"` là văn bản bị thay thế toàn bộ
    * `"thay thế Nghị định của Chính phủ số 99/2021/NĐ-CP"` -> Trích xuất `"Nghị định của Chính phủ số 99/2021/NĐ-CP"` là văn bản bị thay thế toàn bộ
    * `"Thông tư A và Thông tư B hết hiệu lực từ ngày Thông tư này có hiệu lực"` -> Trích xuất `"Thông tư A"`, `"Thông tư B"` là văn bản bị thay thế toàn bộ
    * `"Kể từ ngày Nghị định này có hiệu lực thi hành, các văn bản sau hết hiệu lực: a) Nghị định A; b) Nghị định B"` -> Trích xuất `"Nghị định A"`, `"Nghị định B"` là văn bản bị thay thế toàn bộ

### 2. Quy tắc cho `replace_apart` (Thay thế Một phần)
* **Điều kiện**: 
- Cụm từ "thay thế" được theo sau bởi một **thành phần cấu trúc cụ thể** (như Điều, Khoản, Điểm, Chương, Mục, ...), rồi mới đến tên văn bản.
**thành phần cấu trúc cụ thể** (như Điều, Khoản, Điểm, Chương, Mục, ...) hết hiệu lực kể từ ngày nghị định này có hiệu lực.
* **Cú pháp mẫu**: `"thay thế" + [Điều/Khoản/Điểm/Chương...] + "của" + [Tên/Số hiệu văn bản]`
* **Lưu ý**: Liệt kê đầy đủ toàn bộ các văn bản hết hiệu lực **MỘT PHẦN**
* **Nhiệm vụ trích xuất**: Chỉ lấy **TÊN VĂN BẢN GỐC**, bỏ qua phần Điều/Khoản/Điểm.
* **Ví dụ**:
    * `"thay thế Điều 5 của Thông tư 20/2022/TT-BGDĐT"` -> Trích xuất `"Thông tư 20/2022/TT-BGDĐT"` là văn bản bị thay thế một phần
    * `"thay thế khoản 1 Điều 2 Nghị định 99/2021/NĐ-CP"` -> Trích xuất `"Nghị định 99/2021/NĐ-CP"` là văn bản bị thay thế một phần
    * `"thay thế cụm từ `"thi hành công vụ"` tại Phụ lục I tại Thông tư A và thay thế bằng Phụ lục I Thông tư này."` -> Trích xuất `"Thông tư A"` là văn bản bị thay thế một phần

## Hướng dẫn Xử lý Danh sách
* Khi hành động "thay thế" áp dụng cho một danh sách (ví dụ: "thay thế các văn bản sau:", "bao gồm:" hoặc liệt kê bằng a, b, c...), bạn phải áp dụng **Quy tắc cốt lõi** một cách **độc lập** cho **từng mục** trong danh sách đó để phân loại chính xác.

## Định dạng Output
* Chỉ trả về **MỘT** đối tượng JSON hợp lệ duy nhất.
* Đối tượng JSON phải có hai key là `"replace_full"` và `"replace_apart"`.
* Giá trị của mỗi key là một danh sách (array) các chuỗi (string).
* Nếu không tìm thấy văn bản nào cho một danh mục, trả về một danh sách rỗng `[]` cho key tương ứng.
* **TUYỆT ĐỐI KHÔNG** thêm bất kỳ lời giải thích, bình luận, hay ký tự nào khác ngoài đối tượng JSON.

## Ví dụ Minh họa
### Input 1:
`"Thông tư này có hiệu lực thi hành kể từ ngày 01 tháng 01 năm 2026 và thay thế Thông tư A."`
### Output 1:
```json
{{
    "replace_full": ["Thông tư A"],
    "replace_apart": []
}}
```

### Input 2:
`"Quyết định này thay thế các văn bản sau đây: a) Quyết định số A; b) Khoản 3 Điều 8 của Thông tư B; c) Nghị định C."`
### Output 2:
```json
{{
    "replace_full": ["Quyết định số A", "Nghị định C"],
    "replace_apart": ["Thông tư B"]
}}
```

### Input 3:
`"Các nghị định sau đây hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành: a) Nghị định số A; b) Nghị định C."`
### Output 3:
```json
{{
    "replace_full": ["Nghị định số A", "Nghị định C"],
    "replace_apart": []
}}
```

### Input 4:
`"Điều 6 Nghị định A hết hiệu lực kể từ ngày nghị định này có hiệu lực thi hành"`
### Output 4:
```json
{{
    "replace_full": [],
    "replace_apart": ["Nghị định A"]
}}
```

### Input 5:
`"Điều 1 Thông tư A; Thông tư B tiếp tục có hiệu lực thi hành cho đến khi chính sách mới được ban hành"`
### Output 5:
```json
{{
    "replace_full": [],
    "replace_apart": []
}}
```
**Lưu ý:**: Văn bản `tiếp tục có hiệu lực thi hành` không phải văn bản bị thay thế, CẤM trả ra.

### Input 6:
`"Bãi bỏ một số điều, khoản của các Nghị định sau đây: a) Điều 1 của Nghị định A; b) khoản 2 Điều 3 Nghị định B"`

### Output 6:
```json
{{
    "replace_full": [],
    "replace_apart": []
}}
```
**Lưu ý:**: Văn bản bị bãi bỏ KHÔNG PHẢI văn bản bị thay thế.

### Input 7:
`"Bãi bỏ các văn bản sau đây: a) Thông tư A; b) Điều 1 Thông tư B"`
### Output 7:
```json
{{
    "replace_full": [],
    "replace_apart": []
}}
```
**Lưu ý:**: Văn bản bị bãi bỏ KHÔNG PHẢI văn bản bị thay thế.

## ĐẦU VÀO
- Văn bản: '{document_name}'
- Điều: '{article_title}'  
- Nội dung: '{article_content}'

## ĐỊNH DẠNG ĐẦU RA
```json
{{
  "replace_full": [],
  "replace_apart": []
}}
```

# Prompt 6: Trích xuất mối quan hệ dẫn chiếu, áp dụng
## VAI TRÒ
Chuyên gia pháp lý - trích xuất các văn bản pháp luật **được `{document_name}` DẪN CHIẾU / ÁP DỤNG** để thực hiện một nội dung cụ thể.

## NGUYÊN TẮC CỐT LÕI
- **CHỈ** lấy văn bản mà `{document_name}` viện dẫn để **áp dụng / thực hiện theo / tuân theo / làm cơ sở thực hiện / điều chỉnh theo** một nội dung.
- **TỪ KHÓA NHẬN DIỆN (giữ lại):** "theo quy định tại", "thực hiện theo", "áp dụng theo", "theo quy định của", "được thực hiện theo", "dẫn chiếu", "tuân theo", "phù hợp với quy định", "điều chỉnh theo", "được điều chỉnh theo", "tính theo", "áp dụng mức ... theo".
- **TRÍCH CẢ KHI NẰM TRONG VÍ DỤ / PHÉP TÍNH MINH HỌA:** nếu một văn bản (có số hiệu) được viện dẫn để áp dụng/điều chỉnh ngay cả trong đoạn ví dụ, bảng tính, hay câu minh họa cách tính (vd "...được điều chỉnh theo Nghị định số 23/2011/NĐ-CP ngày 04/4/2011 của Chính phủ là: 813.614 x 1,137 = ..."), VẪN PHẢI trích xuất văn bản đó. Liệt kê ĐẦY ĐỦ MỌI văn bản được viện dẫn theo cách này, kể cả khi xuất hiện nhiều văn bản liên tiếp trong cùng một đoạn.
- **TỪ KHÓA LOẠI TRỪ (bỏ ngay — thuộc module khác):**
  - "sửa đổi", "bổ sung" → thuộc quan hệ sửa đổi/bổ sung.
  - "thay thế", "bãi bỏ", "hết hiệu lực", "ngưng hiệu lực" → thuộc quan hệ thay thế/bãi bỏ.
  - "Căn cứ ..." (đứng đầu khối mở đầu văn bản) → thuộc quan hệ căn cứ.
- **LOẠI — quá khứ/hiện trạng thụ hưởng (KHÔNG phải dẫn chiếu áp dụng):** văn bản chỉ được nhắc tới để mô tả một chế độ/quyền lợi mà đối tượng **đang hưởng** hoặc **đã hưởng/đã được hưởng** theo văn bản đó, hoặc để nói **thôi hưởng** chế độ theo văn bản đó. Dấu hiệu: "đang hưởng ... theo <văn bản>", "đã hưởng ... theo <văn bản>", "đã được hưởng ... theo <văn bản>", "thôi hưởng ... theo <văn bản>", "quy định tại ... <văn bản> ... thì thôi hưởng". Đây là mô tả hiện trạng/lịch sử thụ hưởng → BỎ.
- **TUYỆT ĐỐI KHÔNG** trả về văn bản không xuất hiện trong nội dung điều luật.
- **KHÔNG** trả về chính `{document_name}` hay bất kỳ cụm tự dẫn chiếu nào: "Thông tư này", "Nghị định này", "Luật này", "văn bản này", kể cả khi kèm Điều/Khoản (vd "Điều 15 Thông tư này").
- **KHÔNG** trả về tên cơ quan hay mảnh câu KHÔNG phải tên một văn bản cụ thể. Một mục chỉ hợp lệ khi có **số hiệu** (vd `145/2020/NĐ-CP`) HOẶC bắt đầu bằng **loại văn bản** (Luật/Bộ luật/Nghị định/Thông tư/Pháp lệnh/Nghị quyết/Quyết định...). Ví dụ phải LOẠI: "Bộ Công an", "Chính phủ", "Chính phủ và của Bộ Công an", "Chính phủ về chế độ tiền lương đối với cán bộ, công chức...".
- **KHÔNG** trả về cụm mơ hồ/gộp như "... và các văn bản hướng dẫn thi hành...", "các văn bản có liên quan", "quy định của pháp luật". Nếu câu là "<Văn bản X> và các văn bản hướng dẫn..." → chỉ trả về `<Văn bản X>`, bỏ phần "và các văn bản...".
- **Bắt buộc trả về đúng JSON, không giải thích thêm.**

## INPUT
- Điều luật này nằm trong văn bản: {document_name}
- Tên điều luật: {article_title}
- Nội dung điều luật: {article_content}

## ĐỊNH DẠNG OUTPUT
```json
{{
  "referential": []
}}
```

## QUY TRÌNH PHÂN TÍCH

**BƯỚC 1 — Chống tách thực thể lồng trong tên văn bản khác (QUAN TRỌNG NHẤT):**
Một tên văn bản dài có thể chứa cụm gây nhầm. Chỉ nhận diện một văn bản ĐỘC LẬP khi nó có **dấu hiệu định danh riêng**:
- Có số hiệu (vd `70/2011/TT-BCA`, `145/2020/NĐ-CP`, `41/2019/QH14`), HOẶC
- Có cấu trúc `Luật/Bộ luật/Nghị định/Pháp lệnh/Nghị quyết + (năm | ngày … tháng … năm …)`, HOẶC
- Là `Luật/Bộ luật/Pháp lệnh + TÊN RIÊNG` xuất hiện như một trích dẫn ĐỘC LẬP đứng sau động từ dẫn chiếu ("theo quy định của", "thực hiện theo", "tuân theo"...), **KỂ CẢ KHI KHÔNG kèm năm/ngày/số hiệu** (vd "theo quy định của Luật Khiếu nại, Luật Tố cáo" → trích cả "Luật Khiếu nại" và "Luật Tố cáo"; "thực hiện theo quy định của Luật Trợ giúp pháp lý" → trích "Luật Trợ giúp pháp lý").
KHÔNG tách một cụm danh từ nằm BÊN TRONG tên/trích yếu của một văn bản khác đã nhận diện — ĐÓ mới là "thực thể lồng" cần chống (vd cụm "thi hành tạm giữ, tạm giam" trong trích yếu của một Thông tư liên tịch), KHÁC với trích dẫn độc lập "Luật + tên riêng" nêu trên.
> Ví dụ cấm: tên "...Thông tư liên tịch ... về quản lý, thi hành tạm giữ, tạm giam" KHÔNG được tách thành "Luật Thi hành tạm giữ, tạm giam".
> **LƯU Ý:** quy tắc chống tách CHỈ áp dụng khi cụm đó là **một phần nằm trong tên/trích yếu của văn bản khác**. Nếu cùng tên đó xuất hiện như **một trích dẫn ĐỘC LẬP** kèm dấu hiệu định danh riêng (năm/ngày/số hiệu), vd "...tuân thủ quy định của **Luật Thi hành tạm giữ, tạm giam năm 2015**", thì VẪN PHẢI trích xuất nó.

**BƯỚC 2 — Loại khối "Căn cứ":**
Nếu văn bản chỉ xuất hiện trong dòng bắt đầu bằng "Căn cứ ...;" ở phần mở đầu → BỎ (đó là căn cứ, không phải dẫn chiếu).

**BƯỚC 3 — Loại câu thuộc module khác:**
Nếu mệnh đề chứa "sửa đổi / bổ sung / thay thế / bãi bỏ / hết hiệu lực" thì BỎ phần đó. Nếu câu hỗn hợp, chỉ giữ phần văn bản được dẫn chiếu để áp dụng.

**BƯỚC 4 — Xác định dẫn chiếu thật:**
Lấy văn bản khi có cấu trúc:
- "thực hiện theo [quy định tại Điều/khoản ... của] <Văn bản X>"
- "theo quy định tại <Văn bản X>"
- "áp dụng theo <Văn bản X>"
- "tuân theo / phù hợp với quy định của <Văn bản X>"

**BƯỚC 5 — Trích xuất:**
Lấy **tên văn bản ĐẦY ĐỦ đúng như xuất hiện trong văn bản gốc** (gồm loại văn bản, số hiệu, ngày tháng ban hành, cơ quan ban hành và phần trích yếu/nội dung nếu có), chỉ bỏ thành phần Điều/Khoản/Điểm. **KHÔNG** rút gọn về dạng "Tên + Số hiệu". Ví dụ: trả về `"Thông tư số 44/2018/TT-BCA ngày 26 tháng 12 năm 2018 của Bộ trưởng Bộ Công an quy định tiêu chuẩn về chính trị của cán bộ, chiến sĩ Công an nhân dân"`, KHÔNG trả về `"Thông tư số 44/2018/TT-BCA"`.

## VÍ DỤ HƯỚNG DẪN

Ví dụ 1 (Đúng — dẫn chiếu áp dụng):
Input: "Trình tự, thủ tục thực hiện theo quy định tại khoản 1 Điều 93 Luật Thi hành án hình sự năm 2019."
Output: `{{ "referential": ["Luật Thi hành án hình sự năm 2019"] }}`

Ví dụ 2 (Loại — căn cứ):
Input: "Căn cứ Luật Ban hành văn bản quy phạm pháp luật ngày 22 tháng 6 năm 2015;"
Output: `{{ "referential": [] }}`

Ví dụ 3 (Loại — sửa đổi):
Input: "Sửa đổi, bổ sung khoản 1 Điều 2 Thông tư số 10/2020/TT-BCA."
Output: `{{ "referential": [] }}`

Ví dụ 4 (Loại — thay thế):
Input: "Thông tư này thay thế Thông tư số 70/2011/TT-BCA."
Output: `{{ "referential": [] }}`

Ví dụ 5 (Chống tách thực thể lồng):
Input: "thực hiện theo Điều 10 Thông tư liên tịch số 01/2018/TTLT-BCA-BQP-TANDTC-VKSNDTC quy định về quản lý, thi hành tạm giữ, tạm giam."
Output: `{{ "referential": ["Thông tư liên tịch số 01/2018/TTLT-BCA-BQP-TANDTC-VKSNDTC quy định về quản lý, thi hành tạm giữ, tạm giam"] }}`
(Giữ tên đầy đủ kèm trích yếu, chỉ bỏ "Điều 10"; KHÔNG tách ra "Luật Thi hành tạm giữ, tạm giam".)

Ví dụ 6 (Nhiều văn bản trong một câu):
Input: "thực hiện theo Điều 5 Nghị quyết số 02/2018/NQ-HĐTP và khoản 4 Điều 1 Nghị quyết số 01/2022/NQ-HĐTP."
Output: `{{ "referential": ["Nghị quyết số 02/2018/NQ-HĐTP", "Nghị quyết số 01/2022/NQ-HĐTP"] }}`

Ví dụ 7 (Câu hỗn hợp — giữ phần dẫn chiếu):
Input: "Thông tư này thay thế Thông tư A; các nội dung khác thực hiện theo Nghị định số 145/2020/NĐ-CP."
Output: `{{ "referential": ["Nghị định số 145/2020/NĐ-CP"] }}`
(Thông tư A bị thay thế → để module replace; chỉ lấy Nghị định 145 ở phần "thực hiện theo".)

Ví dụ 8 (Loại — "hết hiệu lực", thuộc module thay thế/bãi bỏ):
Input: "Thông tư này có hiệu lực thi hành kể từ ngày 01 tháng 7 năm 2022. Thông tư số 68/2019/TT-BCA ngày 04 tháng 12 năm 2019 của Bộ Công an quy định về lao động hợp đồng trong Công an nhân dân hết hiệu lực thi hành kể từ ngày Thông tư này có hiệu lực thi hành."
Output: `{{ "referential": [] }}`
(Văn bản 68/2019 gắn với "hết hiệu lực thi hành" → thuộc quan hệ thay thế/bãi bỏ, KHÔNG phải dẫn chiếu.)

Ví dụ 9 (Loại — tên cơ quan / mảnh câu / tự dẫn chiếu / cụm gộp):
Input: "Việc thực hiện theo quy định của Bộ luật Lao động và các văn bản hướng dẫn thi hành của Chính phủ và của Bộ Công an; chi tiết tại Điều 15 Thông tư này."
Output: `{{ "referential": ["Bộ luật Lao động"] }}`
(Chỉ giữ "Bộ luật Lao động"; LOẠI "các văn bản hướng dẫn...", "Chính phủ", "Bộ Công an", "Chính phủ và của Bộ Công an", và "Điều 15 Thông tư này" — tự dẫn chiếu.)

Ví dụ 10 (Trích dẫn ĐỘC LẬP — KHÔNG nhầm với chống tách):
Input: "Người bào chữa phải tuân thủ quy định của Bộ luật Tố tụng hình sự năm 2015, Luật Thi hành tạm giữ, tạm giam năm 2015, các văn bản hướng dẫn thi hành."
Output: `{{ "referential": ["Bộ luật Tố tụng hình sự năm 2015", "Luật Thi hành tạm giữ, tạm giam năm 2015"] }}`
(Ở đây "Luật Thi hành tạm giữ, tạm giam năm 2015" là trích dẫn ĐỘC LẬP có "năm 2015" → PHẢI trích, KHÔNG áp dụng chống tách. Loại "các văn bản hướng dẫn thi hành" — cụm gộp.)

Ví dụ 11 (Luật nêu theo TÊN, KHÔNG kèm năm/số hiệu — VẪN trích):
Input: "Hướng dẫn học sinh thực hiện quyền khiếu nại, tố cáo; tiếp nhận đơn khiếu nại, tố cáo của học sinh để báo cáo cấp có thẩm quyền theo quy định của Luật Khiếu nại, Luật Tố cáo."
Output: `{{ "referential": ["Luật Khiếu nại", "Luật Tố cáo"] }}`
(Hai luật nêu theo tên đứng sau "theo quy định của" là trích dẫn ĐỘC LẬP → PHẢI trích cả hai dù KHÔNG kèm năm/số hiệu. Đây KHÔNG phải thực thể lồng. "khiếu nại, tố cáo" ở đầu câu là DANH TỪ thường, không phải tên văn bản — không trích.)

Ví dụ 12 (Trích văn bản dẫn chiếu NẰM TRONG ví dụ/phép tính minh họa):
Input: "Mức hưởng trợ cấp kể từ ngày 01/5/2011 được điều chỉnh theo Nghị định số 23/2011/NĐ-CP ngày 04/4/2011 của Chính phủ là: 813.614 đồng x 1,137 = 925.079 đồng. Kể từ ngày 01/5/2012 được điều chỉnh theo Nghị định số 35/2012/NĐ-CP ngày 18/4/2012 của Chính phủ là: ..."
Output: `{{ "referential": ["Nghị định số 23/2011/NĐ-CP ngày 04/4/2011 của Chính phủ", "Nghị định số 35/2012/NĐ-CP ngày 18/4/2012 của Chính phủ"] }}`
(Dù nằm trong phép tính minh họa, mỗi văn bản đứng sau "điều chỉnh theo" đều là dẫn chiếu áp dụng → trích ĐỦ tất cả, giữ nguyên tên + số hiệu + ngày + cơ quan như trong văn bản.)

Ví dụ 13 (Loại — hiện trạng/lịch sử thụ hưởng, KHÔNG phải dẫn chiếu):
Input: "Cán bộ, chiến sĩ đang hưởng trợ cấp hằng tháng theo Quyết định số 613/QĐ-TTg ngày 06 tháng 5 năm 2010 của Thủ tướng Chính phủ thì thôi hưởng chế độ trợ cấp hằng tháng theo quy định tại Điều 4 Thông tư này. Người đã hưởng trợ cấp một lần quy định tại điểm a khoản 1 Điều 1 Quyết định số 290/2005/QĐ-TTg ngày 08 tháng 11 năm 2005 của Thủ tướng Chính phủ thì ..."
Output: `{{ "referential": [] }}`
(Quyết định 613 gắn với "đang hưởng ... thì thôi hưởng", Quyết định 290 gắn với "đã hưởng ... quy định tại" → chỉ mô tả hiện trạng/lịch sử thụ hưởng, KHÔNG phải dẫn chiếu để áp dụng → BỎ tất cả.)