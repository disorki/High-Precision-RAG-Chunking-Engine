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
    # ленивая загрузка модели реранкера
    global _cross_encoder_model, _tokenizer
    if _cross_encoder_model is None:
        try:
            # попытка загрузки оптимизированной onnx модели
            from optimum.onnxruntime import ORTModelForSequenceClassification
            from transformers import AutoTokenizer
            import torch

            logger.info(f"Загрузка ONNX реранкера '{settings.reranker_model}'...")
            
            model_dir = os.path.join(settings.upload_dir, "models", "onnx_reranker")
            os.makedirs(model_dir, exist_ok=True)
            
            # экспорт в onnx при первом запуске
            if not os.path.exists(os.path.join(model_dir, "model.onnx")):
                logger.info("Экспорт и квантование модели в ONNX (разово)...")
                _tokenizer = AutoTokenizer.from_pretrained(settings.reranker_model)
                model = ORTModelForSequenceClassification.from_pretrained(
                    settings.reranker_model, 
                    export=True
                )
                _tokenizer.save_pretrained(model_dir)
                model.save_pretrained(model_dir)
                logger.info(f"ONNX модель сохранена в {model_dir}")
            else:
                logger.info(f"Загрузка кэшированной ONNX модели из {model_dir}")
                _tokenizer = AutoTokenizer.from_pretrained(model_dir)
                
            _cross_encoder_model = ORTModelForSequenceClassification.from_pretrained(model_dir)
            logger.info("ONNX реранкер успешно загружен")

        except ImportError as e:
            logger.warning(f"Optimum/ONNX не установлен. Используется стандартный PyTorch.")
            try:
                from sentence_transformers import CrossEncoder
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(f"Загрузка PyTorch реранкера '{settings.reranker_model}' на {device}...")
                _cross_encoder_model = CrossEncoder(settings.reranker_model, device=device)
                logger.info("PyTorch реранкер успешно загружен")
            except ImportError:
                logger.error("sentence-transformers или torch не установлены")
                raise
        except Exception as e:
            logger.error(f"Ошибка загрузки реранкера: {e}")
            raise
    return _cross_encoder_model

class RerankerService:
    # сервис реранжирования результатов поиска
    def __init__(self):
        self.enabled = settings.enable_reranker
        self.top_k = settings.reranker_top_k
        self.cache = collections.OrderedDict()
        self.cache_size = settings.embedding_cache_size
        
    def _score_pairs_cached(self, pairs: List[Tuple[str, str]]) -> List[float]:
        # получение скоров для пар (запрос, текст) с lru-кэшированием
        model = get_reranker_model()
        scores = []
        pairs_to_compute = []
        indices_to_compute = []
        
        # проверка кэша
        for i, pair in enumerate(pairs):
            cache_key = (pair[0], pair[1])
            if cache_key in self.cache:
                scores.append(self.cache[cache_key])
                self.cache.move_to_end(cache_key)
            else:
                scores.append(0.0)
                pairs_to_compute.append(pair)
                indices_to_compute.append(i)
                
        # расчет отсутствующих
        if pairs_to_compute:
            if hasattr(model, 'predict'):
                # fallback для sentence-transformers
                import numpy as np
                new_scores = model.predict(pairs_to_compute)
                if isinstance(new_scores, np.ndarray):
                    new_scores = new_scores.tolist()
                elif not isinstance(new_scores, list):
                    new_scores = [new_scores]
            else:
                # optimum onnx
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
                    
            # обновление кэша
            for idx, pair, score in zip(indices_to_compute, pairs_to_compute, new_scores):
                scores[idx] = float(score)
                cache_key = (pair[0], pair[1])
                self.cache[cache_key] = float(score)
                
                # Enforce LRU size
                if len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
                    
        return scores

    def rerank(self, query: str, chunks: List[dict]) -> List[dict]:
        # переупорядочивание чанков на основе кросс-энкодера
        if not self.enabled or not chunks:
            return chunks[:self.top_k]
            
        try:
            # подготовка пар
            pairs = [[query, chunk["text"]] for chunk in chunks]
            
            # расчет скоров
            scores = self._score_pairs_cached(pairs)
            
            # применение новых весов
            for chunk, score in zip(chunks, scores):
                chunk["rerank_score"] = float(score)
                chunk["vector_score"] = chunk.get("score", 0.0)
                chunk["score"] = float(score)
                
            # сортировка по убыванию
            reranked_chunks = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
            
            logger.info(f"Реранжировано {len(chunks)} чанков, оставлено топ-{self.top_k}")
            return reranked_chunks[:self.top_k]
            
        except Exception as e:
            logger.warning(f"Ошибка реранжирования: {e}. Используется исходный порядок.")
            return chunks[:self.top_k]

# синглтон сервиса
reranker_service = RerankerService()
