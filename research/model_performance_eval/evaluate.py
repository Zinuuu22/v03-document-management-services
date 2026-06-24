from locust import HttpUser, task, between, events
import time
import os
import sys
PATH_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PATH_ROOT)
import structlog
from logs.logger_conf import setup_logging
setup_logging()
logger = structlog.get_logger()

from constants import LLMsConfig


class LegalLLMStressTest(HttpUser):
    wait_time = between(1, 2)  # thời gian nghỉ giữa các request

    total_requests = 200
    request_count = 0
    start_time = None
    log_file = "stress_test_log_qwen3_30b_a3b_instruct_2507_multithread.txt"

    @task
    def send_request(self):
        if self.request_count == 0:
            # mở file mới để ghi log
            with open(self.log_file, "w") as f:
                f.write("=== Stress Test Started ===\n")
            self.start_time = time.time()

        if self.request_count < self.total_requests:
            prompt_template = """Đóng vai là một chuyên gia về luật, chuyên nhận diện sự mâu thuẫn về chế tài. Hãy tư duy theo các bước sau:

### **Bước 0: Kiểm tra trùng hoàn toàn (dừng sớm)
- Chuẩn hoá hai đầu vào (lowercase; bỏ khoảng trắng thừa; bỏ xuống dòng; chuẩn hoá dấu câu).
- Nếu hai văn bản sau chuẩn hoá TRÙNG NHAU ≥ 98%, hoặc số điều trích xuất được từ cả hai đều giống nhau và nội dung chính trùng khớp:
  → Trả ngay JSON: {'result': False, 'detail': 'Hai văn bản trùng lặp về nội dung, không xuất hiện mâu thuẫn/không đồng nhất'.}} và DỪNG LUỒNG.

### **Bước 1: Trích xuất thông tin
- Trích xuất [Chủ đề chính]:
+ [Chủ đề chính] là nội dung cốt lõi hoặc mục đích chính mà điều luật hướng đến, được xác định dựa trên ý nghĩa tổng quát của toàn bộ quy định.
+ Xác định [Chủ đề chính] của từng điều luật dựa trên nội dung tổng thể.
+ Nếu [Chủ đề chính] của hai điều luật khác nhau (ví dụ: một điều luật quy định chế tài hành chính, điều luật kia quy định chế tài hình sự), trả về kết quả dưới dạng JSON và dừng luồng tại đây: { 'result': False, 'reason': 'Chủ đề chính của hai điều luật khác nhau: <Chủ đề chính 1> (Điều luật 1) vs <Chủ đề chính 2> (Điều luật 2)' }
- Trích xuất [Vấn đề]:
+ Xác định tất cả [Vấn đề] (hành vi vi phạm/lỗi vi phạm) được quy định trong từng điều luật (ví dụ: vi phạm quy định giao thông, không nộp thuế đúng hạn).
- Với mỗi [Vấn đề], trích xuất chi tiết:
+ [Hành vi vi phạm/lỗi vi phạm]: Hành vi hoặc lỗi cụ thể bị áp dụng chế tài.
+ [Chủ thể vi phạm]: Danh sách đầy đủ các chủ thể vi phạm (người hoặc tổ chức thực hiện hành vi/lỗi).
+ [Loại hình phạt và mức độ hình phạt]: Loại hình phạt (ví dụ: phạt tiền, cảnh cáo) và mức độ cụ thể (ví dụ: 1 triệu đồng, 30 ngày tù).
+ Lập danh sách [Vấn đề] của từng điều luật, kèm chi tiết [Hành vi vi phạm/lỗi vi phạm], [Chủ thể vi phạm], [Loại hình phạt và mức độ hình phạt].
## Lưu ý: Phải trích xuất đầy đủ và chính xác, không bỏ sót bất kỳ yếu tố nào.

### **Bước 2: Xác định [Vấn đề chung]
- Trả lời câu hỏi: Trong danh sách [Vấn đề] của hai điều luật, có [Vấn đề] nào chung không?
- [Vấn đề chung] được định nghĩa là hành vi vi phạm/lỗi vi phạm xuất hiện ở cả hai điều luật với cùng bản chất (ví dụ: cùng là vi phạm quy định giao thông, hoặc cùng là không nộp thuế).
- Nếu CÓ, lập danh sách [Vấn đề chung], đặt tên ngắn gọn cho [Vấn đề chung] (danh từ/cụm danh từ, không quá 20 từ, ví dụ: "người dưới 18 tuổi phạm tội – nguyên tắc áp dụng hình phạt") và GÁN VÀO TRƯỜNG JSON: "common_issue": "<tên vấn đề chung>".
- Nếu KHÔNG, TRẢ VỀ JSON và DỪNG LUỒNG: {'result': false, 'detail': 'Hai điều luật không tồn tại vấn đề chung', 'common_issue': null}
## Lưu ý: Chỉ coi là chung nếu cả hai điều luật đều đề cập rõ ràng đến hành vi vi phạm/lỗi vi phạm đó; không gộp các hành vi/lỗi riêng lẻ thành chung.

### **Bước 3: Phân tích sơ bộ
- Với từng [Vấn đề chung]:
+ Trích xuất [Hành vi vi phạm/lỗi vi phạm] và [Chủ thể vi phạm]:
++ Sử dụng danh sách [Hành vi vi phạm/lỗi vi phạm] và [Chủ thể vi phạm] từ Bước 1.
+ So sánh [Hành vi vi phạm/lỗi vi phạm] và [Chủ thể vi phạm]:
++ Kiểm tra xem [Hành vi vi phạm/lỗi vi phạm] và [Chủ thể vi phạm] có khác biệt không (nhằm xác định phạm vi phân tích mâu thuẫn).
++ Xác định [Hành vi vi phạm/lỗi vi phạm chung] và [Chủ thể vi phạm chung] (những yếu tố giống nhau giữa hai điều luật).
- Nếu [Hành vi vi phạm/lỗi vi phạm] và [Chủ thể vi phạm] có khác biệt thì dừng luồng tại bước này: { 'result': False, 'reason': 'Không có [Hành vi vi phạm/lỗi vi phạm chung] hoặc [Chủ thể vi phạm] chung giữa hai điều luật'}.
## Lưu ý: Chỉ phân tích trong phạm vi [Vấn đề chung], không xem xét các hành vi/lỗi riêng lẻ.

### **Bước 4: Phân tích mâu thuẫn về chế tài
- Điều kiện: Chỉ thực hiện nếu [Vấn đề chung] bao gồm chế tài (dựa trên Bước 2).
- Với từng [Vấn đề chung] về chế tài, thực hiện so sánh sau:
+ Với cùng [Hành vi vi phạm/lỗi vi phạm] và [Chủ thể vi phạm], [Loại hình phạt và mức độ hình phạt A] có đối lập trực tiếp hoặc phủ định hoàn toàn [Loại hình phạt và mức độ hình phạt B] không? (Ví dụ: phạt tiền 1 triệu vs không phạt, hoặc phạt tù vs miễn phạt).
## Lưu ý quan trọng:
- Không phân tích chế tài ngoài phạm vi [Vấn đề chung] đã xác định ở Bước 2.
- Đối lập trực tiếp hoặc phủ định hoàn toàn" là khi chế tài của điều luật này loại trừ hoàn toàn chế tài của điều luật kia (ví dụ: "phải phạt" vs "không được phạt").

### **Bước 5: Tổng hợp kết quả
- 'result': True nếu có ít nhất một sự đối lập trực tiếp hoặc phủ định hoàn toàn trong [Loại hình phạt và mức độ hình phạt] của bất kỳ [Vấn đề chung] nào.
- 'result': False nếu không có sự đối lập trực tiếp hoặc phủ định hoàn toàn.
- Cung cấp lý giải ngắn gọn (2-3 câu) cho từng [Vấn đề chung], nêu rõ sự mâu thuẫn (nếu có).
- Nếu phần giải thích chứa các cụm như “không mâu thuẫn”, “không tồn tại mâu thuẫn”, “mang tính bổ sung”, “không đối lập”, thì **bắt buộc** 'result': false.
- Khi 'result': true **không được** dùng các cụm trên (trừ khi là phủ định hẳn, ví dụ: “không phải bổ sung mà là đối lập trực tiếp…”).
## Trả về kết quả dưới dạng JSON:
{
  "result": <True/False>,
  "detail": "<Lý giải ngắn gọn về sự mâu thuẫn (nếu có), nhất quán với result>",
  "common_issue": "<Tên vấn đề chung hoặc null nếu không có>",
  "action": ["<Danh sách tất cả hành vi vi phạm/lỗi vi phạm từ hai điều luật>"],
  "main_object": ["<Danh sách tất cả chủ thể vi phạm từ hai điều luật>"],
  "penalties": ["<Danh sách tất cả loại hình phạt và mức độ hình phạt từ hai điều luật>"]
}
## Đầu vào:
- Điều luật thứ 1: Điều 123: Người điều khiển ô tô vi phạm tốc độ bị phạt tiền 1.000.000 đồng.
- Điều luật thứ 2: Điều 456: Người điều khiển ô tô vượt quá tốc độ quy định bị phạt tiền 2.000.000 đồng.

## Lưu ý chung:
- Đảm bảo trích xuất đầy đủ thông tin từ hai điều luật, không bỏ sót [Hành vi vi phạm/lỗi vi phạm], [Chủ thể vi phạm], [Loại hình phạt và mức độ hình phạt].
- Giữ nhất quán giữa các bước: chỉ phân tích trong phạm vi [Vấn đề chung] đã xác định ở Bước 2.
- Chỉ coi là "mâu thuẫn" nếu có sự đối lập trực tiếp hoặc phủ định hoàn toàn (khác với 'không đồng nhất' là khác biệt không đối lập trực tiếp).
- Tuyệt đối KHÔNG sử dụng tiếng Anh trong bất kỳ phần nào của câu trả lời. Toàn bộ kết quả, bao gồm JSON, chi tiết giải thích, và tất cả trường văn bản, bắt buộc phải viết bằng tiếng Việt
- Đầu ra phải bằng tiếng Việt, dạng JSON, đầy đủ các trường thông tin, ngắn gọn và chính xác.
"""
            
            payload = {
                # "model": LLMsConfig.LLMS_MODEL_NAME,
                # "model": "qwen3:30b",
                "model": "hf.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF:UD-Q6_K_XL",
                "messages": [
                    {
                        "role": "system",
                        "content": "Bạn là một chuyên gia Pháp lý, thực hiện phân tích theo yêu cầu."
                    },
                    {
                        "role": "user",
                        "content": prompt_template
                    }
                ],  
                "temperature": float(LLMsConfig.PARAM_TEMPERATURE),
                "top_p": float(LLMsConfig.PARAM_TOP_P),
                "top_k": int(LLMsConfig.PARAM_TOP_K),
                "max_tokens": int(LLMsConfig.PARAM_MAX_NEW_TOKENS),
                "repetition_penalty": float(LLMsConfig.PARAM_REPETITION_PENALTY)
        }

            req_start = time.time()
            with self.client.post("/v1/chat/completions", json=payload, catch_response=True) as response:
                req_end = time.time()
                duration = req_end - req_start

                response_json = "ERROR"
                if response.status_code == 200:
                    response.success()
                    status = "SUCCESS"
                    response_json = response.json()['choices'][0]['message']['content']
                else:
                    response.failure(f"Status {response.status_code}")
                    status = f"FAIL ({response.status_code})"

            self.request_count += 1

            # log từng request
            with open(self.log_file, "a") as f:
                f.write(f"Request {self.request_count}: {status}, duration={duration:.3f} sec, response: {response_json}\n")
                        
            if self.request_count == self.total_requests:
                end_time = time.time()
                total_duration = end_time - self.start_time
                with open(self.log_file, "a") as f:
                    f.write(f"\n✅ Completed {self.total_requests} requests in {total_duration:.2f} seconds\n")
                logger.info("stress_test_completed", action="send_request", total_requests=self.total_requests, duration=total_duration)
                events.quitting.fire(environment=self.environment, reverse=False)
