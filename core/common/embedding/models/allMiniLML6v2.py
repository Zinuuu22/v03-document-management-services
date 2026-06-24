from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn.functional as F
from core.common.embedding.models import embeddingBaseModel

class allMiniLML6v2(embeddingBaseModel):
    def __init__(self) -> None:
        self.name = 'allMiniLML6v2'
        self.source_link = 'https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2'
        self.dimension = 384
        self.tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')
        self.model = AutoModel.from_pretrained('sentence-transformers/all-MiniLM-L6-v2').to('cpu')
        self.max_chunk = 1000
        

    def _mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0] #First element of model_output contains all token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        
    def get_embeddings(self, sentences):
        # Tokenize sentences
        encoded_input = self.tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')
        # Compute token embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        # Perform pooling
        embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
        # Normalize embeddings
        embeddings = F.normalize(embeddings, p=2, dim=1)
        return embeddings