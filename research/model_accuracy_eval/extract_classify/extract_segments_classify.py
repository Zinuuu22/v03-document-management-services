from core.common.mongo.client import get_mongo_client
import sys
import os
current_dir = os.getcwd()
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
sys.path.append(project_root)

from constants import MongoDBConfig
from pymongo import MongoClient
from core.v03.segments_classifier.extractor import classify_segment
import pandas as pd
client = get_mongo_client()

def extract_class_document(db_name, main_collection_name, extraced_collection_name, version):
    db = client[db_name]
    main_collection = db[main_collection_name]
    extraced_collection = db[extraced_collection_name]
    # tạo 1 backdoor để khi lỗi sẽ chỉ chạy lại những record chưa chạy trong main_collection
    list_extracted = [rec['before_id'] for rec in list(extraced_collection.find({'version': {'$ne': version}}))] # danh sách các _id trong main đã chạy
    # danh sách record trong main chưa extract
    list_main = list(main_collection.find({'_id': {'$nin': list_extracted}}))
    for article in list_main:
        record = {}
        record['before_id'] = article['_id']
        content = article.get('content')
        record['content'] = content
        classify_content = classify_segment(segment = content, version=version)
        result = [k for k,v in classify_content.items() if v]
        record['model_extracted_class'] = result
        record['version'] = version
        extraced_collection.insert_one(record)

def compare_class(db_name,main_collection_name, extraced_collection_name,compare_collection_name, main_class_key, compared_class_key):
    db = client[db_name]
    compared_collection = db[compare_collection_name]
    main_collection = db[main_collection_name]
    extracted_collection = db[extraced_collection_name]
    pipeline = [
    {
        # 1. Liên kết (Join)
        '$lookup': {
            'from': extraced_collection_name,
            'localField': '_id',
            'foreignField': 'before_id',
            'as': 'extracted'
        }
    },
    {
        # 2. Làm phẳng (Flatten) mảng kết quả lookup
        '$unwind': {
            'path': '$extracted'
        }
    },
    {
        # 3. Chọn và Định hình lại tài liệu (Đã sửa lỗi)
        '$project': {
            # Trường "_id" của tài liệu gốc (document cha)
            'before_id': '$_id',
            'content': '$content',
            'class_qwen_instru': '$extracted.model_extracted_class',
            'class': '$class',
            'version': '$extracted.version'
        }
    }
    ]
    
    listArticle = main_collection.aggregate(pipeline)
    
    for article in listArticle:
        main_class_value = article.get(main_class_key)
        compared_class_value = article.get(compared_class_key)

        # --- LOGIC SO SÁNH SET MỚI ---
        
        # 1. Trường hợp đặc biệt: Compared value là None/[] (HOÀN TOÀN TRỐNG RỖNG)
        # Sử dụng len() sau khi chuyển thành list để kiểm tra cả None và [] một cách hiệu quả.
        # len([]) = 0, len(None) = (sẽ lỗi nếu không kiểm tra None trước)
        
        # Kiểm tra nếu compared_class_value là None hoặc nếu nó là một mảng rỗng []
        is_none_or_empty_list = compared_class_value is None or (isinstance(compared_class_value, list) and not compared_class_value)
        
        if is_none_or_empty_list:
            check = 'none'
        
        else:
            # 2. Xử lý các trường hợp so sánh Set (chỉ chạy khi compared_class_value KHÔNG phải None/[])
            
            # Đảm bảo là set để so sánh không trùng lặp (chỉ áp dụng cho main_class)
            set_main_class = set(main_class_value if main_class_value is not None else [])
            # Vì đã kiểm tra None/[] ở trên, nên bây giờ chỉ cần chuyển giá trị còn lại sang set.
            set_compared_class = set(compared_class_value)

            if set_compared_class == set_main_class:
                check = 'matched'
            elif set_compared_class < set_main_class:
                check = 'less'  # Tập con thực sự: thiếu
            elif set_compared_class > set_main_class:
                check = 'more'  # Tập cha thực sự: thừa
            else:
                # Vừa thiếu vừa thừa (set giao nhau, nhưng không ai là tập con của ai)
                check = 'less_and_more'
                
        # --- KẾT THÚC LOGIC SO SÁNH ---
            
        result_dict = {
            'before_id': article.get('before_id'),
            'content': article.get('content'),
            'class_qwen_instru': article.get('class_qwen_instru'),
            'class': article.get('class'),
            'check': check,
            'version': article.get('version')
        }
        compared_collection.insert_one(result_dict)

if __name__ == '__main__':
    # extract_class_document(db_name='khiemdx', main_collection_name='content_classify_before_test', extraced_collection_name='content_classify_after_test', version='version_5')
    # compare_class(db_name='khiemdx', main_collection_name='content_classify_before_test', extraced_collection_name='content_classify_after_test', compare_collection_name='content_classify_compare_test', main_class_key='class', compared_class_key='class_qwen_instru')
    
    # extract_class_document(db_name='khiemdx', main_collection_name='content_classify_before', extraced_collection_name='content_classify_after_ver5', version='version_5')
    # compare_class(db_name='khiemdx', main_collection_name='content_classify_before', extraced_collection_name='content_classify_after_ver5', compare_collection_name='content_classify_compare_ver5', main_class_key='class', compared_class_key='class_qwen_instru')
    
    # a Giang
    extract_class_document(db_name='khiemdx', main_collection_name='content_classify_before_test_2', extraced_collection_name='content_classify_after_test_2', version='version_2')
    compare_class(db_name='khiemdx', main_collection_name='content_classify_before_test_2', extraced_collection_name='content_classify_after_test_2', compare_collection_name='content_classify_compare_test_2', main_class_key='class', compared_class_key='class_qwen_instru')
    