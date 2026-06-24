import uuid
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging
import time

setup_logging()
logger = structlog.get_logger()

from core.common.embedding.models import embeddingBaseModel
from core.common.textspliter import FixedRecursiveCharacterTextSplitter

class CacheEmbedding():
    def __init__(self, 
                model_instance : embeddingBaseModel) -> None:
        self._model_instance = model_instance()
        self.max_chunks = self._model_instance.max_chunk
        self.textSpliter = FixedRecursiveCharacterTextSplitter(chunk_size=self.max_chunks)
        self.embedding_size = model_instance.dimension

    def embed_chunks(self, 
                    chunks:list[str]):        
        embeddings = self._model_instance.get_embeddings(sentences=chunks)            
        return embeddings        

    
    def embed_segment(self, 
                    segment_text) :

        result = []
        chunks = self.textSpliter.split_text(segment_text)            
        embeddings = self._model_instance.get_embeddings(sentences=chunks)                        
        for j, chunk in enumerate(chunks):
            result_chunk = {
                'segment_text': segment_text,
                'chunk_index': j,
                'text': chunk,
                'vector': embeddings[j]
            }                
            result.append(result_chunk)                
        return result
    
    
    def embed_segments(self, 
                    segments_text) :

        start_t = time.time()
        try:
            result = []
            for segment_text in segments_text:
                # segment_text = re.sub(r'Điều\s\d+\.\s*', '', segment_text)                
                chunks = self.textSpliter.split_text(segment_text)            
                embeddings = self._model_instance.get_embeddings(sentences=chunks)            
                
                for j, chunk in enumerate(chunks):
                    result_chunk = {
                        'segment_text': segment_text,
                        'chunk_index': j,
                        'text': chunk,
                        'vector': embeddings[j]
                    }                
                    result.append(result_chunk)   

            logger.debug("embed_segments_success", action="embed_segments", **{"event.duration": time.time()-start_t, "event.status": "success"}, result_count=len(result))
            return result
        except Exception as e:
            logger.error("embed_segments_failed", action="embed_segments", **{"error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            raise
    

    def embed_segments_batch(self, 
                            segments_id: list[str],
                            segments_index: list[int],                       
                            segments_text: list[str]) -> list[list[float]]:

        if len(segments_id) != len(segments_text):
            raise f"segments_id and segments_text is not match"
    
        result = []

        # Preparse data
        texts = []
        for i, segment_text in enumerate(segments_text):
            chunks = self.textSpliter.split_text(segment_text)
            segment_id = segments_id[i]
            segment_index = segments_index[i]        
            for j, chunk in enumerate(chunks):
                result_chunk = {
                    'segment_id': segment_id,
                    'segment_index': segment_index,                    
                    'segment_text': segment_text,
                    'chunk_index': j,
                    'chunk_id': str(uuid.uuid4()),    
                    'text': chunk,
                    'vector': None
                }
                result.append(result_chunk)
            texts = texts + chunks
        # Create embedding data
        embeddings = self._model_instance.get_embeddings(sentences=texts)   
        for i, embedding in enumerate(embeddings):
            result[i]['vector'] = embedding
        return result
    
    def embed_segments_migrate(self, 
                    segments_id: list[str],
                    segments_index: list[int],
                    segments_text: list[str]) -> list[list[float]]:

        if len(segments_id) != len(segments_text):
            raise f"segments_id and segments_text is not match"
    
        result = []
        for i, segment_text in enumerate(segments_text):
            if len(segment_text) == 0:
                continue
            
            chunks = self.textSpliter.split_text(segment_text)            
            segment_id = segments_id[i]                        
            segment_index = segments_index[i]            
            embeddings = self._model_instance.get_embeddings(sentences=chunks)            
            
            for j, chunk in enumerate(chunks):
                result_chunk = {
                    'segment_id': segment_id,
                    'segment_index': segment_index,
                    'segment_text': segment_text,
                    'chunk_index': j,
                    'chunk_id': uuid.uuid4(),                        
                    'text': chunk,
                    'vector': embeddings[j]
                }                
                result.append(result_chunk)                
        return result
    



if __name__ == "__main__":
    text = '''Điều 2. Phương thức phân giao hạn ngạch thuế quan nhập khẩu mặt hàng muối, trứng gia cầm năm 2024

Hạn ngạch thuế quan nhập khẩu mặt hàng muối, trứng gia cầm năm 2024 được thực hiện theo phương thức phân giao quy định tại Nghị định số 69/2018/NĐ-CP ngày 15 tháng 5 năm 2018 của Chính phủ quy định chi tiết một số điều của Luật Quản lý ngoại thương và Thông tư số 12/2018/TT-BCT ngày 15 tháng 6 năm 2018 của Bộ trưởng Bộ Công Thương quy định chi tiết một số điều của Luật Quản lý ngoại thương và Nghị định số 69/2018/NĐ-CP ngày 15 tháng 5 năm 2018 của Chính phủ quy định chi tiết một số điều của Luật Quản lý ngoại thương.

Điều 3. Đối tượng phân giao hạn ngạch thuế quan nhập khẩu mặt hàng muối, trứng gia cầm năm 2024

Hạn ngạch thuế quan nhập khẩu mặt hàng muối được phân giao cho thương nhân trực tiếp sử dụng làm nguyên liệu sản xuất thuốc, sản phẩm y tế và làm nguyên liệu sản xuất hóa chất.
Hạn ngạch thuế quan nhập khẩu mặt hàng trứng gia cầm được phân giao cho thương nhân có nhu cầu nhập khẩu.
Điều 4. Thời điểm phân giao hạn ngạch thuế quan nhập khẩu mặt hàng muối, trứng gia cầm năm 2024

Bộ Công Thương trao đổi với Bộ Nông nghiệp và Phát triển nông thôn để xác định thời điểm phân giao hạn ngạch thuế quan nhập khẩu mặt hàng muối, trứng gia cầm năm 2024.

Điều 5. Hiệu lực thi hành

Thông tư này có hiệu lực thi hành kể từ ngày 06 tháng 02 năm 2024 đến hết ngày 31 tháng 12 năm 2024./.'''

    from core.embedding.models.vietnameseEmbedding import vietnameseEmbedding
    
    ce = CacheEmbedding(vietnameseEmbedding)            
    ce.embed_segments(['0xc11'], [text])