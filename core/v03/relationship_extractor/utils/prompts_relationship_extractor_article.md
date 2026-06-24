
# Prompt 1: Trích xuất mối quan hệ Dẫn chiếu từ điều luật

**Nhiệm vụ:** Trích xuất các mối quan hệ `Dẫn chiếu` từ nội dung điều luật.

**Dẫn chiếu:**
- Định nghĩa: Là mối quan hệ pháp lý khi một điều luật tham chiếu đến **Điều/Khoản/Điểm** trong văn bản khác.
- **Dấu hiệu nhận biết:** Bắt buộc nằm sau cụm từ như `theo quy định tại`, `quy định tại`, hoặc `được sửa đổi, bổ sung theo` kèm với Điều/Khoản/Điểm được tham chiếu. Trường hợp dẫn chiếu đến điều luật hiện tại thì `name` là `{doc_title}` và `article` là số của điều `{content}`.
- **Ví dụ đúng:** 
+ 'theo quy định tại điểm d khoản 2 Điều 77 của Luật Đấu giá tài sản được sửa đổi, bổ sung theo khoản 44 Điều 1 Luật sửa đổi, bổ sung một số điều của Luật Đấu giá tài sản' -> [{{ "type_llm": "Dẫn chiếu", "article": "Điều 77", "clause": "Khoản 2", "point": "Điểm d", "name": "Luật Đấu giá tài sản", "evidence": "theo quy định tại điểm d khoản 2 Điều 77 của Luật Đấu giá tài sản được sửa đổi, bổ sung theo khoản 44 Điều 1 Luật sửa đổi, bổ sung một số điều của Luật Đấu giá tài sản" }}, {{ "type_llm": "Dẫn chiếu", "article": "Điều 1", "clause": "Khoản 44", "point": "", "name": "Luật sửa đổi, bổ sung một số điều của Luật Đấu giá tài sản", "evidence": "theo quy định tại điểm d khoản 2 Điều 77 của Luật Đấu giá tài sản được sửa đổi, bổ sung theo khoản 44 Điều 1 Luật sửa đổi, bổ sung một số điều của Luật Đấu giá tài sản" }}]
+ 'Điều 2. Đối tượng quy định tại khoản 1, khoản 2, khoản 3 Điều này đủ điều kiện về tuổi tái cử' -> {{ "type_llm": "Dẫn chiếu", "article": "Điều 2", "clause": "", "point": "", "name": "", "evidence": "Điều 2. Đối tượng quy định tại khoản 1, khoản 2, khoản 3 Điều này đủ điều kiện về tuổi tái cử" }}

- **Ví dụ sai:** 
+ 'Thẩm quyền đặt tên, đổi tên đường đô thị thực hiện theo Quy chế của Chính phủ về đặt tên, đối tên đường, phố và công trình công cộng.' -> {{ "type_llm": "Không có mối quan hệ", "article": "", "clause": "", "point": "", "name": "" }}

**Input:**
- Số điều hiện tại: `{number_of_article}`
- Nội dung cần xét: `{content}`
- Tên văn bản hiện tại: `{doc_title}`

**Định dạng Output:** Dạng JSON
- `type_llm` là loại mối quan hệ pháp lý, có thể là `Dẫn chiếu` hoặc `Không có mối quan hệ`.
- `detail_name` là tên các loại văn bản pháp luật đi kèm với số hiệu (ví dụ: Thông tư 36/2012/TT-NH hoặc Thông tư 19/2024/TT-BTP) hoặc chỉ đi kèm với năm (ví dụ: Luật dân sự 2015). Trường hợp đặc biệt, thay **Văn bản này** bằng **{doc_title}**. **Tuyệt đối không** sử dụng các cụm từ chung chung như "pháp luật về lao động", "luật hiện hành" làm giá trị cho `name`.
- `detail_article` là giá trị phải có, định dạng: **Điều** và **số điều** (Điều 3). Nếu `nội dung cần xét` có `Điều này` thì `detail_article` là `Điều {number_of_article}`. **Không có** thì để trống. **Tuyệt đối không** lấy giá trị **Chương/Mục/Phần/Biểu mẫu/Phụ lục**.
- `detail_clause` là định dạng: **Khoản** và **số khoản**, ví dụ: Khoản 1. **Không có** thì để trống.
- `detail_point` là định dạng: **Điểm** và **số điểm**, ví dụ: Điểm a. **Không có** thì để trống.
- `detail_evidence` là trích dẫn chứa kết quả của mối quan hệ pháp lý. Đảm bảo trích dẫn chứa đầy đủ thông tin về `type_llm`, `article`, `clause`, `point`, `name`.

**Output:**
```json
[
    {{
        "type_llm": "Dẫn chiếu/Không có quan hệ",
        "detail_article": "<Điều luật bị dẫn chiếu (Phải có)/Trường hợp không có mối quan hệ thì để rỗng>",
        "detail_clause": "<Khoản bị dẫn chiếu (có thể có)/Trường hợp không có mối quan hệ thì để rỗng>",
        "detail_point": "<Điểm bị dẫn chiếu (có thể có)/Trường hợp không có mối quan hệ thì để rỗng>",
        "detail_name": "<Tên văn bản bị dẫn chiếu (có thể có)/Trường hợp không có mối quan hệ thì để rỗng>",
        "detail_evidence": "<Trích dẫn chứa kết quả của mối quan hệ pháp lý>"
    }}
]
```
    
**Lưu ý:**
- Chỉ trả JSON, không giải thích và suy luận dài dòng. Đảm bảo trích xuất đầy đủ các mối quan hệ.
- `detail_article`, `detail_clause`, `detail_point`, `detail_name` **tuyệt đối phải** có trong `detail_evidence`. Nếu không có thì để **Không có mối quan hệ** .
- **Tuyệt đối không** sử dụng thông tin `Số điều hiện tại` cho `detail_article` khi trong `detail_evidence` không có từ **Điều này**.
- Nếu không rõ số điều được dẫn chiếu thì để trống.
- Tuyệt đối chỉ sử dụng nội dung có trong điều luật, không bịa đặt thông tin không có bằng chứng rõ ràng.

---
## Bỏ qua dẫn chiếu nội bộ (BẮT BUỘC)
- **Tuyệt đối không** trích xuất mối quan hệ trỏ đến **chính văn bản hiện tại** (`{doc_title}`) hay đến **Điều/Khoản/Điểm trong cùng văn bản** — bao gồm mọi trường hợp `Điều này`, `khoản này`, `điểm này`, `văn bản này`, hoặc dẫn chiếu một Điều mà **không nêu tên một văn bản KHÁC**.
- Quy tắc này **được ưu tiên** so với mọi hướng dẫn về `Điều này` ở trên: thay vì gán `{doc_title}` cho `detail_name`, hãy bỏ qua hẳn.
- Chỉ giữ lại mối quan hệ khi `detail_name` là **một văn bản khác được nêu tên rõ ràng**. Nếu không có, trả về `Không có mối quan hệ`.
- `detail_name` **bắt buộc** là tên một **văn bản quy phạm pháp luật** (Luật, Bộ luật, Nghị định, Thông tư, Pháp lệnh, Nghị quyết, Quyết định, …), kèm số hiệu hoặc năm. **Tuyệt đối không** dùng `Phụ lục`, `Phần`, `Chương`, `Mục`, `Tiểu mục`, `Biểu mẫu`, `Danh mục`, `Mẫu`, `Điều/Khoản/Điểm` làm `detail_name`. Nếu đối tượng bị tác động chỉ là các thành phần này mà không nêu tên một văn bản khác, trả về `Không có mối quan hệ`.
- `detail_name` phải ghi **nguyên văn đầy đủ** tên văn bản như xuất hiện trong ngữ cảnh — bao gồm loại văn bản, số hiệu, ngày ban hành và trích yếu nội dung nếu có (ví dụ: `Thông tư số 16/2013/TT-BGTVT ngày 30 tháng 7 năm 2013 của Bộ trưởng Bộ Giao thông vận tải quy định về quản lý tuyến vận tải thủy từ bờ ra đảo trong vùng biển Việt Nam`). Không rút ngắn xuống chỉ còn số hiệu.

# Prompt 2: Trích xuất mối quan hệ Sửa đổi, bổ sung từ điều luật

**Nhiệm vụ:** Trích xuất các mối quan hệ `Sửa đổi`, `Bổ sung`, `Sửa đổi, bổ sung`, `Thay thế`, `Bãi bỏ một phần` từ nội dung điều luật. Dựa trên tài liệu quan hệ pháp lý, tập trung vào các trường hợp sửa đổi/bổ sung từ điều luật hiện tại đến Điều luật hoặc Phần/Chương/Mục/Tiểu mục trong văn bản khác. Không trích xuất các quan hệ khác như bãi bỏ, dẫn chiếu.

## Sửa đổi
- **Định nghĩa:** Là mối quan hệ pháp lý khi một điều luật sửa đổi **Điều luật** hoặc **Phần/Chương/Mục/Tiểu mục** trong văn bản khác.
- **Dấu hiệu nhận biết:** 'sửa đổi Điều <số điều>', 'sửa đổi khoản <số khoản>', 'sửa đổi điểm <số điểm>', 'sửa đổi Phần <số phần>', 'sửa đổi Chương <số chương>', 'sửa đổi Mục <số mục>', 'sửa đổi Tiểu mục <số tiểu mục>', 'thay cụm từ <cụm từ>', 'thay thế khoản <số khoản>', 'thay thế điểm <số điểm>'.

## Bổ sung
- **Định nghĩa:** Là mối quan hệ pháp lý khi một điều luật bổ sung **Điều luật** hoặc **Phần/Chương/Mục/Tiểu mục** trong văn bản khác.
- **Dấu hiệu nhận biết:** 'bổ sung Điều <số điều>', 'bổ sung khoản <số khoản>', 'bổ sung điểm <số điểm>', 'bổ sung Phần <số phần>', 'bổ sung Chương <số chương>', 'bổ sung Mục <số mục>', 'bổ sung Tiểu mục <số tiểu mục>'.

## Sửa đổi, bổ sung
- **Định nghĩa:** Là mối quan hệ pháp lý khi một điều luật sửa đổi và bổ sung **Điều luật** hoặc **Phần/Chương/Mục/Tiểu mục** trong văn bản khác.
- **Dấu hiệu nhận biết:** 'sửa đổi, bổ sung Điều <số điều>', 'sửa đổi, bổ sung khoản <số khoản>', 'sửa đổi, bổ sung điểm <số điểm>', 'sửa đổi, bổ sung Phần <số phần>', 'sửa đổi, bổ sung Chương <số chương>', 'sửa đổi, bổ sung Mục <số mục>', 'sửa đổi, bổ sung Tiểu mục <số tiểu mục>'.

## Thay thế
- **Định nghĩa:** Là mối quan hệ pháp lý khi một điều luật thay thế **Điều luật** trong văn bản khác. **Tuyệt đối không** xác định `type_llm` là `Thay thế` khi thay thế Khoản hoặc Điểm của Điều luật.
- **Dấu hiệu nhận biết:** 'thay thế Điều <số điều>'.

## Bãi bỏ một phần
- **Định nghĩa:** Là mối quan hệ pháp lý khi một điều luật bãi bỏ một phần của **Điều luật** trong văn bản khác.
- **Dấu hiệu nhận biết:** 'bãi bỏ cụm từ <cụm từ>', 'bãi bỏ từ <từ>', 'bãi bỏ khoản <số khoản>', 'bãi bỏ điểm <số điểm>'.

### Ví dụ đúng
+ 'sửa đổi Điều 1 Nghị định 122/2012/NĐ-CP' → `{{ "type_llm": "Sửa đổi", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 1", "detail_clause": "", "detail_point": "", "detail_name": "Nghị định 122/2012/NĐ-CP", "detail_evidence": "sửa đổi Điều 1 Nghị định 122/2012/NĐ-CP" }}`.
+ 'Bổ sung khoản 4 vào Điều 3 Thông tư số 32/2018/TT-BGDĐT' → `{{ "type_llm": "Bổ sung", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 3", "detail_clause": "Khoản 4", "detail_point": "", "detail_name": "Thông tư số 32/2018/TT-BGDĐT", "detail_evidence": "Bổ sung khoản 4 vào Điều 3 Thông tư số 32/2018/TT-BGDĐT" }}`.
+ 'Bổ sung khoản 2a sau khoản 2 Điều 10' → `{{ "type_llm": "Bổ sung", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 10", "detail_clause": "Khoản 2a", "detail_point": "", "detail_name": "", "detail_evidence": "Bổ sung khoản 2a sau khoản 2 Điều 10" }}`.
+ 'Sửa đổi, bổ sung điểm g khoản 1 Điều 9 Thông tư số 111/2013/TT-BTC' → `{{ "type_llm": "Sửa đổi, bổ sung", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 9", "detail_clause": "Khoản 1", "detail_point": "Điểm g", "detail_name": "Thông tư số 111/2013/TT-BTC", "detail_evidence": "Sửa đổi, bổ sung điểm g khoản 1 Điều 9 Thông tư số 111/2013/TT-BTC" }}`.
+ 'sửa đổi Chương II Phần A Luật Dân sự 2015' → `{{ "type_llm": "Sửa đổi", "detail_part": "Phần A", "detail_chapter": "Chương II", "detail_section": "", "detail_subsection": "", "detail_article": "", "detail_clause": "", "detail_point": "", "detail_name": "Luật Dân sự 2015", "detail_evidence": "sửa đổi Chương II Phần A Luật Dân sự 2015" }}`.
+ 'bổ sung Mục 3 vào Phần B Nghị định 45/2020/NĐ-CP' → `{{ "type_llm": "Bổ sung", "detail_part": "Phần B", "detail_chapter": "", "detail_section": "Mục 3", "detail_subsection": "", "detail_article": "", "detail_clause": "", "detail_point": "", "detail_name": "Nghị định 45/2020/NĐ-CP", "detail_evidence": "Bổ sung Mục 3 vào Phần B Nghị định 45/2020/NĐ-CP" }}`.
+ 'thay thế khoản 1 Điều 5 Nghị định 45/2020/NĐ-CP' → `{{ "type_llm": "Sửa đổi", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 5", "detail_clause": "Khoản 1", "detail_point": "", "detail_name": "Nghị định 45/2020/NĐ-CP", "detail_evidence": "Thay thế khoản 1 Điều 5 Nghị định 45/2020/NĐ-CP" }}`.
+ 'thay cụm từ "thanh tra" thành "thẩm quyền" trong Điều 5 Nghị định 45/2020/NĐ-CP' → `{{ "type_llm": "Sửa đổi", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 5", "detail_clause": "", "detail_point": "", "detail_name": "Nghị định 45/2020/NĐ-CP", "detail_evidence": "Thay cụm từ \"thanh tra\" thành \"thẩm quyền\" trong Điều 5 Nghị định 45/2020/NĐ-CP" }}`.
+ 'thay thế Điều 5 Nghị định 45/2020/NĐ-CP' → `{{ "type_llm": "Thay thế", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 5", "detail_clause": "", "detail_point": "", "detail_name": "Nghị định 45/2020/NĐ-CP", "detail_evidence": "Thay thế Điều 5 Nghị định 45/2020/NĐ-CP" }}`.
+ 'Thay thế Phụ lục I Thông tư số 13/2021/TT-BGDĐT' → `{{ "type_llm": "Không có mối quan hệ", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "", "detail_clause": "", "detail_point": "", "detail_name": "", "detail_evidence": "Thay thế Phụ lục I Thông tư số 13/2021/TT-BGDĐT" }}`.
+ 'bãi bỏ cụm từ "vi phạm" tại khoản 1 Điều 5' -> `{{ "type_llm": "Bãi bỏ một phần", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 5", "detail_clause": "Khoản 1", "detail_point": "", "detail_name": "", "detail_evidence": "bãi bỏ cụm từ \"vi phạm\" tại khoản 1 Điều 5" }}`.

### Ví dụ sai 
+ 'thay thế khoản 1 Điều 5 Nghị định 45/2020/NĐ-CP' → `{{ "type_llm": "Thay thế", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 5", "detail_clause": "Khoản 1", "detail_point": "", "detail_name": "Nghị định 45/2020/NĐ-CP", "detail_evidence": "Thay thế khoản 1 Điều 5 Nghị định 45/2020/NĐ-CP" }}`. 

## Input
- Số điều hiện tại: `{number_of_article}`
- Nội dung cần xét: `{content}`
- Tên văn bản hiện tại: `{doc_title}`

## Định dạng Output
Dạng JSON
- `type_llm` là tên các loại mối quan hệ pháp lý bao gồm: `Sửa đổi`, `Bổ sung`, `Sửa đổi, bổ sung`, `Thay thế`, `Bãi bỏ một phần`. Trường hợp đặc biệt `Không có mối quan hệ`.
- `detail_part` là Phần bị ảnh hưởng (ví dụ: Phần A). **Không có** thì để trống.
- `detail_chapter` là Chương bị ảnh hưởng (ví dụ: Chương II). **Không có** thì để trống.
- `detail_section` là Mục bị ảnh hưởng (ví dụ: Mục 3). **Không có** thì để trống.
- `detail_subsection` là Tiểu mục bị ảnh hưởng (ví dụ: Tiểu mục 2.1). **Không có** thì để trống.
- `detail_article` là Điều bị ảnh hưởng (BẮT BUỘC có tiền tố 'Điều' nếu có, ví dụ: Điều 3). **Không có** thì để trống. **Chỉ** lấy giá trị **Điều**; không lấy Biểu mẫu/Phụ lục.
- `detail_clause` là Khoản bị ảnh hưởng (BẮT BUỘC có tiền tố 'Khoản' nếu có, ví dụ: Khoản 1; chỉ áp dụng nếu có detail_article). **Không có** thì để trống.
- `detail_point` là Điểm bị ảnh hưởng (BẮT BUỘC có tiền tố 'Điểm' nếu có, ví dụ: Điểm a; chỉ áp dụng nếu có detail_article và detail_clause). **Không có** thì để trống.
- `detail_name` là tên các loại văn bản pháp luật đi kèm với số hiệu (ví dụ: Thông tư 36/2012/TT-NH hoặc Thông tư 19/2024/TT-BTP), chỉ đi kèm với năm (ví dụ: Luật dân sự 2015) hoặc chỉ có tên văn bản (ví dụ: Luật lao động). **Tuyệt đối không** sử dụng các cụm từ chung chung như "pháp luật về lao động", "luật hiện hành" làm giá trị cho `detail_name`. Lấy từ Tiêu đề Điều.
- `detail_evidence` là trích dẫn chứa kết quả của mối quan hệ pháp lý (phải là đoạn trích ngắn gọn). Đảm bảo trích dẫn chứa đầy đủ thông tin về `type_llm`, các trường detail liên quan, và `detail_name`.

### Output
```json
[
  {{
    "type_llm": "Sửa đổi/Bổ sung/Sửa đổi, bổ sung/Thay thế/Bãi bỏ một phần/Không có mối quan hệ",
    "detail_part": "<Phần bị ảnh hưởng - để trống nếu không có>",
    "detail_chapter": "<Chương bị ảnh hưởng - để trống nếu không có>",
    "detail_section": "<Mục bị ảnh hưởng - để trống nếu không có>",
    "detail_subsection": "<Tiểu mục bị ảnh hưởng - để trống nếu không có>",
    "detail_article": "<Điều bị ảnh hưởng (BẮT BUỘC có tiền tố 'Điều' nếu có) - Ví dụ: Điều 7>",
    "detail_clause": "<Khoản bị ảnh hưởng (BẮT BUỘC có tiền tố 'Khoản' nếu có) - Ví dụ: Khoản 4>",
    "detail_point": "<Điểm bị ảnh hưởng (BẮT BUỘC có tiền tố 'Điểm' nếu có) - để trống nếu không có>",
    "detail_name": "<Tên văn bản bị ảnh hưởng (Lấy từ Tiêu đề Điều)>",
    "detail_evidence": "<Trích dẫn chứa kết quả (Phải là đoạn trích ngắn gọn)>"
  }}
]
```

## Lưu ý
- Chỉ trả JSON, không giải thích và suy luận dài dòng. Đảm bảo trích xuất đầy đủ các mối quan hệ từ nội dung điều luật.
- Các trường detail **tuyệt đối phải** có trong `detail_evidence`. Nếu không có thì để **Không có mối quan hệ**.
- Nếu `type_llm` khác `Không có mối quan hệ` thì **bắt buộc** phải xác định một trong những giá trị `detail_article`, `detail_clause`, `detail_point` hoắc các thông tin khác.
- **Tuyệt đối không** sử dụng thông tin `Số điều hiện tại` cho `detail_article` khi trong `detail_evidence` không có từ **Điều này**.
- **Tuyệt đối không** sử dụng thông tin `Tên văn bản hiện tại` cho `detail_name` trong bất kỳ trường hợp nào.
- Nếu không rõ số hoặc cấp độ bị sửa đổi/bổ sung thì để trống.
- Tuyệt đối chỉ sử dụng nội dung có trong điều luật, không bịa đặt thông tin không có bằng chứng rõ ràng. Không trích xuất quan hệ nếu chỉ đề cập chung chung mà không chỉ rõ cấp độ (Phần/Chương/Mục/Tiểu mục/Điều).

---
## Bỏ qua dẫn chiếu nội bộ (BẮT BUỘC)
- **Tuyệt đối không** trích xuất mối quan hệ trỏ đến **chính văn bản hiện tại** (`{doc_title}`) hay đến **Điều/Khoản/Điểm trong cùng văn bản** — bao gồm mọi trường hợp `Điều này`, `khoản này`, `điểm này`, `văn bản này`, hoặc dẫn chiếu một Điều mà **không nêu tên một văn bản KHÁC**.
- Quy tắc này **được ưu tiên** so với mọi hướng dẫn về `Điều này` ở trên: thay vì gán `{doc_title}` cho `detail_name`, hãy bỏ qua hẳn.
- Chỉ giữ lại mối quan hệ khi `detail_name` là **một văn bản khác được nêu tên rõ ràng**. Nếu không có, trả về `Không có mối quan hệ`.
- `detail_name` **bắt buộc** là tên một **văn bản quy phạm pháp luật** (Luật, Bộ luật, Nghị định, Thông tư, Pháp lệnh, Nghị quyết, Quyết định, …), kèm số hiệu hoặc năm. **Tuyệt đối không** dùng `Phụ lục`, `Phần`, `Chương`, `Mục`, `Tiểu mục`, `Biểu mẫu`, `Danh mục`, `Mẫu`, `Điều/Khoản/Điểm` làm `detail_name`. Nếu đối tượng bị tác động chỉ là các thành phần này mà không nêu tên một văn bản khác, trả về `Không có mối quan hệ`.
- `detail_name` phải ghi **nguyên văn đầy đủ** tên văn bản như xuất hiện trong ngữ cảnh — bao gồm loại văn bản, số hiệu, ngày ban hành và trích yếu nội dung nếu có (ví dụ: `Thông tư số 16/2013/TT-BGTVT ngày 30 tháng 7 năm 2013 của Bộ trưởng Bộ Giao thông vận tải quy định về quản lý tuyến vận tải thủy từ bờ ra đảo trong vùng biển Việt Nam`). Không rút ngắn xuống chỉ còn số hiệu.

# Prompt 3: Trích xuất mối quan hệ Hướng dẫn chi tiết từ điều luật

**Nhiệm vụ:** Trích xuất các mối quan hệ `Hướng dẫn chi tiết` từ nội dung điều luật.

**Hướng dẫn chi tiết:**
- Định nghĩa: là mối quan hệ pháp lý khi nội dung của một điều luật được quy định chi tiết trong nội dung văn bản khác.
- Dấu hiệu nhận biết: 'quy định chi tiết tại'.
- **Ví dụ đúng:** 'quy định chi tiết tại Điều 1 Nghị định 122/2012/NĐ-CP' -> {{ "type_llm": "Hướng dẫn chi tiết", "article": "Điều 1", "clause": "", "point": "", "name": "Nghị định 122/2012/NĐ-CP", "evidence": "quy định chi tiết tại Điều 1 Nghị định 122/2012/NĐ-CP" }}
- **Ví dụ sai:** 'quy định chi tiết về điều kiện đầu tư kinh doanh' -> {{ "type_llm": "Không có mối quan hệ", "article": "", "clause": "", "point": "", "name": "" }}

**Input:**
- Số điều hiện tại: `{number_of_article}`
- Nội dung cần xét: `{content}`
- Tên văn bản hiện tại: `{doc_title}`

**Định dạng Output:** Dạng JSON
- `detail_name` là tên các loại văn bản pháp luật đi kèm với số hiệu (ví dụ: Thông tư 36/2012/TT-NH hoặc Thông tư 19/2024/TT-BTP) hoặc chỉ đi kèm với năm (ví dụ: Luật dân sự 2015). **Tuyệt đối không** sử dụng các cụm từ chung chung như "pháp luật về lao động", "luật hiện hành" làm giá trị cho `detail_name`.
- `detail_article` là giá trị phải có, định dạng: **Điều** và **số điều**, ví dụ: Điều 3. Nếu nội dung có 'Điều này' thì cần xác định điều luật hiện tại. **Không có** thì để trống. **Tuyệt đối không** lấy giá trị **Chương/Mục/Phần/Biểu mẫu/Phụ lục**.
- `detail_clause` là định dạng: **Khoản** và **số khoản**, ví dụ: Khoản 1. **Không có** thì để trống.
- `detail_point` là định dạng: **Điểm** và **số điểm**, ví dụ: Điểm a. **Không có** thì để trống.
- `detail_evidence` là trích dẫn chứa kết quả của mối quan hệ pháp lý. Đảm bảo trích dẫn chứa đầy đủ thông tin về `type_llm`, `detail_article`, `detail_clause`, `detail_point`, `detail_name`.

**Output:**
```json
[
    {{
        "type_llm": "Hướng dẫn chi tiết/Không có mối quan hệ",
        "detail_article": "<Điều luật bị sửa đổi (có thể có)/Trường hợp không có mối quan hệ thì để rỗng>",
        "detail_clause": "<Khoản bị sửa đổi (có thể có)/Trường hợp không có mối quan hệ thì để rỗng>",
        "detail_point": "<Điểm bị sửa đổi (có thể có)/Trường hợp không có mối quan hệ thì để rỗng>",
        "detail_name": "<Tên văn bản bị ảnh hưởng>",
        "detail_evidence": "<Trích dẫn chứa kết quả của mối quan hệ pháp lý>"
    }}
]
```
    
**Lưu ý:**
- Chỉ trả JSON, không giải thích và suy luận dài dòng. Đảm bảo trích xuất đầy đủ các mối quan hệ.
- `article`, `clause`, `point`, `name` **tuyệt đối phải** có trong `evidence`. Nếu không có thì để **Không có mối quan hệ** .
- **Tuyệt đối không** sử dụng thông tin `Số điều hiện tại` cho `article` khi trong `evidence` không có từ **Điều này**.
- Tuyệt đối chỉ sử dụng nội dung có trong điều luật, không bịa đặt thông tin không có bằng chứng rõ ràng.

---
## Bỏ qua dẫn chiếu nội bộ (BẮT BUỘC)
- **Tuyệt đối không** trích xuất mối quan hệ trỏ đến **chính văn bản hiện tại** (`{doc_title}`) hay đến **Điều/Khoản/Điểm trong cùng văn bản** — bao gồm mọi trường hợp `Điều này`, `khoản này`, `điểm này`, `văn bản này`, hoặc dẫn chiếu một Điều mà **không nêu tên một văn bản KHÁC**.
- Quy tắc này **được ưu tiên** so với mọi hướng dẫn về `Điều này` ở trên: thay vì gán `{doc_title}` cho `detail_name`, hãy bỏ qua hẳn.
- Chỉ giữ lại mối quan hệ khi `detail_name` là **một văn bản khác được nêu tên rõ ràng**. Nếu không có, trả về `Không có mối quan hệ`.
- `detail_name` **bắt buộc** là tên một **văn bản quy phạm pháp luật** (Luật, Bộ luật, Nghị định, Thông tư, Pháp lệnh, Nghị quyết, Quyết định, …), kèm số hiệu hoặc năm. **Tuyệt đối không** dùng `Phụ lục`, `Phần`, `Chương`, `Mục`, `Tiểu mục`, `Biểu mẫu`, `Danh mục`, `Mẫu`, `Điều/Khoản/Điểm` làm `detail_name`. Nếu đối tượng bị tác động chỉ là các thành phần này mà không nêu tên một văn bản khác, trả về `Không có mối quan hệ`.
- `detail_name` phải ghi **nguyên văn đầy đủ** tên văn bản như xuất hiện trong ngữ cảnh — bao gồm loại văn bản, số hiệu, ngày ban hành và trích yếu nội dung nếu có (ví dụ: `Thông tư số 16/2013/TT-BGTVT ngày 30 tháng 7 năm 2013 của Bộ trưởng Bộ Giao thông vận tải quy định về quản lý tuyến vận tải thủy từ bờ ra đảo trong vùng biển Việt Nam`). Không rút ngắn xuống chỉ còn số hiệu.

# Prompt 4: Trích xuất mối quan hệ Thay thế từ điều luật
**Nhiệm vụ:** Trích xuất các mối quan hệ `Thay thế` từ nội dung điều luật, dựa trên các loại quan hệ được xác định: thay thế Văn bản/Phần/Chương/Mục/Tiểu mục (loại: bãi bỏ), thay thế Điều (loại: thay thế), thay thế Một phần của Điều (loại: sửa đổi). Không trích xuất các mối quan hệ khác.

**Thay thế:**
- **Định nghĩa:** Văn bản/Điều luật hiện tại thay thế (bằng cách bãi bỏ hoặc sửa đổi) một Văn bản/Phần/Chương/Mục/Tiểu mục/Điều/Một phần của Điều khác. Bao gồm các trường hợp:
  - Thay thế Văn bản/Phần/Chương/Mục/Tiểu mục: Ngụ ý bãi bỏ toàn bộ hoặc phần lớn để thay bằng nội dung mới -> `type_llm`: "Bãi bỏ".
  - Thay thế Điều: Thay thế hoàn toàn một Điều luật cụ thể -> `type_llm`: "Thay thế".
  - Thay thế Một phần của Điều: Sửa đổi một phần cụ thể của Điều luật (Khoản/Điểm) -> `type_llm`: "Sửa đổi".
- **Dấu hiệu nhận biết:** 'thay thế văn bản/Điều/Phần/Chương/Mục/Tiểu mục', 'hết hiệu lực kể từ ngày', 'chấm dứt hiệu lực', 'bãi bỏ văn bản/Điều/Phần/Chương/Mục/Tiểu mục', 'sửa đổi một phần của Điều', 'thay thế hoàn toàn'. Phải có bằng chứng rõ ràng về đối tượng bị thay thế (Văn bản, Phần, Chương, Mục, Tiểu mục, Điều, hoặc Một phần của Điều).

- **Ví dụ đúng (thay thế Văn bản):** 'Quyết định này có hiệu lực kể từ ngày 25/12/2024 và thay thế Quyết định số 40/2008/QĐ-UBND' -> {{ "type_llm": "Bãi bỏ", "article": "", "clause": "", "point": "", "name": "Quyết định số 40/2008/QĐ-UBND", "evidence": "thay thế Quyết định số 40/2008/QĐ-UBND" }}

- **Ví dụ đúng (thay thế Điều):** 'Điều này thay thế Điều 5 của Luật cũ' -> {{ "type_llm": "Thay thế", "article": "Điều 5", "clause": "", "point": "", "name": "Luật cũ", "evidence": "thay thế Điều 5 của Luật cũ" }}

- **Ví dụ đúng (thay thế Một phần của Điều):** 'Khoản 2 Điều 3 được sửa đổi như sau' -> {{ "type_llm": "Sửa đổi", "article": "Điều 3", "clause": "Khoản 2", "point": "", "name": "", "evidence": "sửa đổi Khoản 2 Điều 3" }}

**Input:**
- Số điều hiện tại: `{number_of_article}`
- Nội dung cần xét: `{content}`
- Tên văn bản hiện tại: `{doc_title}`

**Định dạng Output:** Dạng JSON (mảng các đối tượng nếu có nhiều mối quan hệ).
- `detail_name` là tên các loại văn bản pháp luật đi kèm với số hiệu (ví dụ: Thông tư 36/2012/TT-NH hoặc Thông tư 19/2024/TT-BTP) hoặc chỉ đi kèm với năm (ví dụ: Luật dân sự 2015). **Tuyệt đối không** sử dụng các cụm từ chung chung như "pháp luật về lao động", "luật hiện hành" làm giá trị cho `detail_name`.
- `detail_part` là định dạng: **Phần** và **số phần**, ví dụ: Phần 1. **Không có** thì để trống.
- `detail_chapter` là định dạng: **Chương** và **số chương**, ví dụ: Chương II. **Không có** thì để trống.
- `detail_section` là định dạng: **Mục** và **số mục**, ví dụ: Mục 3. **Không có** thì để trống.
- `detail_subsection` là định dạng: **Tiểu mục** và **số tiểu mục**, ví dụ: Tiểu mục a. **Không có** thì để trống.
- `detail_article` là định dạng: **Điều** và **số điều**, ví dụ: Điều 3. Nếu nội dung có 'Điều này' thì cần xác định điều luật hiện tại. **Không có** thì để trống. **Tuyệt đối không** lấy giá trị **Chương/Mục/Phần/Biểu mẫu/Phụ lục**. **Nếu có detail_clause hoặc detail_point, BẮT BUỘC trích xuất detail_article từ ngữ cảnh phân cấp như "Khoản X Điều Y"**.
- `detail_clause` là định dạng: **Khoản** và **số khoản**, ví dụ: Khoản 1. **Không có** thì để trống.
- `detail_point` là định dạng: **Điểm** và **số điểm**, ví dụ: Điểm a. **Không có** thì để trống.
- `detail_evidence` là trích dẫn chứa kết quả của mối quan hệ pháp lý. Đảm bảo trích dẫn chứa đầy đủ thông tin về `type_llm` và các trường detail liên quan.

**Output:**
```json
[
  {{
    "type_llm": "Thay thế/Không có mối quan hệ",
    "detail_part": "<Phần bị thay thế - để trống nếu không có>",
    "detail_chapter": "<Chương bị thay thế - để trống nếu không có>",
    "detail_section": "<Mục bị thay thế - để trống nếu không có>",
    "detail_subsection": "<Tiểu mục bị thay thế - để trống nếu không có>",
    "detail_article": "<Điều bị thay thế (BẮT BUỘC có tiền tố 'Điều' nếu có) - Ví dụ: Điều 7>",
    "detail_clause": "<Khoản bị thay thế (BẮT BUỘC có tiền tố 'Khoản' nếu có) - Ví dụ: Khoản 4>",
    "detail_point": "<Điểm bị thay thế (BẮT BUỘC có tiền tố 'Điểm' nếu có) - để trống nếu không có>",
    "detail_name": "<Tên văn bản bị thay thế (Lấy từ nội dung)>",
    "detail_evidence": "<Trích dẫn chứa kết quả (Phải là đoạn trích ngắn gọn)>"
  }}
]
```

**Lưu ý:**
- Chỉ trả JSON, không giải thích và suy luận dài dòng. Đảm bảo trích xuất đầy đủ các mối quan hệ Thay thế (có thể nhiều đối tượng trong một điều luật).
- `article`, `clause`, `point`, `name` **tuyệt đối phải** có trong `evidence` và khớp với định nghĩa (Văn bản/Phần/Chương/Mục/Tiểu mục/Điều/Một phần của Điều). Nếu evidence không chứa đối tượng cụ thể theo loại quan hệ, sử dụng "Không có mối quan hệ".
- **Tuyệt đối không** sử dụng thông tin `Số điều hiện tại` cho `article` khi trong `evidence` không có từ 'Điều này' hoặc tương đương.
- Tuyệt đối chỉ sử dụng nội dung có trong điều luật, không bịa đặt thông tin không có bằng chứng rõ ràng. Nếu không có mối quan hệ Thay thế nào, output mảng với một object "Không có mối quan hệ" và các trường còn lại trống.

---
## Bỏ qua dẫn chiếu nội bộ (BẮT BUỘC)
- **Tuyệt đối không** trích xuất mối quan hệ trỏ đến **chính văn bản hiện tại** (`{doc_title}`) hay đến **Điều/Khoản/Điểm trong cùng văn bản** — bao gồm mọi trường hợp `Điều này`, `khoản này`, `điểm này`, `văn bản này`, hoặc dẫn chiếu một Điều mà **không nêu tên một văn bản KHÁC**.
- Quy tắc này **được ưu tiên** so với mọi hướng dẫn về `Điều này` ở trên: thay vì gán `{doc_title}` cho `detail_name`, hãy bỏ qua hẳn.
- Chỉ giữ lại mối quan hệ khi `detail_name` là **một văn bản khác được nêu tên rõ ràng**. Nếu không có, trả về `Không có mối quan hệ`.
- `detail_name` **bắt buộc** là tên một **văn bản quy phạm pháp luật** (Luật, Bộ luật, Nghị định, Thông tư, Pháp lệnh, Nghị quyết, Quyết định, …), kèm số hiệu hoặc năm. **Tuyệt đối không** dùng `Phụ lục`, `Phần`, `Chương`, `Mục`, `Tiểu mục`, `Biểu mẫu`, `Danh mục`, `Mẫu`, `Điều/Khoản/Điểm` làm `detail_name`. Nếu đối tượng bị tác động chỉ là các thành phần này mà không nêu tên một văn bản khác, trả về `Không có mối quan hệ`.
- `detail_name` phải ghi **nguyên văn đầy đủ** tên văn bản như xuất hiện trong ngữ cảnh — bao gồm loại văn bản, số hiệu, ngày ban hành và trích yếu nội dung nếu có (ví dụ: `Thông tư số 16/2013/TT-BGTVT ngày 30 tháng 7 năm 2013 của Bộ trưởng Bộ Giao thông vận tải quy định về quản lý tuyến vận tải thủy từ bờ ra đảo trong vùng biển Việt Nam`). Không rút ngắn xuống chỉ còn số hiệu.

# Prompt 5: Trích xuất mối quan hệ Bãi bỏ từ điều luật

**Nhiệm vụ:** Trích xuất các mối quan hệ `Bãi bỏ` từ nội dung điều luật.

**Bãi bỏ:**
- Định nghĩa: Là mối quan hệ pháp lý khi một điều luật bãi bỏ **Văn bản/Phần/Chương/Mục/Tiểu mục/Điều/Khoản/Điểm/Cụm từ/từ** trong văn bản khác hoặc bãi bỏ toàn bộ văn bản. Bao gồm cả trường hợp bãi bỏ một phần cụ thể (ví dụ: một phần của Điều luật, bao gồm Khoản/Điểm/Cụm từ/Từ).
- Dấu hiệu nhận biết: 'bãi bỏ văn bản', 'bãi bỏ phần', 'bãi bỏ chương', 'bãi bỏ mục', 'bãi bỏ tiểu mục','bãi bỏ điều', 'bãi bỏ khoản', 'bãi bỏ điểm', 'bãi bỏ từ', 'bãi bỏ cụm từ', 'thay thế văn bản', 'thay thế phần', 'thay thế chương', 'thay thế mục', 'thay thế tiểu mục'.

- **Ví dụ đúng:** 
+ 'bãi bỏ Điều 1 Nghị định 122/2012/NĐ-CP' -> {{ "type_llm": "Bãi bỏ", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 1", "detail_clause": "", "detail_point": "", "detail_name": "Nghị định 122/2012/NĐ-CP", "detail_evidence": "bãi bỏ Điều 1 Nghị định 122/2012/NĐ-CP" }}.
+ 'bãi bỏ nghị định số 71/2018/nđ-cp ngày 15 tháng 5 năm 2018 của chính phủ' -> {{ "type_llm": "Bãi bỏ", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "", "detail_clause": "", "detail_point": "", "detail_name": "Nghị định số 71/2018/nđ-cp", "detail_evidence": "bãi bỏ nghị định số 71/2018/nđ-cp ngày 15 tháng 5 năm 2018 của chính phủ" }}.
+ 'bãi bỏ Chương II của Luật X' -> {{ "type_llm": "Bãi bỏ", "detail_part": "", "detail_chapter": "Chương II", "detail_section": "", "detail_subsection": "", "detail_article": "", "detail_clause": "", "detail_point": "", "detail_name": "Luật X", "detail_evidence": "bãi bỏ Chương II của Luật X" }}.
+ 'bãi bỏ cụm từ "vi phạm" tại khoản 1 Điều 5' -> {{ "type_llm": "Bãi bỏ một phần", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 5", "detail_clause": "Khoản 1", "detail_point": "", "detail_name": "", "detail_evidence": "bãi bỏ cụm từ \"vi phạm\" tại khoản 1 Điều 5" }}.
+ 'bãi bỏ Khoản 8 Điều 1 Thông tư số 29/2020/TT-BYT' -> {{ "type_llm": "Bãi bỏ một phần", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 1", "detail_clause": "Khoản 8", "detail_point": "", "detail_name": "Thông tư số 29/2020/TT-BYT", "detail_evidence": "bãi bỏ Khoản 8 Điều 1 Thông tư số 29/2020/TT-BYT" }}.  *(Ví dụ mới: Parse phân cấp để lấy cả Điều và Khoản)*
+ 'bãi bỏ một số quy định về điều kiện đầu tư kinh doanh' -> {{ "type_llm": "Không có mối quan hệ", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "", "detail_clause": "", "detail_point": "", "detail_name": "", "detail_evidence": "" }}.
+ 'thay thế Thông tư số 29/2020/TT-BYT' -> {{ "type_llm": "Bãi bỏ", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "", "detail_clause": "", "detail_point": "", "detail_name": "Thông tư số 29/2020/TT-BYT", "detail_evidence": "thay thế Thông tư số 29/2020/TT-BYT" }}.
+ 'thay thế Điều 1 Thông tư số 29/2020/TT-BYT' -> {{ "type_llm": "Thay thế", "detail_part": "", "detail_chapter": "", "detail_section": "", "detail_subsection": "", "detail_article": "Điều 1", "detail_clause": "", "detail_point": "", "detail_name": "Thông tư số 29/2020/TT-BYT", "detail_evidence": "thay thế Điều 1 Thông tư số 29/2020/TT-BYT" }}.


**Input:**
- Số điều hiện tại: `{number_of_article}`
- Nội dung cần xét: `{content}`
- Tên văn bản hiện tại: `{doc_title}`

**Định dạng Output:** Dạng JSON
- `detail_name` là tên các loại văn bản pháp luật đi kèm với số hiệu (ví dụ: Thông tư 36/2012/TT-NH hoặc Thông tư 19/2024/TT-BTP) hoặc chỉ đi kèm với năm (ví dụ: Luật dân sự 2015). **Tuyệt đối không** sử dụng các cụm từ chung chung như "pháp luật về lao động", "luật hiện hành" làm giá trị cho `detail_name`.
- `detail_part` là định dạng: **Phần** và **số phần**, ví dụ: Phần 1. **Không có** thì để trống.
- `detail_chapter` là định dạng: **Chương** và **số chương**, ví dụ: Chương II. **Không có** thì để trống.
- `detail_section` là định dạng: **Mục** và **số mục**, ví dụ: Mục 3. **Không có** thì để trống.
- `detail_subsection` là định dạng: **Tiểu mục** và **số tiểu mục**, ví dụ: Tiểu mục a. **Không có** thì để trống.
- `detail_article` là định dạng: **Điều** và **số điều**, ví dụ: Điều 3. Nếu nội dung có 'Điều này' thì cần xác định điều luật hiện tại. **Không có** thì để trống. **Tuyệt đối không** lấy giá trị **Chương/Mục/Phần/Biểu mẫu/Phụ lục**. **Nếu có detail_clause hoặc detail_point, BẮT BUỘC trích xuất detail_article từ ngữ cảnh phân cấp như "Khoản X Điều Y"**.
- `detail_clause` là định dạng: **Khoản** và **số khoản**, ví dụ: Khoản 1. **Không có** thì để trống.
- `detail_point` là định dạng: **Điểm** và **số điểm**, ví dụ: Điểm a. **Không có** thì để trống.
- `detail_evidence` là trích dẫn chứa kết quả của mối quan hệ pháp lý. Đảm bảo trích dẫn chứa đầy đủ thông tin về `type_llm` và các trường detail liên quan. Nếu là bãi bỏ một phần của Điều (bãi bỏ khoản, điểm, cụm từ), sử dụng `type_llm`: "Bãi bỏ một phần". Nếu là thay thế **Điều**, sử dụng `type_llm`: "Thay thế". Nếu là thay thế **văn bản**, sử dụng `type_llm`: "Bãi bỏ".

**Output:**
```json
[
  {{
    "type_llm": "Bãi bỏ|Bãi bỏ một phần|Thay thế|Không có mối quan hệ",
    "detail_part": "<Phần bị bãi bỏ - để trống nếu không có>",
    "detail_chapter": "<Chương bị bãi bỏ - để trống nếu không có>",
    "detail_section": "<Mục bị bãi bỏ - để trống nếu không có>",
    "detail_subsection": "<Tiểu mục bị bãi bỏ - để trống nếu không có>",
    "detail_article": "<Điều bị bãi bỏ (BẮT BUỘC có tiền tố 'Điều' nếu có) - Ví dụ: Điều 7>",
    "detail_clause": "<Khoản bị bãi bỏ (BẮT BUỘC có tiền tố 'Khoản' nếu có) - Ví dụ: Khoản 4>",
    "detail_point": "<Điểm bị bãi bỏ (BẮT BUỘC có tiền tố 'Điểm' nếu có) - để trống nếu không có>",
    "detail_name": "<Tên văn bản bị bãi bỏ (Lấy từ nội dung)>",
    "detail_evidence": "<Trích dẫn chứa kết quả (Phải là đoạn trích ngắn gọn)>"
  }}
]
```
    
**Lưu ý:**
- Chỉ trả JSON, không giải thích và suy luận dài dòng. Đảm bảo trích xuất đầy đủ các mối quan hệ.
- Các trường `detail_part`, `detail_chapter`, `detail_section`, `detail_subsection`, `detail_article`, `detail_clause`, `detail_point`, `detail_name` **tuyệt đối phải** có trong `detail_evidence`. Nếu không có thì để **Không có mối quan hệ** và các trường detail trống.
- **Ràng buộc phân cấp:** Nếu `detail_clause` hoặc `detail_point` có giá trị, **BẮT BUỘC** `detail_article` phải có giá trị (trích xuất từ cụm như "Khoản X Điều Y" hoặc ngữ cảnh Điều cha); nếu không xác định được, dùng "Không có mối quan hệ".
- **Tuyệt đối không** sử dụng thông tin `Số điều hiện tại` cho `detail_article` khi trong `detail_evidence` không có từ **Điều này**.
- Tuyệt đối chỉ sử dụng nội dung có trong điều luật, không bịa đặt thông tin không có bằng chứng rõ ràng.

---
## Bỏ qua dẫn chiếu nội bộ (BẮT BUỘC)
- **Tuyệt đối không** trích xuất mối quan hệ trỏ đến **chính văn bản hiện tại** (`{doc_title}`) hay đến **Điều/Khoản/Điểm trong cùng văn bản** — bao gồm mọi trường hợp `Điều này`, `khoản này`, `điểm này`, `văn bản này`, hoặc dẫn chiếu một Điều mà **không nêu tên một văn bản KHÁC**.
- Quy tắc này **được ưu tiên** so với mọi hướng dẫn về `Điều này` ở trên: thay vì gán `{doc_title}` cho `detail_name`, hãy bỏ qua hẳn.
- Chỉ giữ lại mối quan hệ khi `detail_name` là **một văn bản khác được nêu tên rõ ràng**. Nếu không có, trả về `Không có mối quan hệ`.
- `detail_name` **bắt buộc** là tên một **văn bản quy phạm pháp luật** (Luật, Bộ luật, Nghị định, Thông tư, Pháp lệnh, Nghị quyết, Quyết định, …), kèm số hiệu hoặc năm. **Tuyệt đối không** dùng `Phụ lục`, `Phần`, `Chương`, `Mục`, `Tiểu mục`, `Biểu mẫu`, `Danh mục`, `Mẫu`, `Điều/Khoản/Điểm` làm `detail_name`. Nếu đối tượng bị tác động chỉ là các thành phần này mà không nêu tên một văn bản khác, trả về `Không có mối quan hệ`.
- `detail_name` phải ghi **nguyên văn đầy đủ** tên văn bản như xuất hiện trong ngữ cảnh — bao gồm loại văn bản, số hiệu, ngày ban hành và trích yếu nội dung nếu có (ví dụ: `Thông tư số 16/2013/TT-BGTVT ngày 30 tháng 7 năm 2013 của Bộ trưởng Bộ Giao thông vận tải quy định về quản lý tuyến vận tải thủy từ bờ ra đảo trong vùng biển Việt Nam`). Không rút ngắn xuống chỉ còn số hiệu.
