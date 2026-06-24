import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

def extract_document_level(document_code):
    response = {"document_level": "Địa Phương"}

    if document_code.find('UBND') != -1 or document_code.find('HDND') != -1 or document_code.find('HĐND') != -1 or document_code.rstrip().endswith('-UB'):
        response["document_level"] = "Địa Phương"
    else:
        response["document_level"] = "Trung Ương"

    return response

if __name__ == '__main__':
    logger.info("extract_result", result=extract_document_level('26/2012/UBND'))
