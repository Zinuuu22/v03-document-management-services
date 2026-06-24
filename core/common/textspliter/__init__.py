from typing import Any, Optional
from collections.abc import Iterable
import os
import sys
import nltk
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()
#for pkg in ["punkt", "punkt_tab"]:
#    try:
#        nltk.data.find(f"tokenizers/{pkg}")
#    except LookupError:
#        nltk.download(pkg)

class FixedRecursiveCharacterTextSplitter():
    def __init__(self, 
                 fixed_separator: str = "\n\n", 
                 separators: Optional[list[str]] = None, 
                 chunk_size : int = None,
                 chunk_overlap: int = 0,
                 **kwargs: Any):
        """Create a new TextSplitter."""
        super().__init__(**kwargs)
        self._fixed_separator = fixed_separator
        self._separators = separators or ["\n\n", "\n", " ", ""]
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def _length_function(self, text : str) -> int:
        tokens = nltk.word_tokenize(text)
        return len(tokens)
    
    def split_text(self, document_segmented: str) -> list[str]:
        """Split incoming text and return chunks."""
        start_t = time.time()
        try:
            if self._fixed_separator:
                chunks = document_segmented.split(self._fixed_separator)
            else:
                chunks = list(document_segmented)
            final_chunks = []
            for chunk in chunks:
                if self._length_function(chunk) > self._chunk_size:
                    final_chunks.extend(self.recursive_split_text(chunk))
                elif len(chunk):
                    final_chunks.append(chunk)
            
            logger.info("split_text_success", action="split_text", **{"event.duration": time.time()-start_t, "event.status": "success"}, output_chunks=len(final_chunks))
            return final_chunks
        except Exception as e:
            logger.error("split_text_failed", action="split_text", **{"error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            raise

    def recursive_split_text(self, text: str) -> list[str]:
        """Split incoming text and return chunks."""
        final_chunks = []
        # Get appropriate separator to use
        separator = self._separators[-1]
        for _s in self._separators:
            if _s == "":
                separator = _s
                break
            if _s in text:
                separator = _s
                break
        # Now that we have the separator, split the text
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        # Now go merging things, recursively splitting longer texts.
        _good_splits = []
        for s in splits:
            if self._length_function(s) < self._chunk_size:
                _good_splits.append(s)
            else:
                if _good_splits:
                    merged_text = self._merge_splits(_good_splits, separator)
                    final_chunks.extend(merged_text)
                    _good_splits = []
                other_info = self.recursive_split_text(s)
                final_chunks.extend(other_info)
        if _good_splits:
            merged_text = self._merge_splits(_good_splits, separator)
            final_chunks.extend(merged_text)
        return final_chunks
    
    def _join_docs(self, docs: list[str], separator: str) -> Optional[str]:
        text = separator.join(docs)
        text = text.strip()
        if text == "":
            return None
        else:
            return text
    
    def _merge_splits(self, splits: Iterable[str], separator: str) -> list[str]:
        # We now want to combine these smaller pieces into medium size
        # chunks to send to the LLM.
        separator_len = self._length_function(separator)

        docs = []
        current_doc: list[str] = []
        total = 0
        for d in splits:
            _len = self._length_function(d)
            if (
                    total + _len + (separator_len if len(current_doc) > 0 else 0)
                    > self._chunk_size
            ):
                if total > self._chunk_size:
                    logger.warning("chunk_size_exceeded", action="_merge_splits", chunk_size=total, max_chunk_size=self._chunk_size)
                if len(current_doc) > 0:
                    doc = self._join_docs(current_doc, separator)
                    if doc is not None:
                        docs.append(doc)
                    # Keep on popping if:
                    # - we have a larger chunk than in the chunk overlap
                    # - or if we still have any chunks and the length is long
                    while total > self._chunk_overlap or (
                            total + _len + (separator_len if len(current_doc) > 0 else 0)
                            > self._chunk_size
                            and total > 0
                    ):
                        total -= self._length_function(current_doc[0]) + (
                            separator_len if len(current_doc) > 1 else 0
                        )
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += _len + (separator_len if len(current_doc) > 1 else 0)
        doc = self._join_docs(current_doc, separator)
        if doc is not None:
            docs.append(doc)
        return docs


if __name__ == '__main__':
    frc = FixedRecursiveCharacterTextSplitter(chunk_size=100)
