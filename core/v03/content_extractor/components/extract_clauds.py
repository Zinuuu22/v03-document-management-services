import re
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.content_extractor.utils.regex_pattern import EXTRACT_CLAUDS_CLAUD_PATTERN_1, \
                                                        EXTRACT_CLAUDS_CLAUD_PATTERN_2, \
                                                        EXTRACT_CLAUDS_POINT_PATTERN, \
                                                        EXTRACT_CLAUDS_REFERENCE_PATTERN, \
                                                        EXTRACT_CLAUDS_REFERENCE_SAMPLE_PATTERN


def __replace_nested_quotes(text):    
    '''
        replace nested quotes to clean data and remove noise
    '''
    
    text = re.sub(r' {2,}', ' ', text)    
    text = text.replace('"\n', '”\n').replace('\n "', '\n “').replace('\n"', '\n“')        
    stack = []
    text_list = list(text)
    for i, char in enumerate(text_list):
        if char == '“':
            if len(stack) >= 1:
                text_list[i] = "'"
            stack.append(char)
            
        if char == '”':
            if len(stack) > 1:
                text_list[i] = "'"
            if len(stack) != 0:
                stack.pop()
    return ''.join(text_list)


def __extract_refer(content):        
    '''
        extract reference clauds/points from input content
    '''
    cleaned_content = __replace_nested_quotes(content)    
    results = re.findall(EXTRACT_CLAUDS_REFERENCE_PATTERN, cleaned_content, re.DOTALL)    
    return cleaned_content, results


def __get_content_by_restore_refer(text, references):
    '''
        convert REFERENCE_{index} mask to true content of this reference
    '''
    matches = re.findall(EXTRACT_CLAUDS_REFERENCE_SAMPLE_PATTERN, text)
    for index in matches:
        text = text.replace(f'[REFERENCE_{index}]', references[int(index)])
    return text


def extract_clauds(segment_content):    
    output = {
        "clean_content": None,
        "description": None,
        'points': None        
    }    
    
    # Extract Referenced Clauds from Segments to remove noise
    clean_segment_content, references = __extract_refer(segment_content)    
    if len(references):
        for i, reference in enumerate(references):
            if len(reference) > 5:
                clean_segment_content = clean_segment_content.replace(reference, f'[REFERENCE_{i}]')                                 
    else:
        output['clean_content'] = clean_segment_content  

    # Check for subsections (1.1, 1.2, etc.)
    has_subsections = bool(re.search(r'(?:(?<=\n)|^)\s*\d+\.\d+\s', clean_segment_content))
    if has_subsections:
        claud_pattern = EXTRACT_CLAUDS_CLAUD_PATTERN_2
    else:
        claud_pattern = EXTRACT_CLAUDS_CLAUD_PATTERN_1
    
    # Extract clauds based on patterns
    clauds = re.findall(claud_pattern, clean_segment_content, re.DOTALL)
    output_clauds = []
    if clauds:    
        for claud in clauds:            
            output_points = []            
            points = re.findall(EXTRACT_CLAUDS_POINT_PATTERN, claud, re.DOTALL)
            points = [point.strip() for point in points]
            for point in points:
                output_point = __get_content_by_restore_refer(point, references)    
                output_points.append(output_point)
            
            output_claud = __get_content_by_restore_refer(claud, references)          
            output_clauds.append({'claud': output_claud, 'points': output_points})                            
        description = clean_segment_content.split('1.')[0].strip()
    else:
        description = clean_segment_content
            
    output['clean_content'] = clean_segment_content
    output['description'] = description        
    output['clauds'] = output_clauds   
    return output


if __name__ == '__main__':
    segment_content = f"""1. Sửa đổi, bổ sung khoản 4 Điều 22 như sau:
“4. Sĩ quan được xét thăng cấp bậc hàm từ Đại tá lên Thiếu tướng phải còn ít nhất đủ 03 năm công tác; trường hợp không còn đủ 03 năm công tác khi có yêu cầu do Chủ tịch nước quyết định.”.
2. Bổ sung khoản 4 vào sau khoản 3 Điều 23 như sau:
“4. Chính phủ quy định cụ thể tiêu chí, tiêu chuẩn quy định tại khoản 1 Điều này để xét thăng cấp bậc hàm cấp tướng trước thời hạn. Bộ trưởng Bộ Công an quy định cụ thể tiêu chí, tiêu chuẩn quy định tại khoản 1 và khoản 2 Điều này để xét thăng cấp bậc hàm trước thời hạn và thăng cấp bậc hàm vượt bậc từ Đại tá trở xuống.”.
3. Sửa đổi, bổ sung một số điểm, khoản của Điều 25 như sau:
a) Sửa đổi, bổ sung điểm b khoản 1 như sau:
“b) Thượng tướng, số lượng không quá 07 bao gồm:
Thứ trưởng Bộ Công an. Số lượng không quá 06;
Sĩ quan Công an nhân dân biệt phái được bầu giữ chức vụ Chủ nhiệm Ủy ban Quốc phòng và An ninh của Quốc hội;”;
b) Sửa đổi, bổ sung điểm d khoản 1 như sau:
“d) Thiếu tướng, số lượng không quá 162 bao gồm:
Cục trưởng của đơn vị trực thuộc Bộ Công an và chức vụ, chức danh tương đương, trừ trường hợp quy định tại điểm c khoản 1 Điều này;
Giám đốc Công an tỉnh, thành phố trực thuộc trung ương ở địa phương được phân loại đơn vị hành chính cấp tỉnh loại I và là địa bàn trọng điểm, phức tạp về an ninh, trật tự, diện tích rộng, dân số đông. Số lượng không quá 11;
Phó Chủ nhiệm Ủy ban Kiểm tra Đảng ủy Công an Trung ương. Số lượng không quá 03;
Phó Cục trưởng, Phó Tư lệnh và tương đương của đơn vị trực thuộc Bộ Công an quy định tại điểm c khoản 1 Điều này. Số lượng: 17 đơn vị mỗi đơn vị không quá 04, các đơn vị còn lại mỗi đơn vị không quá 03;
Phó Cục trưởng và tương đương của đơn vị trực thuộc Bộ Công an quy định tại điểm này. Số lượng: 02 đơn vị mỗi đơn vị 01;
Phó Giám đốc Công an thành phố Hà Nội, Phó Giám đốc Công an Thành phố Hồ Chí Minh. Số lượng mỗi đơn vị không quá 03;
Sĩ quan Công an nhân dân biệt phái được phê chuẩn giữ chức vụ Ủy viên Thường trực Ủy ban Quốc phòng và An ninh của Quốc hội hoặc được bổ nhiệm chức vụ Tổng cục trưởng hoặc tương đương;”;
c) Sửa đổi, bổ sung điểm e khoản 1 như sau:
“e) Thượng tá: Trưởng phòng và tương đương; Trưởng Công an huyện, quận, thị xã, thành phố thuộc tỉnh, thành phố trực thuộc trung ương; Trung đoàn trưởng, trừ trường hợp quy định tại khoản 4 Điều này;”;
d) Sửa đổi, bổ sung khoản 2 như sau:
“2. Ủy ban Thường vụ Quốc hội quy định cụ thể vị trí có cấp bậc hàm cao nhất là Trung tướng, Thiếu tướng chưa được quy định cụ thể trong Luật này; quy định cấp bậc hàm cấp tướng đối với chức vụ, chức danh của sĩ quan ở đơn vị thành lập mới nhưng không vượt quá số lượng tối đa vị trí cấp tướng theo quyết định của cấp có thẩm quyền.”;
đ) Sửa đổi, bổ sung khoản 4 như sau:
“4. Trưởng phòng và tương đương ở đơn vị trực thuộc Bộ Công an có chức năng, nhiệm vụ trực tiếp chiến đấu, tham mưu, nghiên cứu, hướng dẫn chuyên môn, nghiệp vụ toàn lực lượng; Trung đoàn trưởng ở đơn vị trực thuộc Bộ Công an, Công an thành phố Hà Nội và Công an Thành phố Hồ Chí Minh; Trưởng phòng tham mưu, nghiệp vụ, tổ chức cán bộ, công tác đảng và công tác chính trị, Trưởng Công an quận, thành phố thuộc Công an thành phố Hà Nội và Công an Thành phố Hồ Chí Minh có cấp bậc hàm cao hơn 01 bậc quy định tại điểm e khoản 1 Điều này.”.
4. Sửa đổi, bổ sung khoản 2 Điều 29 như sau:
“2. Sĩ quan Công an nhân dân biệt phái được hưởng chế độ, chính sách như sĩ quan đang công tác trong Công an nhân dân. Việc phong, thăng, giáng, tước cấp bậc hàm đối với sĩ quan biệt phái thực hiện như đối với sĩ quan đang công tác trong Công an nhân dân, trừ sĩ quan biệt phái quy định tại các điểm b, c và d khoản 1, khoản 3 Điều 25 và khoản 1 Điều 27 của Luật này.
Sĩ quan Công an nhân dân khi kết thúc nhiệm vụ biệt phái được xem xét, bố trí chức vụ tương đương chức vụ biệt phái; được giữ nguyên quyền lợi của chức vụ biệt phái.”.
5. Sửa đổi, bổ sung một số khoản của Điều 30 như sau:
a) Sửa đổi, bổ sung khoản 1 và bổ sung khoản 1a vào sau khoản 1 như sau:
“1. Hạn tuổi phục vụ cao nhất của hạ sĩ quan, sĩ quan Công an nhân dân quy định như sau:
a) Hạ sĩ quan: 47;
b) Cấp úy: 55;
c) Thiếu tá, Trung tá: nam 57, nữ 55;
d) Thượng tá: nam 60, nữ 58;
đ) Đại tá: nam 62, nữ 60;
e) Cấp tướng: nam 62, nữ 60.
1a. Hạn tuổi phục vụ cao nhất của nam sĩ quan quy định tại điểm đ và điểm e, nữ sĩ quan quy định tại điểm d và điểm đ khoản 1 Điều này thực hiện theo lộ trình về tuổi nghỉ hưu đối với người lao động như quy định của Bộ luật Lao động.
Chính phủ quy định chi tiết khoản này.”;
b) Sửa đổi, bổ sung khoản 3 và khoản 4 như sau:
“3. Trường hợp đơn vị công an có nhu cầu, sĩ quan quy định tại các điểm b, c và d khoản 1 Điều này nếu có đủ phẩm chất, giỏi về chuyên môn, nghiệp vụ, có sức khỏe tốt và tự nguyện thì có thể được kéo dài tuổi phục vụ theo quy định của Bộ trưởng Bộ Công an, nhưng không quá 62 đối với nam và 60 đối với nữ.
Trường hợp đặc biệt sĩ quan quy định tại khoản 1 Điều này có thể được kéo dài tuổi phục vụ hơn 62 đối với nam và hơn 60 đối với nữ theo quyết định của cấp có thẩm quyền.
4. Sĩ quan Công an nhân dân là giáo sư, phó giáo sư, tiến sĩ, chuyên gia cao cấp có thể được kéo dài tuổi phục vụ hơn 62 đối với nam và hơn 60 đối với nữ theo quy định của Chính phủ.”.
6. Sửa đổi, bổ sung khoản 2 Điều 42 như sau:
“2. Hạn tuổi phục vụ cao nhất của công nhân công an: nam 62, nữ 60 và thực hiện theo lộ trình về tuổi nghỉ hưu đối với người lao động như quy định của Bộ luật Lao động. Công nhân công an được áp dụng chế độ, chính sách như đối với công nhân quốc phòng.
Chính phủ quy định chi tiết khoản này.”.
"""
    output = extract_clauds(segment_content)
    logger.debug("claud_extraction_output", action="main", claud_count=len(output.get('clauds', [])))
    for claud in output['clauds']:
        points = claud['points']
        for point in points:
            logger.debug("claud_point_extracted", action="main", point_length=len(point))
