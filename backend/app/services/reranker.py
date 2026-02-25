import logging
import os
import collections
from typing import List, Tuple

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_cross_encoder_model = None
_tokenizer = None

def get_reranker_model():
    global _cross_encoder_model, _tokenizer
    if _cross_encoder_model is None:
        try:
            # For production CPU speed, we try to use ONNX Runtime / Optimum
            from optimum.onnxruntime import ORTModelForSequenceClassification
            from transformers import AutoTokenizer
            import torch

            logger.info(f"Loading optimized ONNX Cross-Encoder model '{settings.reranker_model}'...")
            
            model_dir = os.path.join(settings.upload_dir, "models", "onnx_reranker")
            os.makedirs(model_dir, exist_ok=True)
            
            # Export to ONNX if we haven't already
            if not os.path.exists(os.path.join(model_dir, "model.onnx")):
                logger.info("Downloading, exporting, and quantizing model to ONNX. This happens only once...")
                _tokenizer = AutoTokenizer.from_pretrained(settings.reranker_model)
                model = ORTModelForSequenceClassification.from_pretrained(
                    settings.reranker_model, 
                    export=True
                )
                _tokenizer.save_pretrained(model_dir)
                model.save_pretrained(model_dir)
                logger.info(f"ONNX Model exported and saved to {model_dir}")
            else:
                logger.info(f"Loading cached ONNX model from {model_dir}")
                _tokenizer = AutoTokenizer.from_pretrained(model_dir)
                
            _cross_encoder_model = ORTModelForSequenceClassification.from_pretrained(model_dir)
            logger.info("ONNX Cross-Encoder loaded successfully.")

        except ImportError as e:
            logger.warning(f"Optimum/ONNX not installed ({e}). Falling back to standard PyTorch CrossEncoder.")
            try:
                from sentence_transformers import CrossEncoder
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(f"Loading PyTorch Cross-Encoder model '{settings.reranker_model}' on {device}...")
                _cross_encoder_model = CrossEncoder(settings.reranker_model, device=device)
                logger.info("PyTorch Cross-Encoder loaded successfully.")
            except ImportError:
                logger.error("sentence-transformers or torch are not installed. Cannot use reranker.")
                raise
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}")
            raise
    return _cross_encoder_model

class RerankerService:
    def __init__(self):
        self.enabled = settings.enable_reranker
        self.top_k = settings.reranker_top_k
        self.cache = collections.OrderedDict()
        self.cache_size = settings.embedding_cache_size
        
    def _score_pairs_cached(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Score a list of pairs using the cross-encoder model, with local LRU caching.
        """
        model = get_reranker_model()
        scores = []
        pairs_to_compute = []
        indices_to_compute = []
        
        # Check cache
        for i, pair in enumerate(pairs):
            cache_key = (pair[0], pair[1])
            if cache_key in self.cache:
                scores.append(self.cache[cache_key])
                self.cache.move_to_end(cache_key)
            else:
                scores.append(0.0)  # Placeholder
                pairs_to_compute.append(pair)
                indices_to_compute.append(i)
                
        # Compute missing
        if pairs_to_compute:
            if hasattr(model, 'predict'):
                # sentence-transformers CrossEncoder fallback
                import numpy as np
                new_scores = model.predict(pairs_to_compute)
                if isinstance(new_scores, np.ndarray):
                    new_scores = new_scores.tolist()
                elif not isinstance(new_scores, list):
                    new_scores = [new_scores]
            else:
                # Optimum ONNX
                import torch
                global _tokenizer
                inputs = _tokenizer(
                    [p[0] for p in pairs_to_compute],
                    [p[1] for p in pairs_to_compute],
                    padding=True,
                    truncation=True,
                    return_tensors="pt"
                )
                with torch.no_grad():
                    logits = model(**inputs).logits
                
                # Squeeze the last dimension if it's 1 (standard cross-encoder output)
                new_scores = logits.squeeze(-1).tolist()
                if not isinstance(new_scores, list):
                    new_scores = [new_scores]
                    
            # Update scores and cache
            for idx, pair, score in zip(indices_to_compute, pairs_to_compute, new_scores):
                scores[idx] = float(score)
                cache_key = (pair[0], pair[1])
                self.cache[cache_key] = float(score)
                
                # Enforce LRU size
                if len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
                    
        return scores

    def rerank(self, query: str, chunks: List[dict]) -> List[dict]:
        """
        Rerank a list of chunks based on a query using Cross-Encoder.
        Returns the top-k results sorted by the reranker score.
        """
        if not self.enabled or not chunks:
            return chunks[:self.top_k]
            
        try:
            # Prepare pairs for cross encoder: (query, document_text)
            pairs = [[query, chunk["text"]] for chunk in chunks]
            
            # Score pairs
            scores = self._score_pairs_cached(pairs)
            
            # Combine chunks with new scores
            for chunk, score in zip(chunks, scores):
                chunk["rerank_score"] = float(score)
                chunk["vector_score"] = chunk.get("score", 0.0)
                chunk["score"] = float(score)  # override main score for sorting
                
            # Sort by new score descending
            reranked_chunks = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
            
            logger.info(f"Reranked {len(chunks)} chunks, keeping top {self.top_k}")
            return reranked_chunks[:self.top_k]
            
        except Exception as e:
            logger.warning(f"Reranking failed: {e}. Falling back to original vector search order.")
            return chunks[:self.top_k]

reranker_service = RerankerService()
