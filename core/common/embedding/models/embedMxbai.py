import torch.nn.functional as F
import torch
from torch import Tensor
from transformers import AutoTokenizer, AutoModel
from core.common.embedding.models import embeddingBaseModel

class embedMxbai(embeddingBaseModel):
    def __init__(self, device = 'cuda') -> None:
        self.name = 'Mxbai'
        self.source_link = 'https://huggingface.co/mixedbread-ai/mxbai-embed-large-v1'
        self.dimension = 1024                
        self.tokenizer = AutoTokenizer.from_pretrained('mixedbread-ai/mxbai-embed-large-v1')
        self.device = device
        if self.device == 'cuda':
            self.model = AutoModel.from_pretrained('mixedbread-ai/mxbai-embed-large-v1')
        else:    
            self.model = AutoModel.from_pretrained('mixedbread-ai/mxbai-embed-large-v1').to('cpu')
        self.max_chunk = 1000
    
    def transform_query(self, query: str) -> str:
        """ For retrieval, add the prompt for query (not for documents).
        """
        return f'Represent this sentence for searching relevant passages: {query}'

    # The model works really well with cls pooling (default) but also with mean pooling.
    def pooling(self, outputs: torch.Tensor, inputs,  strategy: str = 'cls'):
        if strategy == 'cls':
            outputs = outputs[:, 0]
        elif strategy == 'mean':
            outputs = torch.sum(
                outputs * inputs["attention_mask"][:, :, None], dim=1) / torch.sum(inputs["attention_mask"])
        else:
            raise NotImplementedError
        return outputs.detach().cpu().numpy()
    
    def get_embeddings(self, sentences):
        inputs = self.tokenizer(sentences, padding=True, return_tensors='pt')
        for k, v in inputs.items():
            inputs[k] = v
        outputs = self.model(**inputs).last_hidden_state
        embeddings = self.pooling(outputs, inputs, 'cls')
        return embeddings        