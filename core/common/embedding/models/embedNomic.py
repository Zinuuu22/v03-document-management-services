import torch
import torch.nn.functional as F
from torch import Tensor
from transformers import AutoTokenizer, AutoModel
from core.common.embedding.models import embeddingBaseModel

class embedNommic(embeddingBaseModel):
    def __init__(self) -> None:
        self.name = 'Nomic'
        self.source_link = 'https://huggingface.co/nomic-ai/nomic-embed-text-v1'
        self.dimension = 768        
        self.tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
        self.model = AutoModel.from_pretrained('nomic-ai/nomic-embed-text-v1', trust_remote_code=True).to('cpu')
        self.model.eval()
        self.max_chunk = 1000

    def _average_pool(self, model_output, attention_mask):
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        
    def get_embeddings(self, sentences):
        _sentences = []
        for sentence in sentences:
            _sentences.append(f'search_document: {sentence}')        
        encoded_input = self.tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')
        with torch.no_grad():
            model_output = self.model(**encoded_input)        
        embeddings = self._average_pool(model_output, encoded_input['attention_mask'])
        embeddings = F.normalize(embeddings, p=2, dim=1)
        return embeddings        