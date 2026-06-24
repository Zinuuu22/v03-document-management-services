from email import message
import sys
import json
import structlog
import os
from typing import Tuple, Dict, List, Set
from concurrent.futures import ThreadPoolExecutor
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from logs.logger_conf import setup_logging
from core.common.llms import LLMs
from constants import LLMsConfigAnalyze

setup_logging()
logger = structlog.get_logger()


#Call LLMs
LLms = LLMs(llms_config=LLMsConfigAnalyze)

# Load the prompt from JSON file once at module level
JSON_FILE_PATH = f"{PROJECT_ROOT}/core/v03/analyze/prompts.json"
try:
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        EXTRACT_ANALYZE_PROMPT = json.load(f)
except Exception as e:
    logger.error("load_prompt_failed", **{"error.code": "SYS", "error.message": str(e)}, json_file=JSON_FILE_PATH, exc_info=True)

def preprocess_segment(segment: str) -> str:
    """Preprocess a segment by removing newlines and stripping whitespace."""
    return segment.replace("\n", " ").strip()

def validate_segments(segment_1: str, segment_2: str) -> Tuple[bool, Dict[str, List[Dict]]]:
    """Validate that segments are not empty; return error output if invalid."""
    if not segment_1 or not segment_2:
        error = "One or both segments are empty."
        return False, {
            'conflict': [{'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}}],
            'cross': [{'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}}],
            'duplicate': [{'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}}]
        }
    return True, {}

def get_common_categories(category_1: List[str], category_2: List[str]) -> Tuple[Set[str], Dict[str, List[Dict]]]:
    """Find common categories between two lists; return error output if none."""
    common_categories = set(category_1).intersection(set(category_2))
    if not common_categories:
        error = "No common categories between category_1 and category_2."
        return set(), {
            'conflict': [{'segment_1': "", 'segment_2': "", 'category': None, 'result': False, 'detail': error, 'answer': {}}],
            'cross': [{'segment_1': "", 'segment_2': "", 'category': None, 'result': False, 'detail': error, 'answer': {}}],
            'duplicate': [{'segment_1': "", 'segment_2': "", 'category': None, 'result': False, 'detail': error, 'answer': {}}]
        }
    return common_categories, {}


def generate_answer(segment_1, category_1, segment_1_id, segment_2, category_2, segment_2_id):
    """Generate answer by analyzing segments based on common categories from prompt_v1.json."""
    
    output = {
        'conflict': [],
        'cross': [],
        'duplicate': []
    }
    
    # try:
    if not segment_1 or not segment_2:
        error = "Đoạn điều luật segment_1 hoặc segment_2 trống."            
        output['conflict'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
        output['cross'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
        output['duplicate'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
        return output
    
    pp_segment_1 = segment_1.replace("\n", " ").strip()
    pp_segment_2 = segment_2.replace("\n", " ").strip()

    # Kiểm tra các danh mục chung giữa category_1 và category_2
    category_1 = [c.lower().strip() for c in category_1]
    category_2 = [c.lower().strip() for c in category_2]   
    common_categories = set(category_1).intersection(set(category_2))        
    if not common_categories or len(common_categories) == 0:
        logger.debug("no_common_categories", action="generate_answer")
        error = "Không có danh mục chung giữa category_1 và category_2."
        output['conflict'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
        output['cross'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
        output['duplicate'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
        return output                   
    
    for _category in common_categories:        
        cross_result = False                
        for category, _ in EXTRACT_ANALYZE_PROMPT['cross_types'].items():
            if category.lower().strip() != _category:
                continue                             
            prompt_template = EXTRACT_ANALYZE_PROMPT['cross_types'][category]["prompt"]
            prompt = prompt_template.replace("{segment_1}", pp_segment_1).replace("{segment_2}", pp_segment_2)
            try:
                logger.debug("cross_types_prompt", action="generate_answer", prompt=prompt)
                response = LLms.llms(prompt=prompt)
                
                pp_answer = LLms.llms_post_process(response)
                output['cross'].append({
                    'segment_1': segment_1,
                    'segment_2': segment_2,
                    'category': category,
                    'result': pp_answer.get('result', False) if pp_answer else False,
                    'detail': pp_answer.get('detail', None) if pp_answer else None,
                    'answer': pp_answer,
                    'base_segment_id': segment_1_id,
                    'validate_segment_id': segment_2_id
                })
                cross_result = pp_answer.get('result', False) if pp_answer else False
            except Exception as e:
                logger.error("cross_types_error", action="generate_answer", **{"error.code": "CONT", "error.message": str(e)}, category=category, exc_info=True)
                output['cross'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': category, 'result': False, 'detail': f"Lỗi khi xử lý prompt: {e}", 'answer': {}})

        
        if not cross_result:
            for category in EXTRACT_ANALYZE_PROMPT['conflict_types']:
                if category.lower().strip() != _category:
                    continue                 
                prompt_template = EXTRACT_ANALYZE_PROMPT['conflict_types'][category]["prompt"]
                prompt = prompt_template.replace("{segment_1}", pp_segment_1).replace("{segment_2}", pp_segment_2)
                try:
                    logger.debug("conflict_types_prompt", action="generate_answer", prompt=prompt)                                
                    response = LLms.llms(prompt=prompt)               
                
                    pp_answer = LLms.llms_post_process(response)
                    output['conflict'].append({
                        'segment_1': segment_1,
                        'segment_2': segment_2,
                        'category': category,
                        'result': pp_answer.get('result', False) if pp_answer else False,
                        'detail': pp_answer.get('detail', None) if pp_answer else None,
                        'answer': pp_answer,
                        'base_segment_id': segment_1_id,
                        'validate_segment_id': segment_2_id
                    })
                except Exception as e:
                    logger.error("conflict_types_error", action="generate_answer", **{"error.code": "CONT", "error.message": str(e)}, category=category, exc_info=True)
                    output['conflict'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': category, 'result': False, 'detail': f"Lỗi khi xử lý prompt: {e}", 'answer': {}})

        for category, _ in EXTRACT_ANALYZE_PROMPT['duplicate_types'].items():
            if category.lower().strip() != _category:
                continue                
            prompt_template = EXTRACT_ANALYZE_PROMPT['duplicate_types'][category]["prompt"]
            prompt = prompt_template.replace("{segment_1}", pp_segment_1).replace("{segment_2}", pp_segment_2)
            try:
                logger.debug("duplicate_types_prompt", action="generate_answer", prompt=prompt)                
                response = LLms.llms(prompt=prompt)
                
                pp_answer = LLms.llms_post_process(response)
                output['duplicate'].append({
                    'segment_1': segment_1,
                    'segment_2': segment_2,
                    'category': category,
                    'result': pp_answer.get('result', False) if pp_answer else False,
                    'detail': pp_answer.get('detail', None) if pp_answer else None,
                    'answer': pp_answer,
                    'base_segment_id': segment_1_id,
                    'validate_segment_id': segment_2_id
                })
            except Exception as e:
                logger.error("duplicate_types_error", action="generate_answer", **{"error.code": "CONT", "error.message": str(e)}, category=category, exc_info=True)
                output['duplicate'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': category, 'result': False, 'detail': f"Lỗi khi xử lý prompt: {e}", 'answer': {}})
    return output


def generate_answer_multithread(segment_1, category_1, segment_2, category_2):
    """Generate answer by analyzing segments based on common categories from prompt_v2.json."""    
    output = {
        'conflict': [],
        'cross': [],
        'duplicate': []
    }
    
    try:
        if not segment_1 or not segment_2:
            error = "Đoạn điều luật segment_1 hoặc segment_2 trống."            
            output['conflict'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
            output['cross'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
            output['duplicate'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
            return output
        
        pp_segment_1 = segment_1.replace("\n", " ").strip()
        pp_segment_2 = segment_2.replace("\n", " ").strip()

        
        common_categories = set(category_1).intersection(set(category_2))        
        if not common_categories:
            error = "Không có danh mục chung giữa category_1 và category_2."
            output['conflict'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
            output['cross'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
            output['duplicate'].append({'segment_1': segment_1, 'segment_2': segment_2, 'category': None, 'result': False, 'detail': error, 'answer': {}})
            return output
        
        def process_category(output_key, types_dict, category, segment_1, segment_2):
            result = {
                'segment_1': segment_1,
                'segment_2': segment_2,
                'category': category,
                'result': False,
                'detail': "KHÔNG THÀNH CÔNG",
                'answer': {}
            }
            
            if category in types_dict:
                prompt_template = types_dict[category]["prompt"]
                prompt = prompt_template.replace("{segment_1}", pp_segment_1).replace("{segment_2}", pp_segment_2)
                try:
                    response = LLms.llms(prompt=prompt)
                    pp_answer = LLms.llms_post_process(response)
                    result.update({
                        'result': pp_answer.get('result', False) if pp_answer else False,
                        'detail': pp_answer.get('detail', "Không có phân tích từ LLM." if output_key == 'conflict' else "Không có chi tiết từ LLM.") if pp_answer else "Không có phân tích từ LLM." if output_key == 'conflict' else "Không có chi tiết từ LLM.",
                        'answer': pp_answer
                    })
                except Exception as e:
                    logger.error("process_category_error", action="generate_answer", **{"error.code": "CONT", "error.message": str(e)}, output_key=output_key, category=category, exc_info=True)
                    result['detail'] = f"Lỗi khi xử lý prompt: {e}"
            
            return (output_key, result)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            for category in common_categories:
                futures.append(executor.submit(
                    process_category, 
                    'conflict', EXTRACT_ANALYZE_PROMPT['conflict_types'], category, segment_1, segment_2
                ))
                futures.append(executor.submit(
                    process_category, 
                    'cross', EXTRACT_ANALYZE_PROMPT['cross_types'], category, segment_1, segment_2
                ))
                futures.append(executor.submit(
                    process_category, 
                    'duplicate', EXTRACT_ANALYZE_PROMPT['duplicate_types'], category, segment_1, segment_2
                ))
            
            for future in futures:
                output_key, result = future.result()
                output[output_key].append(result)
                
    except Exception as e:
        logger.error("generate_answer_error", action="generate_answer", **{"error.code": "CONT", "error.message": str(e)}, exc_info=True)            
    return output

# Ví dụ sử dụng
if __name__ == "__main__":
    segment_1 = """Điều 52. Người có quyền đề nghị Tòa án tuyên bố văn bản công chứng vô hiệu
Công chứng viên, người yêu cầu công chứng, người làm chứng, người phiên dịch, người có quyền lợi, nghĩa vụ liên quan, cơ quan nhà nước có thẩm quyền có quyền đề nghị Tòa án tuyên bố văn bản công chứng vô hiệu khi có căn cứ cho rằng việc công chứng có vi phạm pháp luật."""
    segment_1_id = 1

    segment_2 = """Điều 398. Đơn yêu cầu tuyên bố văn bản công chứng vô hiệu
1. Công chứng viên đã thực hiện việc công chứng, người yêu cầu công chứng, người làm chứng, người có quyền lợi, nghĩa vụ liên quan, cơ quan nhà nước có thẩm quyền có quyền yêu cầu Tòa án tuyên bố văn bản công chứng vô hiệu khi có căn cứ cho rằng việc công chứng có vi phạm pháp luật theo quy định của pháp luật về công chứng."""
    segment_2_id = 2
    category_1 = ['Quyền Lợi và Nghĩa Vụ']
    category_2 = ['Quyền Lợi và Nghĩa Vụ']
    
    import time
    start = time.time()
    
    result = generate_answer_multithread(segment_1, category_1, segment_2, category_2)
