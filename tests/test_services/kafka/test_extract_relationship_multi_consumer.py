import json
from kafka import KafkaProducer
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

sys.path.append(PROJECT_ROOT)
from constants import KafkaConfig, MongoDBConfig, AppConfig, PreprocessTopics, MongoDBCollectionConfig

        
producer = KafkaProducer(bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                        api_version=(0,11,5))

def _send_message_to_kafka_topic(data, kafka_topic):
    message_value = json.dumps(data).encode("utf-8")
    producer.send(kafka_topic, value=message_value)        
    producer.flush()
#     producer.close()

def send_result_validate(data):    
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.EXTRACT_RELATIONSHIP_QUERY_TOPIC)

if __name__ == "__main__":    
    # doc_id = "f215c5fa-c48a-4a4a-867b-30e535b71e13"
    # data = {
    #     "request_id": doc_id,
    #     "doc_id": doc_id,
    #     "doc_code": "",
    #     "top_k":10
    # }


    data = {
        "request_id":"3bdf5894-ac2c-4c4c-bc07-46b896f2be0f", 
        "doc_id":"f215c5fa-c48a-4a4a-867b-30e535b71e13",
        "doc_content": """CHÍNH PHỦ
------- | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
---------------

Số: 12/NQ-CP | Hà Nội, ngày 07 tháng 02 năm 2023

NGHỊ QUYẾT

BAN HÀNH CHƯƠNG TRÌNH HÀNH ĐỘNG CỦA CHÍNH PHỦ THỰC HIỆN NGHỊ QUYẾT SỐ 15-NQ/TW NGÀY 05 THÁNG 5 NĂM 2022 CỦA BỘ CHÍNH TRỊ VỀ PHƯƠNG HƯỚNG, NHIỆM VỤ PHÁT TRIỂN THỦ ĐÔ HÀ NỘI ĐẾN NĂM 2030, TẦM NHÌN ĐẾN NĂM 2045

CHÍNH PHỦ

Căn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;

Căn cứ Luật sửa đổi, bổ sung một số điều của Luật Tổ chức Chính phủ và Luật Tổ chức chính quyền địa phương ngày 22 tháng 11 năm 2019;

Căn cứ Nghị quyết số 15-NQ/TW ngày 05 tháng 5 năm 2022 của Bộ Chính trị về phương hướng, nhiệm vụ phát triển Thủ đô Hà Nội đến năm 2030, tầm nhìn đến năm 2045;

Xét đề nghị của Bộ trưởng Bộ Kế hoạch và Đầu tư,

QUYẾT NGHỊ:

Điều 1. Ban hành kèm theo Nghị quyết này Chương trình hành động của Chính phủ thực hiện Nghị quyết số 15-NQ/TW ngày 05 tháng 5 năm 2022 của Bộ Chính trị về phương hướng, nhiệm vụ phát triển Thủ đô Hà Nội đến năm 2030, tầm nhìn đến năm 2045.

Điều 2. Nghị quyết này có hiệu lực thi hành từ ngày ký ban hành.

Điều 3. Các Bộ trưởng, Thủ trưởng cơ quan ngang bộ, Chủ tịch Ủy ban nhân dân các tỉnh, thành phố trực thuộc trung ương và các tổ chức, cá nhân có liên quan chịu trách nhiệm thi hành Nghị quyết này./.

Nơi nhận:
- Ban Bí thư Trung ương Đảng;
- Thủ tướng, các Phó Thủ tướng Chính phủ;
- Các Bộ, cơ quan ngang Bộ, cơ quan thuộc Chính phủ;
- HĐND, UBND các tỉnh, thành phố trực thuộc TW;
- Văn phòng Trung ương, các ban của Đảng;
- Văn phòng Tổng bí thư;
- Văn phòng Chủ tịch nước;
- Hội đồng Dân tộc, các Ủy ban của Quốc hội;
- Văn phòng Quốc hội;
- Tòa án nhân dân tối cao;
- Viện kiểm soát nhân dân tối cao;
- Kiểm toán nhà nước;
- Cơ quan Trung ương Mặt trận Tổ quốc Việt Nam;
- Cơ quan Trung ương của các đoàn thể;
- VPCP: BTCN, các PCN, Trợ lý TTg, TGĐ Cổng TTĐT, các Vụ, Cục;
- Lưu: VT, QHĐP (3)Q.Cường. | TM. CHÍNH PHỦ
THỦ TƯỚNG




Phạm Minh Chính

CHƯƠNG TRÌNH HÀNH ĐỘNG CỦA CHÍNH PHỦ

THỰC HIỆN NGHỊ QUYẾT SỐ 15-NQ/TW NGÀY 05 THÁNG 5 NĂM 2022 CỦA BỘ CHÍNH TRỊ VỀ PHƯƠNG HƯỚNG, NHIỆM VỤ PHÁT TRIỂN THỦ ĐÔ HÀ NỘI ĐẾN NĂM 2030, TẦM NHÌN ĐẾN NĂM 2045
(Ban hành kèm theo Nghị quyết số 12/NQ-CP ngày 07 tháng 02 năm 2023 của Chính phủ)

Căn cứ các mục tiêu, nhiệm vụ và giải pháp chủ yếu tại Nghị quyết số 15-NQ/TW ngày 05 tháng 5 năm 2022 của Bộ Chính trị về phương hướng, nhiệm vụ phát triển Thủ đô Hà Nội đến năm 2030, tầm nhìn đến năm 2045, Chính phủ ban hành Chương trình hành động triển khai thực hiện Nghị quyết như sau:

I. MỤC ĐÍCH, YÊU CẦU

1. Việc xây dựng và ban hành Chương trình hành động nhằm thống nhất chỉ đạo các cấp, các ngành tổ chức quán triệt, triển khai, cụ thể hóa Nghị quyết, tạo sự chuyển biến rõ rệt về nhận thức, hành động và trách nhiệm của cán bộ, công chức, viên chức các cấp, các ngành và nhân dân Thủ đô Hà Nội về vị trí, vai trò đặc biệt quan trọng trong phát triển Thủ đô Hà Nội ngàn năm văn hiến, trung tâm đầu não chính trị - hành chính của quốc gia, trở thành trung tâm, động lực thúc đẩy phát triển vùng đồng bằng sông Hồng, vùng kinh tế trọng điểm Bắc Bộ, vùng Thủ đô và cả nước; đến năm 2030, trở thành Thành phố có sức cạnh tranh cao trong khu vực và thế giới, phấn đấu phát triển ngang tầm thủ đô các nước phát triển trong khu vực.

2. Chương trình hành động phải cụ thể hóa Nghị quyết số 15-NQ/TW và quán triệt định hướng phát triển và phương hướng, nhiệm vụ phát triển đất nước giai đoạn 2021-2030 tại Nghị quyết Đại hội đại biểu toàn quốc làn thứ XIII của Đảng; xác định các nhiệm vụ chủ yếu, thể hiện các giải pháp cụ thể và thiết thực, được tổ chức tốt để thực hiện thắng lợi mục tiêu của Nghị quyết số 15-NQ/TW.

3. Chương trình hành động phải thể hiện được vai trò kiến tạo, điều phối của Chính phủ theo tinh thần đồng hành cùng Đảng bộ, chính quyền và nhân dân Thủ đô đồng thời xác định các nội dung, nhiệm vụ chủ yếu để Chính phủ và các bộ, ngành và Ủy ban nhân dân thành phố Hà Nội, Ủy ban nhân dân các tỉnh, thành phố trong vùng kinh tế trọng điểm Bắc Bộ, vùng đồng bằng sông Hồng, vùng Thủ đô và cả nước tập trung chỉ đạo xây dựng và thực hiện các chủ trương, chính sách có tính đột phá; huy động và phân bổ nguồn lực thực hiện các dự án trọng điểm, quan trọng của Hà Nội; xây dựng một số cơ chế, chính sách đặc thù và phân cấp cho chính quyền Thủ đô Hà Nội thẩm quyền, trách nhiệm giải quyết công việc phù hợp với yêu cầu, nhiệm vụ đặc thù của Thủ đô; tăng cường các hình thức liên kết, hợp tác phù hợp với nhu cầu và thế mạnh của tùng địa phương và mở rộng hợp tác quốc tế.

4. Phấn đấu đạt các mục tiêu, chỉ tiêu cụ thể đã đề ra trong Nghị quyết

a) Giai đoạn từ nay đến năm 2030:

- Thủ đô Hà Nội là thành phố “Văn hiến - Văn minh - Hiện đại”; trở thành trung tâm, động lực thúc đẩy phát triển vùng đồng bằng sông Hồng, vùng kinh tế trọng điểm Bắc Bộ, vùng Thủ đô và cả nước; hội nhập quốc tế sâu rộng, có sức cạnh tranh cao với khu vực, thế giới, phấn đấu phát triển ngang tầm thủ đô các nước phát triển trong khu vực.

- Tốc độ tăng trưởng GRDP bình quân hàng năm giai đoạn 2021-2025 tăng khoảng 7,5% - 8,0%[1]; GRDP giai đoạn 2026-2030 tăng 8,0 - 8,5%/năm; GRDP bình quân đầu người đến năm 2025 đạt khoảng 8.300-8.500 USD, đến năm 2030 đạt khoảng 12.000 - 13.000 USD; Tỷ trọng công nghiệp chế biến, chế tạo trong GRDP đến năm 2025 đạt khoảng 17%, đến năm 2030 đạt khoảng 20%; Tỷ trọng kinh tế số trong GRDP đến năm 2025 đạt khoảng 30%, đến năm 2030 đạt khoảng 40%; Tỷ trọng giá trị sản xuất nông nghiệp ứng dụng công nghệ cao trong giá trị sản xuất nông nghiệp đến năm 2025 đạt 70%, đến năm 2030 đạt 80%; Năng suất lao động tăng bình quân đến năm 2025 đạt 7,0-7,5%, đến năm 2030 đạt 7,5%; Tỷ lệ đô thị hóa đến năm 2025 đạt khoảng 60-62%, đến năm 2030 đạt 75%; Tỷ lệ nước thải đô thị được xử lý đến năm 2025 đạt 50-55%, đến năm 2030 đạt 100%.

b) Tầm nhìn đến năm 2045: Thủ đô Hà Nội là thành phố kết nối toàn cầu, có mức sống và chất lượng cuộc sống cao, với GRDP bình quân đầu người đạt trên 36.000 USD; kinh tế, văn hóa, xã hội phát triển toàn diện, đặc sắc và hài hòa; tiêu biểu cho cả nước; có trình độ phát triển ngang tầm thủ đô các nước phát triển trong khu vực và trên thế giới.

II. NHIỆM VỤ VÀ GIẢI PHÁP CHỦ YẾU

Để đạt được các chỉ tiêu cụ thể nêu trên, trong thời gian tới, bên cạnh các nhiệm vụ thường xuyên, các bộ, cơ quan ngang bộ, cơ quan thuộc Chính phủ, Ủy ban nhân dân thành phố Hà Nội cần cụ thể hóa và tổ chức triển khai thực hiện các nhiệm vụ, giải pháp sau đây:

1. Công tác quán triệt, tuyên truyền, phổ biến thông tin, tạo sự đồng thuận trong xây dựng, tổ chức thực hiện các chương trình, kế hoạch hành động thực hiện Nghị quyết số 15-NQ/TW

- Các bộ, ngành, Ủy ban nhân dân thành phố Hà Nội và cả nước tập trung triển khai ngay công tác nghiên cứu, quán triệt nội dung của Nghị quyết trong toàn thể đội ngũ cán bộ đảng viên, công chức, viên chức, người lao động thuộc thẩm quyền quản lý làm chuyển biến nhận thức và quyết tâm cao của các ngành, các cấp. Tiếp tục phát huy mạnh mẽ truyền thống cách mạng, ngàn năm văn hiến, anh hùng, hoà bình, hữu nghị, tinh thần chủ động, sáng tạo, ý chí tự lực, tự cường và khát vọng vươn lên của cán bộ, đảng viên và nhân dân Hà Nội.

- Công tác tuyên truyền về Nghị quyết cần được tiến hành với quy mô sâu rộng với nhiều hình thức đa dạng, phong phú, hấp dẫn và phù hợp với từng đối tượng, kết hợp với việc tuyên truyền thực hiện Nghị quyết Đại hội đại biểu toàn quốc lần thứ XIII của Đảng, Nghị quyết Đại hội Đảng bộ thành phố gắn với từng giai đoạn, tạo nhận thức sâu sắc về cơ hội, thuận lợi, thách thức, cũng như những tiềm năng, lợi thế, vị trí, vai trò đặc biệt quan trọng của Thủ đô Hà Nội để tiếp tục tạo ra sự phát triển bứt phá mới trong những năm tới.

- Các bộ, cơ quan liên quan và tỉnh, thành phố trong cả nước chủ động phối hợp tốt với các cơ quan thông tấn, báo chí để tuyên truyền, phổ biến thông tin về Nghị quyết số 15-NQ/TW của Bộ Chính trị và Chương trình, kế hoạch hành động thực hiện Nghị quyết; tăng cường ứng dụng công nghệ truyền thông mới, áp dụng nhiều hình thức, phương thức đa dạng để phổ biến thông tin và triển khai thực hiện Nghị quyết đạt hiệu quả cao nhất.

- Tăng cường thông tin, tuyên truyền đối ngoại về Thủ đô Hà Nội nói chung và mục tiêu xây dựng, phát triển Thủ đô trở thành đô thị thông minh, hiện đại, xanh, sạch, đẹp, an toàn, phát triển nhanh và bền vững; là trung tâm chính trị - hành chính quốc gia, trung tâm lớn về kinh tế, văn hóa, giáo dục và đào tạo, khoa học và công nghệ, hội nhập quốc tế.

2. Phát triển kinh tế Thủ đô nhanh và bền vững trên cơ sở tiếp tục đẩy mạnh cơ cấu lại kinh tế gắn với đổi mới mô hình tăng trưởng, huy động và sử dụng có hiệu quả mọi nguồn lực

a) Tiếp tục đẩy mạnh cơ cấu lại kinh tế gắn với đổi mới mô hình tăng trưởng, lấy khoa học và công nghệ cao và đổi mới sáng tạo là động lực then chốt để phát triển kinh tế xã hội. Trong đó, ưu tiên phát huy hiệu quả nguồn lực trí tuệ con người, đẩy mạnh ứng dụng khoa học, công nghệ, thành tựu của Cách mạng công nghiệp lần thứ 4; nâng cao tỷ lệ kinh tế số trong quy mô nền kinh tế; xây dựng và phát triển một số ngành - chuỗi sản phẩm công nghiệp, dịch vụ hiện đại, đặc trưng trở thành những trụ cột phát triển của kinh tế Thủ đô như: công nghiệp - công nghệ cao, dịch vụ tài chính - ngân hàng, logistics, phát triển công nghiệp văn hóa, du lịch, đặc biệt là du lịch văn hóa. Cụ thể:

- Hình thành và phát triển các mô hình kinh tế mới (kinh tế xanh, kinh tế tuần hoàn, kinh tế chia sẻ, kinh tế ban đêm,...); thúc đẩy quá trình chuyển đổi số, phát triển thương mại điện tử và kinh tế số, đảm bảo đầy đủ quyền tự do, an toàn trong hoạt động kinh doanh cho người dân và doanh nghiệp; trong đó việc chuyển đổi số là một nhiệm vụ quan trọng trong chỉ đạo, điều hành.

- Phát triển mạnh các loại dịch vụ trình độ chất lượng cao như: Dịch vụ tư vấn đối với khoa học - công nghệ, y tế, giáo dục - đào tạo, tài chính,... để đưa Thủ đô Hà Nội trở thành trung tâm tài chính, thương mại, dịch vụ, du lịch mang tầm khu vực và quốc tế. Phát triển loại hình giáo dục, đào tạo, các dịch vụ y tế chuyên sâu chất lượng cao ngang tầm với các nước phát triển trong khu vực và thế giới. Phát triển nền tư pháp số để Thủ đô Hà Nội trở thành nơi giải quyết, xử lý tư pháp tốt của cả nước, khu vực và thế giới.

- Tiếp tục thực hiện việc cơ cấu lại ngành công nghiệp theo hướng tập trung phát triển công nghiệp mũi nhọn có hàm lượng công nghệ và giá trị gia tăng cao: cơ khí chế tạo; công nghiệp công nghệ thông tin và truyền thông, phần mềm, sản phẩm số,...; điện, điện tử; công nghệ mới trong lĩnh vực năng lượng, trí tuệ nhân tạo, cơ sở dữ liệu lớn (block chain); công nghệ sinh học, công nghệ y học, công nghiệp dược,..

- Cơ cấu lại ngành nông nghiệp theo hướng nông nghiệp sinh thái, công nghệ cao, xây dựng hệ thống tổ chức sản xuất, kinh doanh giống phục vụ nhu cầu sản xuất nông nghiệp trên địa bàn Thủ đô và các tỉnh lân cận; xây dựng nông thôn xanh, hiện đại, giàu bản sắc; xây dựng người nông dân văn minh, có kỹ năng, trình độ, là chủ thể xây dựng, thụ hưởng thành quả phát triển. Chuyển mạnh từ xây dựng các “chuỗi cung ứng nông sản” sang phát triển các “chuỗi giá trị ngành hàng”. Hình thành một số khu, cụm liên kết ngành phục vụ sản xuất nông nghiệp (kho tàng, bến bãi, nhà máy chế biến, trạm trại giống...). Ưu tiên phát triển công nghiệp chế biến gắn với thị trường tiêu thụ nông sản chính của Thủ đô và phát triển các khu nông nghiệp ứng dụng công nghệ cao, các mô hình nông nghiệp thông minh ứng dụng công nghệ số.

b) Tập trung nguồn lực để đầu tư phát triển, nâng cấp hệ thống kết cấu hạ tầng kinh tế - xã hội của Thành phố một cách tổng thể, đồng bộ, hiện đại và hiệu quả, trong đó chú trọng phân bổ, ưu tiên hợp lý nguồn vốn từ ngân sách nhà nước, kết hợp với đẩy mạnh công tác xã hội hóa thu hút nguồn vốn đầu tư vào phát triển kết cấu hạ tầng, nhất là phương thức đối tác công tư (PPP); thu hút và sử dụng hiệu quả hơn vốn đầu tư hỗ trợ phát triển chính thức (ODA) và vốn vay của các nhà tài trợ, phấn đấu xây dựng và phát triển thành phố Hà Nội trở thành đô thị thông minh, hiện đại, có bản sắc, mang tính dẫn dắt, tạo hiệu ứng lan tỏa, liên kết vùng đô thị phía Bắc và cả nước.

c) Phát triển mạnh các thành phần kinh tế để tạo đột phá trong phát triển kinh tế - xã hội của Thủ đô Hà Nội

- Cơ cấu lại, đổi mới doanh nghiệp nhà nước theo hướng nâng cao hiệu quả hoạt động sản xuất kinh doanh; thực hiện cổ phần hóa, thoái vốn của doanh nghiệp nhà nước trong các ngành nghề, lĩnh vực mà Nhà nước không cần nắm giữ hoặc không giữ quyền chi phối. Tập trung xử lý dứt điểm các tổng công ty nhà nước, các dự án, công trình đầu tư của doanh nghiệp nhà nước kém hiệu quả, thua lỗ kéo dài.

- Phát triển đầy đủ, đồng bộ các thị trường, nhất là thị trường tài chính, tiền tệ, khoa học và công nghệ, lao động, văn hóa.

- Tạo dựng môi trường đầu tư, kinh doanh thuận lợi, bình đẳng giữa các thành phần kinh tế; thúc đẩy khu vực kinh tế tư nhân phát triển mạnh mẽ cả về số lượng, chất lượng. Đẩy mạnh phát triển doanh nghiệp đổi mới sáng tạo, khoa học và công nghệ, kết nối theo chuỗi giá trị với các doanh nghiệp trong vùng đồng bằng sông Hồng và cả nước cũng như trong khu vực và thế giới.

- Phát triển khu vực kinh tế tập thể, tạo điều kiện thuận lợi để các hợp tác xã, liên hiệp hợp tác xã phát triển hiệu quả trong mọi lĩnh vực. Đồng thời, chú trọng phát triển kinh tế tư nhân, tạo điều kiện thuận lợi để kinh tế tư nhân thực sự thành một động lực quan trọng, tạo đột phá trong phát triển kinh tế xã hội của thành phố, đặc biệt trong ngành kinh tế mũi nhọn, có lợi thế như chế biến chế tạo, công nghiệp hỗ trợ, du lịch, thương mại, dịch vụ logistics, ngân hàng,...

- Chủ động thu hút đầu tư trực tiếp nước có chọn lọc, ưu tiên các ngành, lĩnh vực có đóng góp tích cực cho quá trình tái cấu trúc kinh tế theo hướng bền vững, xanh, thông minh, hiện đại, đổi mới sáng tạo, đem lại giá trị gia tăng cao, khuyến khích các dự án có quy mô lớn, có hàm lượng công nghệ, công nghệ hiện đại sử dụng tiết kiệm năng lượng có khả năng lan tỏa, gắn kết, kéo theo sự phát triển của doanh nghiệp trong nước; thu hút các tập đoàn đa quốc gia thành lập các trung tâm đổi mới sáng tạo, trung tâm nghiên cứu phát triển đặt trụ sở tại Hà Nội.

3. Phát triển mạnh mẽ sự nghiệp văn hóa, xây dựng người Hà Nội thanh lịch, văn minh, xứng đáng là trung tâm lớn về giáo dục và đào tạo, khoa học và công nghệ, y tế. Bảo đảm an sinh, phúc lợi xã hội, nâng cao chất lượng cuộc sống của nhân dân Thủ đô

a) Tập trung phát triển văn hóa Thủ đô xứng tầm với truyền thống nghìn năm Thăng Long - Hà Nội.

- Nghiên cứu, xây dựng cơ chế, chính sách để có nguồn lực đầu tư hợp lý phát triển văn hóa của Thủ đô. Tập trung đầu tư bảo tồn, phát huy giá trị các di tích lịch sử - văn hóa, danh lam thắng cảnh quốc gia đặc biệt, di tích lịch sử - văn hóa, danh lam thắng cảnh quốc gia, di sản thế giới, các công trình kiến trúc có giá trị văn hóa lịch sử trên địa bàn; đầu tư, nâng cấp, hiện đại hóa một số công trình văn hóa, thể thao mới, mang tính biểu tượng, tiêu biểu của Thủ đô (tượng đài, quảng trường, bảo tàng, nhà hát, công viên, trung tâm văn hóa, điện ảnh...)

- Triển khai chương trình nghiên cứu khoa học xã hội và nhân văn về phát triển văn hóa và con người Thủ đô. Đưa văn hóa và con người Hà Nội thực sự trở thành giá trị tinh thần to lớn, nguồn lực nội sinh quan trọng quyết định sự phát triển bền vững Thủ đô.

- Phát huy hiệu quả, giá trị mô hình Hà Nội - Thành phố sáng tạo về thiết kế trong Mạng lưới các thành phố sáng tạo của UNESCO, phấn đấu trở thành trung tâm hội tụ thiết kế và đổi mới ở khu vực - kinh đô sáng tạo của Đông Nam Á.

- Đẩy mạnh phát triển các ngành công nghiệp văn hóa Thủ đô. Tiếp tục xây dựng Thủ đô Hà Nội tham gia vào “Mạng lưới các thành phố sáng tạo của UNESCO” trong các lĩnh vực thủ công mỹ nghệ và nghệ thuật dân gian; ẩm thực; văn học và âm nhạc...

b) Nâng cao chất lượng giáo dục toàn diện, xây dựng Thủ đô Hà Nội là trung tâm lớn, tiêu biểu của cả nước về giáo dục, đào tạo chất lượng cao đáp ứng được quá trình chuyển đổi số quốc gia, đổi mới sáng tạo hội nhập với khu vực và quốc tế. Tăng cường đầu tư, phát triển Đại học Quốc gia Hà Nội, Trường Đại học Bách Khoa Hà Nội theo hướng có trọng tâm, trọng điểm phát triển ngang tầm các đại học có chất lượng cao trong khu vực.

- Nghiên cứu xây dựng phát triển các cơ sở đào tạo nguồn nhân lực chất lượng cao, nhất là nguồn nhân lực tại chỗ, đáp ứng yêu cầu của quá trình chuyển đổi số quốc gia, đổi mới sáng tạo và hội nhập quốc tế và cuộc Cách mạng công nghiệp lần thứ tư, đồng thời, phát triển được đội ngũ nhân lực, các nhà quản trị có khả năng ứng dụng công nghệ và phát triển các dịch vụ hiện đại trong các lĩnh vực ngân hàng, tài chính, logistics, bảo hiểm, công nghệ thông tin, phân phối bán lẻ, tư vấn, dịch vụ phát triển kinh doanh.

- Phấn đấu phát triển giáo dục nghề nghiệp Thủ đô đạt và vượt các mục tiêu, chỉ tiêu phát triển giáo dục nghề nghiệp tại Chiến lược phát triển giáo dục nghề nghiệp đến năm 2030, trong đó đẩy mạnh đào tạo nhân lực có kỹ năng nghề cao; hình thành các trung tâm Quốc gia, trung tâm Vùng về đào tạo và thực hành nghề chất lượng cao trên địa bàn Thủ đô.

c) Phát triển mạnh mẽ khoa học, công nghệ và đổi mới sáng tạo, góp phần phát triển Thủ đô hiện đại văn minh; lấy doanh nghiệp làm trung tâm, tạo động lực phát triển mới, nâng cao năng suất, chất lượng hiệu quả và sức cạnh tranh của kinh tế Thủ đô.

- Xây dựng môi trường số kết nối, triển khai nền tảng kết nối để chia sẻ dữ liệu khoa học công nghệ, để khai thác hiệu quả nguồn tài nguyên và thành quả nghiên cứu khoa học công nghệ.

- Thí điểm hợp tác đầu tư, hỗ trợ hình thành Trung tâm nghiên cứu và phát triển (R&D) ở một số doanh nghiệp ở một số ngành, lĩnh vực ưu tiên nhằm phát triển sản phẩm mới, mở rộng thị trường, tăng khả năng cạnh tranh của sản phẩm; có mức ưu đãi phù hợp đối với các doanh nghiệp thực hiện đề tài, dự án ươm tạo công nghệ, đổi mới công nghệ.

- Tiếp tục tập trung đầu tư xây dựng, phát triển Khu công nghệ cao Hòa Lạc thành Trung tâm nghiên cứu, phát triển, chuyển giao công nghệ và đổi mới sáng tạo của Hà Nội và của quốc gia. Đến năm 2030, Thủ đô Hà Nội nằm trong nhóm dẫn đầu khu vực Đông Nam Á về khoa học dữ liệu và trí tuệ nhân tạo, công nghệ 5G và sau 5G. Đến năm 2045, là một trong những Trung tâm nghiên cứu hàng đầu về một số lĩnh vực khoa học cơ bản (toán học, vật lý, y học,...) trong khu vực Đông Nam Á và Châu Á.

- Tiếp cận và tận dụng tối đa cơ hội của cuộc cách mạng công nghiệp lần thứ tư để phát triển các lĩnh vực có nhiều tiềm năng và lợi thế như: nông nghiệp công nghệ cao, nông nghiệp hữu cơ, công nghệ sinh học, công nghệ thông tin, công nghệ vật liệu mới, công nghệ xử lý môi trường, y tế, công nghệ số, khoa học dữ liệu, trí tuệ nhân tạo, chuỗi khối, in 3D, phát triển du lịch...

- Xây dựng chương trình trọng điểm phát triển doanh nghiệp đổi mới sáng tạo và phát triển sản phẩm chủ lực của Thủ đô trên cơ sở các hoạt động hỗ trợ ứng dụng, đổi mới, chuyển giao công nghệ, áp dụng các tiêu chuẩn hệ thống quản lý tiên tiến, công cụ cải tiến năng suất chất lượng, áp dụng chỉ dẫn địa lý, áp dụng và quản lý hệ thống truy xuất nguồn gốc; xây dựng, quản lý và phát triển nhãn hiệu sản phẩm...

- Phát triển Sàn giao dịch công nghệ Hà Nội tiến tới là sản giao dịch công nghệ quốc gia kết nối liên thông với các trung tâm công nghệ lớn của thế giới. Hình thành và phát triển mạng lưới các tổ chức dịch vụ đánh giá, định giá công nghệ, môi giới chuyển giao công nghệ, tài sản trí tuệ. Kết nối nền tảng trực tuyến về hệ sinh thái khởi nghiệp và đổi mới sáng tạo quốc gia và thành phố Hà Nội. Xây dựng bộ chỉ số đổi mới sáng tạo, đẩy mạnh phát triển văn hóa khởi nghiệp, đổi mới sáng tạo trên địa bàn.

- Tăng cường đầu tư, hợp tác quốc tế trong phát triển khoa học, công nghệ và đổi mới sáng tạo; tìm kiếm công nghệ tiên tiến, thúc đẩy hoạt động ứng dụng, chuyển giao tiến bộ khoa học và công nghệ, đổi mới công nghệ phục vụ phát triển sản xuất, kinh doanh, phát triển kinh tế - xã hội, bảo đảm quốc phòng, an ninh Thủ đô.

d) Xây dựng hệ thống y tế tiên tiến, hiện đại, một số lĩnh vực tiệm cận các nước phát triển trên thế giới.

- Đầu tư các bệnh viện đa khoa, chuyên khoa tại Hà Nội ngang tầm các trung tâm chuyên sâu kỹ thuật cao của khu vực và thế giới. Đẩy mạnh thực hiện chủ trương xã hội hóa trong lĩnh vực y tế; hình thành hệ thống khám chữa bệnh theo mô hình liên kết giữa các bệnh viện, trung tâm chuyên khoa thành phố với các trung tâm y tế cấp huyện, y tế tư nhân để nâng cao chất lượng dịch vụ khám, chữa bệnh và phục hồi chức năng ở tất cả các tuyến.

- Phát triển hệ thống y tế phổ cập, mô hình bác sỹ gia đình gắn với chăm sóc sức khỏe ban đầu cho nhân dân. Năm 2025, hoàn thành xây dựng, quản lý hồ sơ sức khỏe điện tử toàn dân, 100% người dân được khám sức khỏe định kỳ hàng năm.

đ) Gắn phát triển kinh tế với thực hiện tiến bộ xã hội, đảm bảo an sinh, phúc lợi xã hội; không ngừng nâng cao đời sống vật chất, tinh thần, chất lượng cuộc sống của nhân dân Thủ đô.

- Phát triển hệ thống an sinh xã hội toàn diện, bao phủ toàn dân, mở rộng đối tượng thuộc diện thụ hưởng chính sách; chủ động bố trí nguồn lực và tạo điều kiện tối đa cho người dân tiếp cận với các dịch vụ xã hội, nhất là y tế, giáo dục, dạy nghề, trợ giúp pháp lý, nhà ở,...

- Thực hiện đồng bộ các chính sách xã hội, giảm nghèo bền vững, nâng cao phúc lợi xã hội hướng tới phát triển bền vững, thu hẹp khoảng cách giàu, nghèo giữa thành thị và nông thôn; nâng mức trợ cấp xã hội thường xuyên, trợ giúp khẩn cấp phù hợp với khả năng ngân sách thành phố.

- Khuyến khích các doanh nghiệp, tổ chức, cá nhân trong và ngoài nước quyên góp, ủng hộ, tài trợ, đầu tư vào các hoạt động trợ giúp xã hội, tạo nguồn lực để nâng mức hỗ trợ đối với người cao tuổi, người nghèo, người khuyết tật, trẻ em mồ côi, trợ giúp xã hội trong thiên tai dịch bệnh; các hoạt động về tư vấn, tuyên truyền, đấu tranh phòng, chống ma túy, cai nghiện ma túy, phát triển các mô hình quản lý sau cai nghiện,...

- Thực hiện các giải pháp giải quyết việc làm, đảm bảo ổn định thu nhập cho người lao động, nâng cao hiệu quả hoạt động vay vốn, giải quyết việc làm; ứng dụng công nghệ thông tin giải quyết các chính sách an sinh xã hội, thực hiện tốt các chính sách bảo hiểm xã hội, bảo hiểm thất nghiệp, bảo hiểm tai nạn lao động; ngăn chặn, đấu tranh, phòng ngừa các tệ nạn xã hội.

- Thực hiện tốt công tác dân tộc và các chính sách về dân tộc, tôn giáo; ưu tiên tập trung nguồn lực phát triển nhanh và bền vững vùng đồng bào dân tộc thiểu số và miền núi.

- Xây dựng các cơ sở, mô hình tập luyện, sân chơi, câu lạc bộ thể dục, thể thao trong nhà, ngoài trời,... Xây dựng trung tâm thể thao đóng vai trò là trung tâm thể thao trọng điểm làm chức năng trung tâm vùng đồng thời là trung tâm thể thao cấp quốc gia; bố trí đất dành cho hoạt động thể dục, thể thao duy trì ổn định từ 3,5m2 đến 04m2/người dân. Tăng cường ứng dụng khoa học và công nghệ, y sinh học thể thao hiện đại.

4. Nâng cao chất lượng công tác quy hoạch, thực hiện nghiêm việc quản lý quy hoạch; đẩy mạnh xây dựng kết cấu hạ tầng đồng bộ, phát triển và quản lý đô thị; khai thác, sử dụng hiệu quả tài nguyên, bảo vệ môi trường

a) Về công tác quy hoạch

- Khẩn trương hoàn thành việc lập Quy hoạch Thủ đô Hà Nội thời kỳ 2021 - 2030, tầm nhìn đến năm 2050 phù hợp với Chiến lược phát triển kinh tế - xã hội, quy hoạch tổng thể quốc gia, quy hoạch ngành quốc gia, quy hoạch vùng, Nghị quyết số 15-NQ/TW của Bộ Chính trị về phương hướng phát triển Thủ đô Hà Nội đến năm 2030, tầm nhìn đến năm 2045.

- Rà soát, hoàn thành điều chỉnh tổng thể Quy hoạch chung xây dựng Thủ đô đến năm 2030 và tầm nhìn đến năm 2050 với sông Hồng là trục xanh, cảnh quan trung tâm, phát triển đô thị hài hoà hai bên sông của Hà Nội.

- Phối hợp với các địa phương trong vùng Thủ đô Hà Nội thực hiện có hiệu quả hoặc rà soát, báo cáo cấp có thẩm quyền điều chỉnh Quy hoạch xây dựng vùng Thủ đô Hà Nội đến năm 2030 và tầm nhìn đến năm 2050 đã được Thủ tướng Chính phủ phê duyệt tại Quyết định số 768/QĐ-TTg ngày 06/5/2016 theo hướng toàn diện hơn, phù hợp với yêu cầu phát triển của Thủ đô Hà Nội và các địa phương trong giai đoạn tới.

- Đẩy nhanh việc lập kế hoạch sử dụng đất 05 năm giai đoạn 2021-2025 của thành phố Hà Nội, lập và điều chỉnh quy hoạch sử dụng đất thời kỳ 2021- 2030 và kế hoạch sử dụng đất hàng năm cấp huyện để đảm bảo quỹ đất phù hợp, thống nhất với các quy hoạch đã được phê duyệt. Kiểm soát chặt chẽ quy trình chuyển đổi đất nông thôn thành đất đô thị theo quy hoạch và chương trình phát triển đô thị.

- Khẩn trương xây dựng và triển khai hiệu quả các quy hoạch phân khu đô thị sông Hồng, sông Đuống để sắp xếp ổn định dân cư hai bên sông; quy hoạch và phát triển các đô thị vệ tinh, nội đô lịch sử, trong đó trước mắt nghiên cứu xây dựng thành phố (đô thị loại II) trực thuộc Thủ đô; sớm nghiên cứu xác định và xây dựng quy hoạch phát triển các đô thị có vị trí, chức năng đặc thù, gắn với khu công nghiệp, khu chế xuất, bến cảng, sân bay,...

- Phối hợp với các bộ, ngành và các địa phương trong vùng tổ chức lập quy hoạch và xây dựng kết cấu hạ tầng ở ngoại thành phục vụ việc di dời các cơ sở công nghiệp gây ô nhiễm môi trường, cơ sở giáo dục đại học, bệnh viện ra khỏi khu vực nội thành; xây dựng lộ trình và biện pháp di dời phù hợp với điều kiện, địa điểm cụ thể và đặc điểm của từng cơ sở cần phải di dời, bảo đảm tính khả thi.

- Tổ chức, rà soát, điều chỉnh các đồ án quy hoạch chuyên ngành hạ tầng kỹ thuật, quy hoạch phát triển đô thị kết nối đồng bộ, gắn với quy hoạch xây dựng nông thôn, giữ gìn bản sắc văn hóa truyền thống, khai thác hiệu quả cảnh quan thiên nhiên vùng nông thôn kết hợp với phát triển du lịch xanh.

- Tổ chức lập và sớm hoàn thành các quy hoạch bảo tồn và phát huy giá trị các khu vực di sản đô thị, khu vực nội đô lịch sử; không gian văn hóa đô thị đáp ứng nhu cầu sáng tạo của người dân; quy hoạch bảo quản, tu bổ, phục hồi di tích lịch sử - văn hóa, danh lam thắng cảnh quốc gia đặc biệt trên địa bàn Thành phố.

- Xây dựng hệ thống dữ liệu về quy hoạch phát triển đô thị; ứng dụng hệ thống thông tin địa lý GIS và công nghệ số, nền tảng số trong quy hoạch và quản lý phát triển đô thị; đảm bảo quản lý phát triển đô thị theo quy hoạch, gắn với quản lý không gian hành chính đô thị.

b) Tập trung đầu tư hoàn thành các công trình kết cấu hạ tầng trọng điểm, xây dựng kết cấu hạ tầng đồng bộ, trong đó:

- Đẩy nhanh tiến độ hoàn thành xây dựng các tuyến đường quốc lộ, đường cao tốc, đường xuyên tâm, đường vành đai, hệ thống đường kết nối nội vùng và liên vùng theo quy hoạch, đồng bộ với quy hoạch kiến trúc, cảnh quan, xây dựng đô thị văn minh hiện đại của Thủ đô; đầu tư xây dựng thêm các cầu qua sông Hồng, sông Đuống với kiến trúc đẹp hiện đại, đặc trưng cho bản sắc và tạo điểm nhấn cho Thủ đô Hà Nội; hoàn chỉnh hạ tầng kỹ thuật; cải tạo chỉnh trang, phục hồi hệ thống sông Hồng, phát huy giá trị cảnh quan lịch sử,...; các dự án giao thông trên cao, hệ thống đường sắt đô thị trên cao và ngầm, các công trình ngầm gắn với khả năng kết nối đồng bộ giữa các hệ thống giao thông công cộng và loại hình vận tải hành khách công cộng khác; khẩn trương hoàn thành đưa vào vận hành khai thác thương mại các tuyến đường sắt đô thị.

- Tập trung nguồn lực đầu tư hạ tầng logistics của Hà Nội trở thành điểm trung chuyển để kết nối với các quốc gia, địa phương trong cả nước về đường bộ, đường sắt, hàng không và đẩy mạnh ứng dụng công nghệ thông tin trong hoạt động logistics, hình thành, xây dựng mô hình dịch vụ logistics điện tử. Quy hoạch và xây dựng hạ tầng số đồng bộ trong quy hoạch và xây dựng kết cấu hạ tầng đô thị.

- Phấn đấu hoàn thành đường Vành đai 4 trước năm 2027 và chuẩn bị đầu tư, xây dựng đường Vành đai 5 trước năm 2030.

- Nghiên cứu, đề xuất xây dựng mô hình thành phố trực thuộc Thủ đô tại khu vực phía bắc (vùng Đông Anh, Mê Linh, Sóc Sơn) và phía Tây (vùng Hòa Lạc, Xuân Mai) và mô hình đô thị thông minh trên cơ sở phát triển khu vực hai bên trục đường Nhật Tân - Nội Bài.

c) Xây dựng phát triển và quản lý đô thị.

- Nghiên cứu tăng tỷ lệ đất phát triển đô thị phù hợp với quy hoạch, hoàn chỉnh mô hình cấu trúc phát triển Thủ đô; tập trung hình thành một số cực tăng trưởng mới. Phấn đấu đến năm 2025, có từ 3-5 huyện phát triển thành quận; đến năm 2030 có thêm 1-2 huyện phát triển thành quận.

- Từng bước tạo ra chùm đô thị, các đô thị vệ tinh, mô hình phát triển đô thị theo định hướng giao thông (TOD), theo các tuyến đường vành đai, tuyến đường kết nối nội vùng, liên vùng, tuyến đường sắt đô thị nhằm giảm tải cho đô thị trung tâm. Quản lý chặt chẽ việc phát triển nhà ở cao tầng và gia tăng dân số tại khu vực đô thị trung tâm.

- Xây dựng hạ tầng đô thị thông minh với ứng dụng mạng lưới kết nối số phục vụ cho quản lý và vận hành đô thị, góp phần xây dựng đô thị thông minh. Xây dựng thương hiệu đô thị để phát huy kinh tế đô thị cho một số khu vực trọng điểm.

- Đẩy mạnh xã hội hóa đầu tư, huy động và sử dụng có hiệu quả mọi nguồn lực, nhất là nguồn lực từ các nhà đầu tư chiến lược cho phát triển đô thị, cơ sở hạ tầng theo quy hoạch đã được phê duyệt và phù hợp với quy định của pháp luật.

- Thường xuyên cải tạo, chỉnh trang, phục hồi, tái thiết đô thị hiệu quả để nâng cao hiệu quả sử dụng đất; khai thác hiệu quả và bền vững các công trình văn hóa, lịch sử các không gian công cộng trong phát triển kinh tế đô thị gắn với bảo tồn không gian lịch sử văn hóa, truyền thống và cảnh quan, xanh, sạch đẹp và khang trang tại khu vực nội đô lịch sử.

- Đẩy mạnh ứng dụng công nghệ thông tin trong quản lý đô thị, quản lý an ninh trật tự đô thị, an toàn giao thông,...; tăng cường kỉ cương, kỷ luật và nâng cao chất lượng quản lý đô thị, trật tự xây dựng, quản lý chặt chẽ và khai thác hợp lý các không gian công cộng trong phát triển kinh tế khu vực đô thị.

d) Tăng cường quản lý và sử dụng hiệu quả tài nguyên, bảo vệ môi trường, chủ động phòng, chống thiên tai và ứng phó với với biến đổi khí hậu.

- Nghiên cứu, đề xuất các giải pháp cụ thể triển khai pháp luật về bảo vệ môi trường, đưa nội dung bảo vệ môi trường và ứng phó với với biến đổi khí hậu vào quá trình xây dựng quy hoạch, kế hoạch, chương trình, dự án,... theo hướng chủ động phòng ngừa và kiểm soát nguồn gây ô nhiễm tác động xấu đến môi trường, tạo chuyển biến rõ nét trong công tác bảo vệ môi trường để xây dựng Thủ đô xanh, sạch, đẹp phát triển bền vững; giải quyết các vấn đề môi trường “nóng” như ô nhiễm môi trường nước, ô nhiễm không khí tại đô thị, ô nhiễm tiếng ồn, công tác thu gom, xử lý rác thải sinh hoạt,... đặc biệt là đối với sông Tô Lịch.

- Xây dựng và phát triển các mô hình kinh tế tuần hoàn, kinh tế xanh, các-bon thấp hướng tới mục tiêu trung hòa các-bon vào năm 2050. Khuyến khích và có các biện pháp hỗ trợ các khu công nghiệp, khu chế xuất trên địa bàn thành phố chuyển đổi sang loại hình khu công nghiệp sinh thái hoặc xây dựng mới các khu công nghiệp sinh thái nhằm sử dụng hiệu quả các nguồn tài nguyên, năng lượng, nâng cao tính cạnh tranh của khu công nghiệp trong thu hút đầu tư và phát triển bền vững.

- Thực hiện các giải pháp nâng cao chất lượng dịch vụ đô thị, quản lý và xử lý hiệu quả các vấn đề về nhà ở đô thị, quản lý đất đai, trật tự xây dựng, trật tự và an toàn giao thông, xử lý chất thải, nước thải và bảo đảm vệ sinh môi trường. Thực hiện hoàn thiện và chuẩn hóa hồ sơ địa chính, cơ sở dữ liệu về đất đai và tài nguyên vào năm 2025.

- Rà soát các dự án đã được giao đất, cho thuê đất và dự án chưa được giao đất để kịp thời điều chỉnh dự án hoặc thu hồi nhằm tạo quỹ đất đầu tư các dự án hạ tầng kinh tế - xã hội quan trọng, xây dựng nhà ở tái định cư, nhà ở cho người thu nhập thấp.

- Tăng cường quản lý và bảo vệ nguồn nước, môi trường các lưu vực sông, xử lý ô nhiễm khu vực cửa sông, hệ thống hồ ao; đảm bảo an ninh nguồn nước sinh hoạt, sản xuất; xử lý hệ thống nước thải kết hợp với hành lang thoát lũ và chỉnh trang xây dựng các không gian xanh đô thị nhằm từng bước khắc phục tình trạng ngập úng trên địa bàn thành phố. Tập trung hoàn thành cải tạo môi trường sông Nhuệ - Đáy, sông Tô Lịch, sông Tích, các chương trình chống úng, ngập; hạ tầng xử lý rác thải, nước thải, cây xanh đô thị,.. theo quy hoạch đô thị. Thực hiện việc lập, công bố danh mục hồ, ao không được san lấp; hành lang bảo vệ nguồn nước.

- Dự báo và xây dựng kế hoạch hành động ứng phó biến đổi khí hậu của thành phố Hà Nội giai đoạn 2021 - 2030 và kế hoạch thực hiện Chiến lược bảo vệ môi trường quốc gia đến năm 2030, tầm nhìn đến năm 2050; xây dựng và triển khai mạng lưới quan trắc chất lượng môi trường, hệ thống thông tin cơ sở dữ liệu khí tượng thủy văn và giám sát biến đổi khí hậu trên địa bàn thành phố để phục vụ cho công tác quản lý nhà nước, dự báo, cảnh báo về khí tượng thủy văn và ứng phó biến đổi khí hậu trên địa bàn thành phố.

- Đẩy mạnh và nâng cao hiệu lực, hiệu quả công tác xây dựng, thực hiện quy hoạch, kế hoạch, quản lý, khai thác, sử dụng các loại tài nguyên trên địa bàn Thủ đô gắn với công tác đánh giá tác động môi trường và đánh giá tác động, tính dễ bị tổn thương, rủi ro, tổn thất và thiệt hại do biến đổi khí hậu. Khuyến khích nghiên cứu, ứng dụng công nghệ mới trong sản xuất, sử dụng các loại nguyên vật liệu mới thân thiện với môi trường để thay thế các loại vật liệu truyền thống.

- Tăng cường công tác thanh tra, kiểm tra giám sát các lĩnh vực tài nguyên và môi trường, đất đai theo hướng tăng cường thanh tra đột xuất và giảm thanh tra theo kế hoạch. Bên cạnh đó, tăng cường công tác tuyên truyền, nâng cao nhận thức về môi trường của các cấp quản lý và mọi người dân để cùng thực hiện tốt Chiến lược quốc gia về Tăng trưởng xanh và Kế hoạch hành động quốc gia thực hiện Chương trình Nghị sự 2030 vì sự phát triển bền vững.

- Sau khi di dời các nhà máy, trường đại học, cao đẳng, trường nghề ra khỏi khu vực nội đô, giữ lại quỹ đất đã giải phóng mặt bằng quy hoạch làm công viên, vườn hoa cây xanh, bảo đảm cảnh quan và các hồ nước để tiêu thoát nước nội thành tránh ngập úng cục bộ, điều hòa lại không khí, môi trường tự nhiên của đô thị.

5. Củng cố quốc phòng, an ninh, xây dựng khu vực phòng thủ vững chắc, giữ vững chủ quyền quốc gia; bảo đảm an ninh chính trị, trật tự, an toàn xã hội

- Tiếp tục xây dựng Thủ đô Hà Nội là thành phố hòa bình; tạo môi trường thuận lợi để phát triển kinh tế, xã hội, bảo đảm cuộc sống bình yên cho nhân dân thành phố. Kịp thời phát hiện, ngăn chặn các hình thức hợp tác kinh tế có tác động, chuyển hóa chính trị, tạo sự lệ thuộc, làm suy giảm tính độc lập, tự chủ của nền kinh tế. Bảo đảm vững chắc an ninh chính trị nội bộ, an ninh kinh tế, an ninh xã hội, quản lý xuất, nhập cảnh... Chủ động phòng ngừa, đấu tranh, ngăn chặn, vô hiệu hóa mọi âm mưu của các thế lực thù địch tác động chuyển hóa phá hoại nội bộ; đấu tranh phòng, chống “tự diễn biến”, “tự chuyển hóa” bảo đảm sự vững mạnh của hệ thống chính trị trên địa bàn Thủ đô; tăng cường công tác đấu tranh phòng, chống tội phạm và vi phạm pháp luật trên địa bàn thành phố; chủ động dự báo tình hình, sẵn sàng ứng phó với các tình huống xảy ra... góp phần tạo môi trường ổn định phục vụ phát triển kinh tế, văn hóa, xã hội, đối ngoại của Thủ đô.

- Tiếp tục thực hiện hiệu quả Nghị quyết số 88/NQ-CP ngày 13/9/2017 của Chính phủ ban hành Chương trình hành động của Chính phủ thực hiện Chỉ thị số 12-CT/TW ngày 05/01/2017 của Bộ Chính trị về tăng cường sự lãnh đạo của Đảng đối với bảo đảm an ninh kinh tế trong điều kiện phát triển kinh tế thị trường định hướng xã hội chủ nghĩa và hội nhập kinh tế quốc tế, nhất là trong bối cảnh hội nhập ngày càng sâu rộng như hiện nay.

- Thực hiện tốt quy hoạch tổng thể bố trí quốc phòng, an ninh, kết hợp với phát triển kinh tế - xã hội của Thủ đô; xây dựng các công trình phòng thủ theo quy hoạch thế trận quân sự khu vực phòng thủ đúng với vị trí chiến lược quan trọng về quốc phòng, an ninh của thành phố với cả nước, vừa đảm bảo quốc phòng, an ninh, vừa phục vụ sản xuất kinh doanh. Tăng cường tiềm lực, nâng cao hiệu quả quản lý nhà nước về an ninh, trật tự; thực hiện quyết liệt, đồng bộ các giải pháp bảo đảm trật tự an toàn giao thông, chống ùn tắc giao thông; tăng cường công tác phòng, chống cháy nổ; bảo đảm an ninh môi trường, tài nguyên, vệ sinh an toàn thực phẩm... trên địa bàn Thủ đô. Tiếp tục quan tâm đầu tư, trang bị cơ sở vật chất, phương tiện vũ khí, trang thiết bị phục vụ công tác, chiến đấu, góp phần xây dựng lực lượng Công an thành phố Hà Nội chính quy, tinh nhuệ, hiện đại có sức chiến đấu cao, đáp ứng yêu cầu, nhiệm vụ trong tình hình mới theo tinh thần Nghị quyết số 12-NQ/TW ngày 16/3/2022 của Bộ Chính trị; bảo đảm tính lưỡng dụng của các công trình, vừa bảo đảm phục vụ dân sinh vừa đáp ứng yêu cầu về an ninh, quốc phòng khi có tình huống phức tạp xảy ra.

- Bảo vệ tuyệt đối an toàn các mục tiêu, sự kiện quan trọng diễn ra trên địa bàn, tạo môi trường hòa bình, ổn định, an ninh và an toàn để xây dựng, phát triển Thủ đô và đất nước.

- Bảo vệ chủ quyền số quốc gia và hội nhập quốc tế; bảo vệ tuyệt đối an toàn, an ninh thông tin, xây dựng môi trường mạng an toàn, tin cậy nhằm thúc đẩy, nâng cao chất lượng, hiệu quả ứng dụng công nghệ thông tin để xây dựng, phát triển Thủ đô và đất nước.

- Tiếp tục làm tốt công tác tuyên truyền, giáo dục, nâng cao nhận thức và ý thức trách nhiệm để mọi người dân, mọi tầng lớp xã hội chung tay bảo vệ Tổ quốc; giữ vững ổn định chính trị, trật tự, an toàn xã hội.

6. Đẩy mạnh công tác đối ngoại, hội nhập quốc tế, hợp tác phát triển, nâng cao vị thế, uy tín của Thủ đô

a) Đẩy mạnh hoạt động đối ngoại, hội nhập và hợp tác quốc tế.

- Bám sát và triển khai hiệu quả đường lối đối ngoại mà Đại hội đại biểu toàn quốc lần thứ XIII của Đảng đề ra. Đẩy mạnh công tác đối ngoại, hội nhập quốc tế, nâng cao hiệu quả công tác đối ngoại và xác định đây là nguồn lực, động lực cho phát triển Thủ đô. Phát huy tiềm năng, thế mạnh của Thủ đô là “Thành phố vì hòa bình” để tạo lợi thế cạnh tranh, thúc đẩy sự thịnh vượng, nâng cao vị thế của Thủ đô để hiện thực hóa mục tiêu đưa Hà Nội thành thành phố kết nối toàn cầu, trung tâm hội nhập quốc tế của khu vực và thế giới.

- Đẩy mạnh hội nhập quốc tế, tạo sức bật mới cho Thủ đô Hà Nội trong giai đoạn tới. Đẩy mạnh hợp tác toàn diện, mở rộng không gian liên kết kinh tế vùng nhằm tạo tiền đề vững chắc cho quan hệ đối ngoại, hội nhập, hợp tác phát triển tiếp tục được mở rộng, đảm bảo tính thiết thực, hiệu quả, nâng cao vị thế của Thủ đô trong khu vực và thế giới.

- Chủ động tham gia làm cầu nối hữu nghị giữa Việt Nam và thế giới nhằm phát huy tối đa vai trò của Thủ đô Hà Nội nói riêng và Việt Nam nói chung tại các cơ chế đa phương, đặc biệt là tại Hiệp hội các Quốc gia Đông Nam Á (ASEAN), Liên Hợp quốc, Diễn đàn Hợp tác kinh tế châu Á - Thái Bình Dương (APEC) và các khuôn khổ hợp tác khu vực và quốc tế trong những vấn đề quan trọng có tầm chiến lược, phù hợp với yêu cầu, khả năng và điều kiện cụ thể. Bên cạnh đó, tiếp tục thúc đẩy hội nhập quốc tế toàn diện, sâu rộng, linh hoạt và hiệu quả vì lợi ích quốc gia, dân tộc. Hà Nội cần chú trọng gắn kết chặt chẽ quá trình hội nhập quốc tế với việc nâng cao sức mạnh tổng hợp và tận dụng tiềm năng vốn có của Thủ đô.

- Đẩy mạnh và nâng cao chất lượng, hiệu quả hội nhập quốc tế trong nhiều lĩnh vực như kinh tế, văn hóa, xã hội, du lịch, môi trường, khoa học - công nghệ, giáo dục - đào tạo và các lĩnh vực khác. Để sánh ngang với các thủ đô, thành phố lớn trong khu vực và trên thế giới, Hà Nội cần tận dụng hiệu quả cơ hội từ hội nhập quốc tế sâu rộng để làm sức bật cho Thủ đô, như tăng cường thu hút vốn FDI và phát triển kinh tế, đẩy mạnh phát triển thương mại quốc tế, tăng cường hợp tác văn hóa, khoa học - công nghệ, giáo dục - đào tạo... Qua đó, Hà Nội sẽ tiếp tục phát huy được thế mạnh và vai trò của mình là cầu nối hữu nghị quốc gia, “Thành phố vì hòa bình”, “Thành phố phát triển”, góp phần nâng cao vị thế của Thủ đô.

- Tăng cường hợp tác với các đô thị, các tổ chức quốc tế; chủ động tích cực tham gia hệ thống mạng lưới các đô thị xanh, thích ứng, bản sắc, bền vững và thông minh ở khu vực và quốc tế.

- Nâng cao năng lực, chất lượng hội nhập quốc tế; chủ động và tích cực nắm bắt cơ hội, thúc đẩy thực thi có hiệu quả các cam kết quốc tế, nhất là các Hiệp định thương mại tự do thế hệ mới, đi đôi với nâng cao năng lực cạnh tranh, thu hút các nguồn đầu tư, tài chính chất lượng, công nghệ cao; củng cố các mối quan hệ truyền thống, mở rộng hợp tác với các thủ đô, thành phố lớn trên thế giới trong các hoạt động liên kết, hợp tác về khoa học và công nghệ, xúc tiến đầu tư, thương mại, du lịch.

- Thành phố Hà Nội nghiên cứu, xây dựng tiêu chí thí điểm và lộ trình thực hiện các “tiêu chí về tầm ảnh hưởng” và “tiêu chí đáng sống” để phù hợp với các đô thị lớn khác trên thế giới.

- Hỗ trợ, tạo điều kiện để các tổ chức quốc tế, tổ chức nước ngoài thực hiện thủ tục thành lập văn phòng đại diện tại Việt Nam (các trung tâm văn hóa, văn phòng đại diện của các hãng thông tin, báo chí...).

- Chủ động tham mưu, đề xuất sáng kiến đăng cai, tổ chức các sự kiện quốc tế; tích cực tham gia các sự kiện đối ngoại, hoạt động xúc tiến thương mại - đầu tư - du lịch trong và ngoài nước, các diễn đàn đa phương trong khu vực và toàn cầu.

- Vận động, thu hút viện trợ phát triển từ các đối tác phát triển, các Quỹ đầu tư, tổ chức và tập đoàn kinh tế, tài chính quốc tế tiềm năng; thu hút kiều bào có trình độ và nguồn vốn tham gia, đầu tư vào các dự án phát triển của thành phố, đặc biệt trong các lĩnh vực như phát triển đô thị xanh, thông minh, cải thiện kết cấu cơ sở hạ tầng, giao thông, giáo dục, văn hóa, du lịch.

b) Đẩy mạnh hợp tác, tăng cường liên kết vùng tạo sự thống nhất và sức mạnh tổng hợp về phát triển kinh tế - xã hội, quốc phòng, an ninh cho Thủ đô Hà Nội, cho các địa phương liên kết và cả nước

- Phát huy vai trò đầu tàu dẫn dắt, lan toả của Thủ đô, liên kết các địa phương trong vùng Thủ đô, vùng đồng bằng sông Hồng, vùng kinh tế trọng điểm Bắc Bộ, vùng trung du và miền núi phía Bắc, vùng Bắc Trung Bộ để phân công, hợp tác giữa các địa phương, hình thành chuỗi đô thị, khu công nghiệp, cụm liên kết liên ngành giữa các địa phương, khai thác các hành lang kinh tế, thúc đẩy phát triển kinh tế của các địa phương và cả vùng.

- Đẩy mạnh các hoạt động phối hợp theo Nghị định số 91/2021/NĐ-CP ngày 21 tháng 10 năm 2021 của Chính phủ quy định cơ chế phối hợp giữa các tỉnh, thành phố trong vùng Thủ đô để thi hành các quy định của pháp luật về Thủ đô. Các địa phương trong vùng cùng với Hà Nội chủ động xây dựng các chương trình, kế hoạch hợp tác, liên kết mang lại hiệu quả cao, tạo sức lan tỏa và khai thác được tiềm năng, thế mạnh của các địa phương trong vùng.

- Phối hợp với các địa phương liên quan rà soát, đề xuất sửa đổi, bổ sung các quy định pháp luật, các cơ chế, chính sách tạo nguồn lực đầu tư đồng bộ hệ thống hạ tầng liên vùng, nhất là hạ tầng giao thông liên vùng Thủ đô, cũng như phối hợp giải quyết vấn đề ô nhiễm môi trường của lưu vực sông Nhuệ, sông Đáy và hệ thống sông Bắc Hưng Hải.

7. Tăng cường xây dựng, chỉnh đốn Đảng và hệ thống chính trị trong sạch, vững mạnh

- Ủy ban nhân dân thành phố Hà Nội chủ động tổ chức học tập, quán triệt, thực hiện tốt các Nghị quyết, Chỉ thị, Kết luận của Trung ương, Bộ Chính trị, Ban Bí thư về công tác xây dựng Đảng, xây dựng hệ thống chính trị, xây dựng Đảng bộ thành phố Hà Nội thật sự trong sạch, vững mạnh.

- Nâng cao chất lượng hiệu quả công tác cải cách hành chính, tập trung chỉ đạo, dành nguồn lực để cải cách thủ tục hành chính, hiện đại hóa hành chính; giảm thủ tục, giảm thời gian và chi phí ở tất cả các lĩnh vực quản lý nhà nước, nhất là các thủ tục liên quan đến người dân và doanh nghiệp; đẩy mạnh ứng dụng công nghệ thông tin trong hoạt động quản lý nhà nước; nâng cao và tiếp tục duy trì ổn định thứ hạng Chỉ số cải cách hành chính (Par Index), chỉ số năng lực cạnh tranh cấp tỉnh (PCI) của thành phố trong tốp đầu các tỉnh, thành phố cả nước.

- Nghiên cứu xây dựng tổ chức bộ máy chính quyền Thủ đô theo hướng tinh gọn, chuyên nghiệp, liên thông, hiệu lực, hiệu quả.

- Tổ chức tốt công tác tiếp dân, xử lý đơn, giải quyết khiếu nại, tố cáo; phòng, chống tham nhũng, tiêu cực; phấn đấu không để xảy ra tình trạng khiếu kiện đông người, vượt cấp, kéo dài phát sinh. Thường xuyên lắng nghe, tiếp thu, giải trình ý kiến phản ánh của nhân dân; theo dõi, đôn đốc tiến độ giải quyết các vụ việc khiếu nại, tố cáo phức tạp, đông người, kéo dài. Tăng cường công tác thanh tra, xử lý sau thanh tra, thanh tra trách nhiệm thủ trưởng của các cấp, các ngành trong các lĩnh vực: tiếp dân, xử lý đơn; giải quyết khiếu nại, tố cáo; phòng, chống tham nhũng; quản lý nhà nước về tài chính, đất đai, tài nguyên, môi trường, y tế, giáo dục; công tác thực hiện tiết kiệm, chống lãng phí...

8. Hoàn thiện hệ thống pháp luật về Thủ đô với cơ chế, chính sách phù hợp, đáp ứng yêu cầu phát triển Thủ đô trong giai đoạn mới

- Khẩn trương tổng kết việc thi hành Luật Thủ đô kết hợp với rà soát, hoàn thiện hệ thống pháp luật với các cơ chế, chính sách đặc thù vượt trội cho Thủ đô để đề xuất bổ sung, sửa đổi Luật Thủ đô theo hướng toàn diện hơn, tăng cường phân cấp, phân quyền cho chính quyền Thủ đô Hà Nội thẩm quyền, trách nhiệm giải quyết công việc phù hợp với yêu cầu, nhiệm vụ đặc thù của Thủ đô, trọng tâm là các lĩnh vực đầu tư, tài chính, quy hoạch, đất đai, quản lý trật tự xây dựng, giao thông, môi trường, dân cư, tổ chức bộ máy, biên chế,... nhằm tạo sự chủ động, tăng tính tự chịu trách nhiệm trong thực hiện nhiệm vụ phát triển kinh tế - xã hội, bảo đảm quốc phòng, an ninh, đối ngoại, trong đó ưu tiên tối đa nguồn lực thực hiện các chương trình, dự án kết nối liên vùng, liên tỉnh, các dự án trọng điểm quốc gia trên địa bàn.

- Sơ kết, tổng kết việc thí điểm tổ chức mô hình chính quyền đô thị tại Nghị quyết số 97/2019/QH14 của Quốc hội để đề xuất hoàn thiện tổ chức, bộ máy chính quyền Thủ đô theo hướng tinh gọn, liên thông, hiệu lực, hiệu quả phù hợp với vai trò, vị trí và yêu cầu phát triển, quản lý Thủ đô trong giai đoạn tới; xây dựng cơ chế tuyển dụng, sử dụng và quản lý công chức, người lao động, tiền lương, thu nhập trong việc thu hút, sử dụng nguồn nhân lực chất lượng cao trong nước và quốc tế phục vụ phát triển Thủ đô.

- Tổng kết việc thí điểm một số cơ chế, chính sách tài chính - ngân sách đặc thù đối với thành phố Hà Nội tại Nghị quyết số 115/2020/QH14 ngày 19/6/2020 của Quốc hội để sửa đổi, bổ sung những cơ chế, chính sách đặc thù, thí điểm vượt trội cần thiết và phân cấp cho chính quyền Thủ đô Hà Nội thẩm quyền trách nhiệm giải quyết công việc phù hợp với yêu cầu, nhiệm vụ đặc thù của Thủ đô trong từng thời kỳ.

- Rà soát, sửa đổi, bổ sung và đề xuất các văn bản quy phạm pháp luật theo thẩm quyền liên quan đến đẩy mạnh cải cách hành chính, cắt giảm, đơn giản hóa các thủ tục hành chính để cải thiện, tạo lập môi trường đầu tư, sản xuất, kinh doanh theo hướng thông thoáng, minh bạch, bình đẳng, tạo điều kiện thuận lợi, tiết giảm chi phí cho doanh nghiệp thuộc mọi thành phần kinh tế đặc biệt là kinh tế tập thể và kinh tế tư nhân có điều kiện thuận lợi tiếp cận với các nguồn lực như mặt bằng, hạ tầng, vốn, thông tin, các chính sách ưu đãi,...

- Đẩy mạnh công tác đối ngoại, hội nhập quốc tế; chủ động thực hiện nghiêm túc, đầy đủ và hiệu quả các cam kết và nghĩa vụ khác của Việt Nam khi tham gia thực hiện các Hiệp định thương mại tự do, đặc biệt là các Hiệp định thương mại tự do thế hệ mới. Rà soát, sửa đổi bổ sung và đề xuất các văn bản quy phạm pháp luật trình cấp thẩm quyền ban hành theo đúng lộ trình đã quy định của các Hiệp định; đồng thời, phân tích, dự báo diễn biến, tình hình của chiến tranh thương mại, cạnh tranh giữa các nước lớn, chủ nghĩa bảo hộ mậu dịch đang có chiều hướng gia tăng, tận dụng triệt để các cơ hội mang lại, hạn chế tối đa khó khăn thách thức.

- Tổ chức rà soát, xây dựng và hoàn thiện khung khổ pháp lý cho các loại hình kinh doanh mới xuất hiện trong nền kinh tế số, xã hội số và các mô hình kinh tế mới gắn với chuyển dịch cơ cấu lao động, trong xu thế phát triển của cuộc cách mạng công nghiệp theo nguyên tắc thị trường.

- Xây dựng cơ chế, chính sách huy động tối đa mọi nguồn lực để thu hút nguồn vốn đầu tư vào phát triển các chương trình mục tiêu, dự án trọng điểm, đặc biệt là các dự án kết cấu hạ tầng kinh tế - xã hội, hạ tầng liên kết vùng, ưu tiên áp dụng hình thức đầu tư theo phương thức đối tác công tư (PPP).

- Xây dựng cơ chế, chính sách ưu đãi thu hút nguồn lực xã hội đầu tư xây dựng phát triển giáo dục, đào tạo, khuyến khích các loại hình liên kết đào tạo trong và ngoài nước; xây dựng các mạng lưới cơ sở khám, chữa bệnh chất lượng cao, hiện đại, các cơ sở nghiên cứu phát triển và chuyển giao công nghệ y tế, khuyến khích các loại hình liên kết giữa các cơ sở y tế công với y tế tư nhân và đầu tư nước ngoài; xây dựng các cơ sở giáo dục nghề nghiệp, cơ sở cai nghiện ma túy, cơ sở trợ giúp xã hội, nhà ở, thiết chế văn hóa cho công nhân lao động.

- Xây dựng các cơ chế, chính sách hỗ trợ ưu đãi nhằm khuyến khích người dân, doanh nghiệp và các cơ chế hợp tác giữa Nhà nước và tư nhân đối với việc cải tạo, trùng tu bảo tồn phát huy các công trình kiến trúc có giá trị văn hóa, lịch sử (nhà cổ, biệt thự cũ và các công trình kiến trúc có giá trị,...). Thành lập Quỹ bảo tồn khu vực nội đô lịch sử để thực hiện cải tạo, chỉnh trang, tái thiết đô thị, gắn với bảo tồn, phát huy giá trị văn hóa khu vực nội đô lịch sử để thực hiện cải tạo, chỉnh trang, tái thiết đô thị gắn với bảo tồn, phát huy giá trị văn hóa khu vực nội đô lịch sử.

- Xây dựng chính sách ứng dụng công nghệ số để xây dựng chính quyền, phát triển chính quyền có mô hình hoạt động dựa trên dữ liệu và công nghệ số, để có khả năng cung cấp dịch vụ chất lượng, nâng cao hiệu quả quản lý kinh tế - xã hội của Thủ đô.

III. TỔ CHỨC THỰC HIỆN

1. Đối với các bộ, ngành, cơ quan thuộc Chính phủ

Các bộ, ngành, cơ quan thuộc Chính phủ căn cứ chức năng nhiệm vụ được giao chủ động phối hợp thường xuyên với thành phố Hà Nội, có cơ chế điều hành tập trung, cụ thể để tăng cường phối hợp triển khai các nội dung Nghị quyết, trong đó tập trung vào một số nội dung cụ thể sau:

- Xây dựng và ban hành kế hoạch thực hiện Nghị quyết số 15-NQ/TW ngày 05 tháng 5 năm 2022 và Nghị quyết này của Chính phủ hoặc lồng ghép vào các chương trình, kế hoạch hành động khác của bộ, ngành.

- Căn cứ Phụ lục kèm theo, giao nhiệm vụ cụ thể cho các cơ quan chức năng cùng phối hợp, hỗ trợ giúp xây dựng cơ chế, chính sách đặc thù phát triển Thủ đô đảm bảo tiến độ, thời gian hoàn thành và chất lượng theo đúng quy định của pháp luật; tiếp tục thực hiện phân cấp, phân quyền toàn diện hơn gắn với cơ chế kiểm soát quyền lực và trách nhiệm của chính quyền địa phương cho Hà Nội.

- Tăng cường theo dõi, đôn đốc, kiểm điểm về tình hình triển khai thực hiện Nghị quyết số 15-NQ/TW ngày 05 tháng 5 năm 2022 của Bộ Chính trị và Nghị quyết này của Chính phủ; định kỳ hàng năm báo cáo kết quả thực hiện gửi Bộ Kế hoạch và Đầu tư để tổng hợp báo cáo Chính phủ.

- Các bộ, ngành khác có liên quan chủ động phối hợp với Ủy ban nhân dân thành phố Hà Nội và các bộ, ngành, địa phương liên quan để triển khai thực hiện Nghị quyết 15-NQ/TW ngày 05 tháng 5 năm 2022 và Nghị quyết này của Chính phủ.

2. Đối với Thủ đô Hà Nội

- Tập trung khẩn trương chỉ đạo các sở, ban, ngành rà soát, kiểm tra, bổ sung kế hoạch theo chức năng, nhiệm vụ để xây dựng các chương trình, cụ thể hóa các mục tiêu, chỉ tiêu, nhiệm vụ, giải pháp của Nghị quyết số 15-NQ/TW ngày 05 tháng 5 năm 2022 của Bộ Chính trị, trong đó trọng tâm xây dựng Thủ đô Hà Nội đi đầu cả nước hoàn thành công nghiệp hóa, hiện đại hóa, trở thành thành phố “Xanh - Văn hiến - Thông minh - Hiện đại”, phát triển thông minh, năng động, hiệu quả, vì con người; trở thành trung tâm - động lực thúc đẩy và dẫn dắt phát triển vùng và cả nước; có sức cạnh tranh khu vực và thế giới, sánh vai thủ đô các nước phát triển cao trong khu vực.

- Chủ động phát triển quan hệ liên kết, trao đổi, hợp tác với các tỉnh, thành phố trong cả nước và các tỉnh, thành phố trong vùng kinh tế trọng điểm Bắc Bộ, vùng đồng bằng sông Hồng, vùng Thủ đô, vùng Trung du và miền núi phía Bắc, vùng Bắc Trung Bộ, đặc biệt là tam giác phát triển Hà Nội - Hải Phòng - Quảng Ninh bền vững trên các lĩnh vực, khai thác, phát huy được tiềm năng, lợi thế của nhau cùng phát triển.

- Định kỳ hàng năm, đánh giá tình hình thực hiện Nghị quyết này của Chính phủ, báo cáo Thủ tướng Chính phủ, đồng gửi Bộ Kế hoạch và Đầu tư để theo dõi và tổng hợp theo quy định.

3. Đối với các tỉnh, thành phố trực thuộc trung ương

Các tỉnh, thành phố trong cả nước, nhất là các tỉnh, thành phố trong vùng kinh tế trọng điểm Bắc Bộ, vùng đồng bằng sông Hồng, vùng Thủ đô, vùng trung du và miền núi phía Bắc, vùng Bắc Trung Bộ chủ động phát triển quan hệ liên kết, hợp tác với thành phố Hà Nội trên các lĩnh vực, tạo sự gắn bó và sức mạnh chung để cùng khai thác các tiềm năng, lợi thế của nhau vì sự phát triển chung.

4. Trong quá trình tổ chức thực hiện, nếu thấy cần sửa đổi, bổ sung những nội dung cụ thể thuộc Chương trình hành động, các bộ, cơ quan thuộc Chính phủ và Ủy ban nhân dân thành phố Hà Nội kịp thời đề xuất các nội dung điều chỉnh để phù hợp với tình hình thực tiễn, gửi Bộ Kế hoạch và Đầu tư để tổng hợp, báo cáo Thủ tướng Chính phủ.

5. Đề nghị các cơ quan của Đảng, Quốc hội, Mặt trận Tổ quốc Việt Nam, các tổ chức chính trị - xã hội phối hợp chặt chẽ với cơ quan hành chính nhà nước các cấp, tăng cường giám sát thực thi công vụ, phản biện xã hội và đóng góp ý kiến, góp phần tạo đồng thuận trong công tác tổ chức triển khai thực hiện Chương trình hành động của Chính phủ ban hành kèm theo Nghị quyết này.

6. Bộ Thông tin và Truyền thông chủ trì, phối hợp chặt chẽ, quyết liệt với Ban Tuyên giáo Trung ương, các cơ quan thông tấn, báo chí, các bộ, ngành trung ương và địa phương tổ chức phổ biến, tuyên truyền rộng rãi Nghị quyết này./.

PHỤ LỤC

NHIỆM VỤ, DỰ ÁN CỤ THỂ CHƯƠNG TRÌNH HÀNH ĐỘNG CỦA CHÍNH PHỦ TRIỂN KHAI THỰC HIỆN NGHỊ QUYẾT 15-NQ/TW CỦA BỘ CHÍNH TRỊ
(Kèm theo Nghị quyết 12/NQ-CP ngày 07 tháng 02 năm 2023 của Chính phủ)

TT | Nhiệm vụ, đề án, dự án | Cơ quan chủ trì thực hiện | Cơ quan phối hợp thực hiện | Thời gian trình | Cấp trình | Sản phẩm

I | Hoàn thiện hệ thống pháp luật về Thủ đô | Hoàn thiện hệ thống pháp luật về Thủ đô | Hoàn thiện hệ thống pháp luật về Thủ đô | Hoàn thiện hệ thống pháp luật về Thủ đô | Hoàn thiện hệ thống pháp luật về Thủ đô | Hoàn thiện hệ thống pháp luật về Thủ đô

1 | Báo cáo tổng kết thi hành Luật Thủ đô | Bộ Tư pháp | Các bộ, ngành, UBND TP Hà Nội và các đơn vị liên quan | 2022 | Chính phủ | Báo cáo

2 | Hồ sơ đề nghị xây dựng Luật Thủ đô (sửa đổi) | Bộ Tư pháp | Các bộ, ngành, UBND TP Hà Nội và các đơn vị liên quan | 2022 | Chính phủ | Hồ sơ đề nghị

3 | Dự án Luật Thủ đô (sửa đổi) | Bộ Tư pháp | Các bộ, ngành, UBND TP Hà Nội và các đơn vị liên quan | 2024 | Chính phủ, Quốc hội | Dự án Luật

4 | Báo cáo sơ kết thí điểm tổ chức mô hình chính quyền đô thị tại thành phố Hà Nội theo Nghị quyết số 97/2019/QH14 ngày 27/11/2019 của Quốc hội khóa XIV | Bộ Nội vụ | UBND TP Hà Nội và các đơn vị liên quan | 2023 | Chính phủ | Báo cáo

5 | Báo cáo tổng kết thí điểm cơ chế, chính sách tài chính - ngân sách đặc thù đối với thành phố Hà Nội theo Nghị quyết số 115/2020/QH14 ngày 19/6/2020 của Quốc hội khóa XIV | Bộ Tài chính | UBND TP Hà Nội và các đơn vị liên quan | 2025 | Chính phủ | Báo cáo

II | Phát triển văn hóa, giáo dục, KHCN, y tế; Bảo đảm an sinh, phúc lợi xã hội | Phát triển văn hóa, giáo dục, KHCN, y tế; Bảo đảm an sinh, phúc lợi xã hội | Phát triển văn hóa, giáo dục, KHCN, y tế; Bảo đảm an sinh, phúc lợi xã hội | Phát triển văn hóa, giáo dục, KHCN, y tế; Bảo đảm an sinh, phúc lợi xã hội | Phát triển văn hóa, giáo dục, KHCN, y tế; Bảo đảm an sinh, phúc lợi xã hội | Phát triển văn hóa, giáo dục, KHCN, y tế; Bảo đảm an sinh, phúc lợi xã hội

1 | Đề án cơ cấu lại hệ thống các cơ sở nghiên cứu khoa học và công nghệ công lập, trong đó: Xây dựng Hà Nội trở thành Trung tâm đổi mới sáng tạo, nghiên cứu, phát triển, chuyển giao công nghệ hàng đầu của cả nước và khu vực; Hoàn thành xây dựng Khu công nghệ cao Hoà Lạc và các cơ sở của Trung tâm Đổi mới sáng tạo quốc gia tại Hà Nội | Bộ Khoa học và Công nghệ | Các cơ quan liên quan và UBND TP Hà Nội | 2023 | Thủ tướng Chính phủ | Đề án

2 | Đề án phát triển một số viện nghiên cứu hàng đầu khu vực, trung tâm đổi mới sáng tạo, nghiên cứu khoa học, chuyển giao và phát triển công nghệ tại các viện nghiên cứu, trường đại học trên địa bàn Thủ đô | Bộ Khoa học và Công nghệ | Các cơ quan liên quan và UBND TP Hà Nội | 2023 | Thủ tướng Chính phủ | Đề án

3 | Đề án phát triển, nâng cao chất lượng các trường đại học, trong đó phấn đấu đến năm 2025 trên địa bàn Thủ đô có ít nhất 01 trường đại học và đến năm 2030 có ít nhất 02 trường đại học nằm trong TOP 100 trường đại học hàng đầu Châu Á | Bộ Giáo dục và Đào tạo | Các cơ quan liên quan và UBND TP Hà Nội | 2023 | Thủ tướng Chính phủ | Đề án

4 | Đầu tư xây dựng một số cơ sở nghiên cứu và chuyển giao công nghệ y, dược trên địa bàn Thủ đô | Bộ Y tế | Các bộ, ngành, các đơn vị liên quan | 2022-2030 | Thủ tướng Chính phủ | Báo cáo

5 | Đề án xây dựng không gian sáng tạo, Trung tâm công nghiệp văn hóa hai bên bờ sông Hồng | Bộ Văn hóa, Thể thao và Du lịch | Các cơ quan liên quan và UBND TP Hà Nội | 2024-2026 | Thủ tướng Chính phủ | Đề án

III | Công tác quy hoạch, xây dựng kết cấu hạ tầng, phát triển và quản lý đô thị, khai thác, sử dụng tài nguyên, bảo vệ môi trường | Công tác quy hoạch, xây dựng kết cấu hạ tầng, phát triển và quản lý đô thị, khai thác, sử dụng tài nguyên, bảo vệ môi trường | Công tác quy hoạch, xây dựng kết cấu hạ tầng, phát triển và quản lý đô thị, khai thác, sử dụng tài nguyên, bảo vệ môi trường | Công tác quy hoạch, xây dựng kết cấu hạ tầng, phát triển và quản lý đô thị, khai thác, sử dụng tài nguyên, bảo vệ môi trường | Công tác quy hoạch, xây dựng kết cấu hạ tầng, phát triển và quản lý đô thị, khai thác, sử dụng tài nguyên, bảo vệ môi trường | Công tác quy hoạch, xây dựng kết cấu hạ tầng, phát triển và quản lý đô thị, khai thác, sử dụng tài nguyên, bảo vệ môi trường

1 | Quy hoạch Thủ đô Hà Nội thời kỳ 2021 - 2030, tầm nhìn đến năm 2050 | UBND thành phố Hà Nội | Bộ Kế hoạch và Đầu tư và các cơ quan liên quan | Quý II/2023 | Thủ tướng Chính phủ | Quyết định của Thủ tướng Chính phủ

2 | Kế hoạch di dời các cơ sở giáo dục đại học ra khỏi trung tâm Thủ đô Hà Nội theo quy hoạch; đảm bảo sử dụng tối thiểu 50% quỹ đất sau di dời sử dụng vào mục đích xây dựng công trình công cộng, phúc lợi xã hội | Bộ Giáo dục và Đào tạo | Các bộ ngành, UBND TP Hà Nội, các đơn vị liên quan | 2023 | Thủ tướng Chính phủ | Quyết định của Thủ tướng Chính phủ

3 | Kế hoạch di dời các bệnh viện ra khỏi trung tâm Thủ đô Hà Nội theo quy hoạch; đảm bảo sử dụng tối thiểu 50% quỹ đất sau di dời sử dụng vào mục đích xây dựng công trình công cộng, phúc lợi xã hội | Bộ Y tế | Các bộ ngành, UBND TP Hà Nội, các đơn vị liên quan | 2023 | Thủ tướng Chính phủ | Quyết định của Thủ tướng Chính phủ

4 | Kế hoạch di dời các trụ sở của bộ, ban, ngành trung ương ra khỏi trung tâm Thủ đô Hà Nội theo quy hoạch; đảm bảo sử dụng tối thiểu 50% quỹ đất sau di dời sử dụng vào mục đích xây dựng công trình công cộng, phúc lợi xã hội | Bộ Xây dựng, Bộ Tài nguyên và Môi trường | Các bộ ngành, UBND TP Hà Nội, các đơn vị liên quan | 2023 | Thủ tướng Chính phủ | Quyết định của Thủ tướng Chính phủ

5 | Nghiên cứu, xác định vị trí và các chỉ tiêu quy hoạch Cảng hàng không quốc tế thứ hai đáp ứng yêu cầu phát triển vùng Thủ đô và khu vực phía Bắc | Bộ Giao thông Vận tải | Các Bộ: Quốc phòng, Xây dựng, Tài nguyên và Môi trường, Nông nghiệp và PTNT và các đơn vị liên quan | 2026-2030 | Thủ tướng Chính phủ | Báo cáo

6 | Thẩm định các đồ án quy hoạch chuyên ngành hạ tầng kỹ thuật Thủ đô Hà Nội đến năm 2030, tầm nhìn đến năm 2050 | Bộ Xây dựng | Các cơ quan liên quan và UBND TP Hà Nội | 2022-2023 | Thủ tướng Chính phủ | Báo cáo

7 | Thẩm định nhiệm vụ và đồ án điều chỉnh tổng thể Quy hoạch chung xây dựng Thủ đô Hà Nội đến năm 2030 và tầm nhìn đến năm 2050 | Bộ Xây dựng | Các cơ quan liên quan và UBND TP Hà Nội | 2022-2024 | Thủ tướng Chính phủ | Báo cáo

IV | Liên kết phát triển vùng | Liên kết phát triển vùng | Liên kết phát triển vùng | Liên kết phát triển vùng | Liên kết phát triển vùng | Liên kết phát triển vùng

1 | Thành lập và ban hành quy chế hoạt động của Hội đồng điều phối vùng Thủ đô | Bộ Kế hoạch và Đầu tư | Các bộ ngành và địa phương liên quan | 2022 | Thủ tướng Chính phủ | Quyết định của Thủ tướng Chính phủ

2 | Báo cáo tổng kết huy động và sử dụng các nguồn lực cho phát triển kết cấu hạ tầng, nhất là dưới hình thức PPP gắn với đẩy mạnh phân cấp, phân quyền cho chính quyền địa phương, trong đó có Thủ đô Hà Nội | Bộ Kế hoạch và Đầu tư | Các bộ ngành, UBND TP Hà Nội, các đơn vị liên quan | 2023 | Thủ tướng Chính phủ | Báo cáo

[1] Nghị quyết Đại hội đại biểu lần thứ XVII (nhiệm kỳ 2020-2025) Đảng bộ thành phố Hà Nội."""
    }
    send_result_validate(data)
