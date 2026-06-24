import sys
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()
from core.v03.metadata_extractor.utils import get_brief_content
from core.v03.metadata_extractor.utils.regex_pattern import REGEX_PATTERNS_ISSUE_DATE


def extract_issue_date(content):
    result = {
        "issue_date": "",
    }
    
    brief_content = get_brief_content(content)
    
    issue_date_match = re.search(REGEX_PATTERNS_ISSUE_DATE["ISSUE_DATE_REGEX"]["pattern"], brief_content)
    if issue_date_match:
        day, month, year = map(int, issue_date_match.groups())
        result["issue_date"] = f"{day:02d}/{month:02d}/{year}"
    return result
    

if __name__ == "__main__":
    txt = """
HỘI ĐỒNG NHÂN DÂN TỈNH PHÚ YÊN --------
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc  ---------------
Số: 57/NQ-HĐND
Phú Yên, ngày 16 tháng 12 năm 2016
NGHỊ QUYẾT
VỀ DỰ TOÁN THU NGÂN SÁCH NHÀ NƯỚC TRÊN ĐỊA BÀN, CHI NGÂN SÁCH ĐỊA PHƯƠNG, PHƯƠNG ÁN PHÂN BỔ NGÂN SÁCH CẤP TỈNH NĂM 2017
HỘI ĐỒNG NHÂN DÂN TỈNH PHÚ YÊN  KHÓA VII, KỲ HỌP THỨ 3
Căn cứ Luật Tổ chức chính quyền địa phương năm 2015;
Căn cứ Luật Ngân sách nhà nước năm 2015;
Căn cứ Luật Đầu tư công năm 2014;
Căn cứ Quyết định số 2309/QĐ-TTg ngày 29/11/2016 của Thủ tướng Chính phủ về giao dự toán ngân sách nhà nước năm 2017; Quyết định số 2577/QĐ-BTC ngày 29/11/2016 của Bộ trưởng Bộ Tài chính về việc giao dự toán thu, chi ngân sách nhà nước năm 2017;
Xét báo cáo của Ủy ban nhân dân tỉnh số 218/BC-UBND, ngày 08/12/2016 về tình hình ước thực hiện dự toán ngân sách năm 2016, dự toán thu ngân sách nhà nước trên địa bàn, chi ngân sách địa phương, phương án phân bổ ngân sách cấp tỉnh năm 2017; Báo cáo số 220/BC-UBND, ngày 08/12/2016 về tình hình thực hiện đầu tư xây dựng cơ bản năm 2016 và dự kiến nguồn kế hoạch vốn ngân sách Nhà nước năm 2017; Báo cáo thẩm tra của Ban Kinh tế - Ngân sách Hội đồng nhân dân tỉnh; ý kiến thảo luận của đại biểu Hội đồng nhân dân tỉnh tại kỳ họp.
QUYẾT NGHỊ:
Điều 1. Thông qua dự toán ngân sách nhà nước tỉnh Phú Yên năm 2017 như sau:
1. Tổng thu ngân sách nhà nước trên địa bàn: 3.790.000 triệu đồng (Bằng chữ: Ba nghìn bảy trăm chín mươi tỷ đồng);
2. Tổng thu ngân sách địa phương: 7.093.800 triệu đồng (Bằng chữ: Bảy nghìn không trăm chín mươi ba tỷ, tám trăm triệu đồng);
3. Tổng chi ngân sách địa phương: 7.093.800 triệu đồng (Bằng chữ: Bảy nghìn không trăm chín mươi ba tỷ, tám trăm triệu đồng).
(Đính kèm các phụ lục 01, 03, 04, 05, 06, 08)
Điều 2. Phân bổ ngân sách cấp tỉnh năm 2017 như sau:
1. Tổng thu ngân sách cấp tỉnh năm 2017 là 6.131.420 triệu đồng (Bằng chữ: Sáu nghìn một trăm ba mươi mốt tỷ, bốn trăm hai mươi triệu đồng);
2. Tổng chi ngân sách cấp tỉnh năm 2017 là: 6.131.420 triệu đồng (Bằng chữ: Sáu nghìn một trăm ba mươi mốt tỷ, bốn trăm hai mươi triệu đồng).
Trong đó:
2.1. Chi trong cân đối ngân sách: 6.072.020 triệu đồng, gồm:
a) Phân bổ ngân sách tỉnh cho các cơ quan, ban, ngành thuộc tỉnh, các khoản trả nợ vay (gốc và lãi) là: 2.113.490 triệu đồng;
b) Bổ sung Quỹ dự trữ tài chính: 1.000 triệu đồng;
c) Dự phòng chi ngân sách: 54.930 triệu đồng;
d) Chi tạo nguồn thực hiện cải cách tiền lương theo quy định: 216.800 triệu đồng;
đ) Các khoản chi thường xuyên ngân sách khối tỉnh chưa phân bổ: 37.550 triệu đồng;
e) Bổ sung cho ngân sách các huyện, thị xã, thành phố: 2.670.800 triệu đồng;
g) Các khoản chi ngân sách địa phương chưa phân bổ: 977.450 triệu đồng, gồm:
- Chi đầu tư phát triển chưa phân bổ: 718.692 triệu đồng, bao gồm:
+ Chi đầu tư từ nguồn vốn xây dựng cơ bản tập trung dự phòng: 39.830 triệu đồng;
+ Chi đầu tư từ nguồn vốn ngân sách trung ương hỗ trợ có mục tiêu vốn trong nước (Phân bổ sau khi có quyết định của trung ương phân bổ vốn chi tiết): 383.750 triệu đồng;
+ Chi đầu tư từ nguồn vốn thực hiện Chương trình mục tiêu quốc gia (Phân bổ sau khi có Quyết định của Trung ương giao chỉ tiêu kế hoạch cụ thể): 138.557 triệu đồng;
+ Chi đầu tư từ nguồn vốn ngân sách trung ương hỗ trợ có mục tiêu vốn ngoài nước (Phân bổ sau khi có quyết định hoặc thông báo của trung ương phân bổ vốn chi tiết): 96.855 triệu đồng;
+ Chi đầu tư từ nguồn vốn vay Ngân hàng Phát triển Việt Nam (Phân bổ sau khi có Quyết định của Trung ương cho vay): 59.700 triệu đồng;
- Chi thường xuyên chưa phân bổ: 258.758 triệu đồng; bao gồm:
+ Kinh phí sự nghiệp giáo dục - đào tạo và dạy nghề 10.835 triệu đồng tiếp tục theo dõi thực hiện trong điều hành ngân sách năm 2017;
+ Kinh phí sự nghiệp chưa phân bổ 205.050 triệu đồng tiếp tục theo dõi thực hiện trong điều hành ngân sách năm 2017;
+ Kinh phí quản lý hành chính 3.195 triệu đồng tiếp tục theo dõi thực hiện trong điều hành ngân sách năm 2017;
+ Chi thường xuyên từ nguồn vốn sự nghiệp thực hiện Chương trình mục tiêu quốc gia (phân bổ sau khi có Quyết định của Trung ương giao chỉ tiêu kế hoạch cụ thể) là 39.679 triệu đồng.
2.2. Chi từ nguồn thu để lại quản lý qua ngân sách nhà nước: 59.400 triệu đồng.
(Đính kèm các phụ lục 02, 07)
Điều 3. Thông qua các giải pháp thực hiện dự toán ngân sách địa phương của Ủy ban nhân dân tỉnh trình Hội đồng nhân dân tỉnh; các giải pháp tại Báo cáo thẩm tra của Ban Kinh tế - Ngân sách và nhấn mạnh một số vấn đề cơ bản sau đây:
1. Ủy ban nhân dân tỉnh chỉ đạo các ngành và các địa phương trong việc tổ chức theo dõi sát diễn biến giá cả thị trường trên địa bàn tỉnh, đặc biệt là giá các mặt hàng thiết yếu phục vụ đời sống nhân dân; có giải pháp cụ thể điều hành và bình ổn giá các mặt hàng thiết yếu trong những tháng cuối năm 2016 và đầu năm 2017, không để xảy ra tình trạng thiếu hàng, sốt giá trên địa bàn tỉnh, nhất là trong dịp tết Nguyên đán cổ truyền của dân tộc.
2. Ủy ban nhân dân tỉnh chỉ đạo các ngành và các địa phương tiếp tục triển khai và thực hiện có hiệu quả các Nghị quyết của Chính phủ về một số giải pháp hỗ trợ sản xuất kinh doanh, hỗ trợ thị trường, tái cơ cấu kinh tế, giải quyết nợ xấu và xem đây là nhiệm vụ trọng tâm trong điều hành dự toán ngân sách nhà nước. Với mục tiêu tiếp tục thực hiện chính sách tài khóa thắt chặt, tiết kiệm, phân bổ nguồn lực đầu tư công hợp
lý, hiệu quả để góp phần cùng chính sách tiền tệ ổn định kinh tế vĩ mô. Thực hiện tăng cường công tác thu ngân sách, bố trí chi chặt chẽ, tiết kiệm và nâng cao hiệu quả chi tiêu công. Ưu tiên nguồn lực để thực hiện các chính sách an sinh xã hội, hỗ trợ người nghèo, đối tượng bảo trợ xã hội...
3. Nhiệm vụ quan trọng của công tác thu ngân sách năm 2017 là tập trung tổ chức bám sát tình hình đầu tư, phát triển sản xuất kinh doanh và hoạt động xuất nhập khẩu năm 2017; tính đúng, tính đủ, kịp thời các khoản thu ngân sách theo các chính sách, chế độ hiện hành và những chế độ, chính sách mới sẽ có hiệu lực thi hành năm 2017; các khoản thu NSNN của doanh nghiệp, tổ chức, cá nhân phát sinh, phải nộp trong năm 2017, trong đó chú ý tính các khoản thu phát sinh từ các dự án đầu tư đã hết thời gian ưu đãi thuế. Bên cạnh đó, tổ chức thực hiện tốt Luật Quản lý thuế nhằm động viên các khoản thu nộp vào NSNN; đồng thời vừa phải tạo sự khuyến khích sản xuất kinh doanh phát triển, tăng tích lũy và phát triển nguồn thu; vừa đảm bảo nguồn lực thực hiện nhiệm vụ phát triển kinh tế - xã hội của tỉnh, vừa chủ động ứng phó với những tác động của giá cả thị trường, vừa phải đẩy mạnh cải cách thủ tục hành chính trong lĩnh vực thuế, tạo môi trường thuận lợi cho doanh nghiệp; thực hiện cơ chế tự kê
khai, tự nộp thuế, tăng trách nhiệm của người nộp thuế và cơ quan thu thuế; tăng cường công tác kiểm tra, chống thất thu, nợ đọng thuế, tạo môi trường bình đẳng cho mọi doanh nghiệp thuộc các thành phần kinh tế.
4. Ủy ban nhân dân tỉnh chỉ đạo các ngành, các cấp thực hiện nghiêm quy định của Luật Ngân sách Nhà nước; tăng cường công tác quản lý và giám sát chặt chẽ các khoản chi, đảm bảo yêu cầu chi đã được bố trí trong dự toán được Hội đồng nhân dân tỉnh thông qua. Trường hợp nếu nguồn thu không đạt dự toán phải sắp xếp lại một số khoản chi để giảm chi tương ứng với nguồn thu.
5. Ưu tiên bố trí chi đầu tư phát triển để thực hiện mục tiêu phát triển kinh tế - xã hội năm 2017 và giai đoạn 2016-2020 của tỉnh, trong đó ưu tiên bố trí dự toán cho các dự án, công trình trọng điểm của tỉnh, phát triển khu vực nông nghiệp, nông thôn, thúc đẩy xóa đói giảm nghèo và phát triển bền vững; tiếp tục ưu tiên bố trí vốn đầu tư phát triển nguồn nhân lực cho lĩnh vực giáo dục-đào tạo, y tế, khoa học-công nghệ, bảo vệ môi trường, an ninh, quốc phòng...
6. Đối với các khoản chưa phân bổ 1.015 tỷ đồng (trong đó: Vốn Ngân sách địa phương chưa phân bổ 977,45 tỷ đồng; ngân sách cấp tỉnh chưa phân bổ 37,55 tỷ đồng), giao Ủy ban nhân dân tỉnh tiếp tục lập phương án phân bổ, báo cáo với Thường trực Hội đồng nhân dân tỉnh cho ý kiến trước khi thực hiện (kèm theo phụ lục số 09).
7. Trong quá trình thực hiện dự toán ngân sách nhà nước năm 2017, Ủy ban nhân dân tỉnh chỉ đạo các ngành, các địa phương phấn đấu thu vượt nhiệm vụ được giao để bổ sung đầu tư phát triển, phòng chống thiên tai, dịch bệnh và xử lý các vấn đề cấp bách, đột xuất phát sinh trong năm ở từng ngành, từng cấp và dành nguồn để thực hiện cải cách tiền lương, thực hiện các chính sách đảm bảo an sinh xã hội theo quy định.
Điều 4. Tổ chức thực hiện
Hội đồng nhân dân tỉnh giao:
1. Ủy ban nhân dân tỉnh tổ chức thực hiện giao nhiệm vụ thu, chi ngân sách cho từng cơ quan, ban, ngành và các địa phương thuộc tỉnh quản lý theo đúng quy định của Luật Ngân sách Nhà nước. Tổ chức quản lý, điều hành ngân sách theo dự toán đã được Hội đồng nhân dân tỉnh quyết định. Trong quá trình thực hiện, giữa hai kỳ họp Hội đồng nhân dân tỉnh, nếu có phát sinh thay đổi so với dự toán ngân sách đã phân bổ thì Ủy ban nhân dân tỉnh báo cáo Thường trực Hội đồng nhân dân tỉnh trước khi thực hiện và báo cáo Hội đồng nhân dân tỉnh tại kỳ họp gần nhất.
2. Thường trực Hội đồng nhân dân, các Ban của Hội đồng nhân dân và các đại biểu Hội đồng nhân dân tỉnh căn cứ chức năng, nhiệm vụ, quyền hạn theo luật định tăng cường đôn đốc, kiểm tra, giám sát việc thực hiện Nghị quyết này.
Nghị quyết này đã được Hội đồng nhân dân tỉnh Phú Yên khóa VII, kỳ họp thứ 3 thông qua ngày 15/12/2016 và có hiệu lực thi hành từ ngày thông qua./.
CHỦ TỊCH     Huỳnh Tấn Việt
    """
    logger.info("extract_result", action="main", result=extract_issue_date(txt))
