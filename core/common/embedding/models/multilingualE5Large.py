import torch.nn.functional as F
from torch import Tensor
from transformers import AutoTokenizer, AutoModel
from core.common.embedding.models import embeddingBaseModel

class multilingualE5Large(embeddingBaseModel):
    def __init__(self) -> None:
        self.name = 'multilingualE5Large'
        self.source_link = 'https://huggingface.co/intfloat/multilingual-e5-large'
        self.dimension = 1024
        self.tokenizer = AutoTokenizer.from_pretrained('intfloat/multilingual-e5-large')
        self.model = AutoModel.from_pretrained('intfloat/multilingual-e5-large').to('cpu')
        self.max_chunk = 1000
        

    def _average_pool(self, last_hidden_states: Tensor,
                    attention_mask: Tensor) -> Tensor:
        last_hidden = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)
        return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]
        
    def get_embeddings(self, sentences):
        _sentences = []
        for sentence in sentences:
            _sentences.append(f'passage: {sentence}')
        batch_dict = self.tokenizer(_sentences, max_length=512, padding=True, truncation=True, return_tensors='pt')
        outputs = self.model(**batch_dict)
        embeddings = self._average_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
        # normalize embeddings
        embeddings = F.normalize(embeddings, p=2, dim=1).detach()
        return embeddings
        