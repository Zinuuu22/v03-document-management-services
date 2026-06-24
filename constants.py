import os
from dotenv import load_dotenv
from typing import Final


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# Load environment variables
load_dotenv()

# ==================== DATABASE CONFIGURATION ====================
class MongoDBConfig:
    HOST: Final[str] = os.getenv('MONGODB_HOST')
    PORT: Final[int] = int(os.getenv('MONGODB_PORT'))
    USERNAME: Final[str] = os.getenv('MONGODB_USERNAME')
    PASSWORD: Final[str] = os.getenv('MONGODB_PASS')
    AUTH_SOURCE: Final[str] = os.getenv('MONGODB_AUTH_SOURCE', 'admin')
    URI: Final[str] = f"mongodb://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/?authSource={AUTH_SOURCE}"

class QdrantConfig:
    HOST: Final[str] = os.getenv("QDRANT_HOST", "192.168.1.200")
    PORT: Final[int] = int(os.getenv('QDRANT_PORT', '6333'))
    API_KEY: Final[str] = os.getenv('QDRANT_API_KEY', '')

# ==================== KAFKA CONFIGURATION ====================
class KafkaConfig:
    BOOTSTRAP_SERVERS: Final[str] = os.getenv('KAFKA_BOOTSTRAP_SERVERS')    

# ==================== TREE CLASSIFIER CONFIGURATION ====================
class TreeClassifierConfig:
    TREE_CLASSIFIER_QUERY_TOPIC: Final[str] = os.getenv('TREE_CLASSIFIER_QUERY_TOPIC', 'TREE_CLASSIFIER_QUERY_TOPIC_DEV')
    TREE_CLASSIFIER_GROUP: Final[str] = os.getenv('TREE_CLASSIFIER_GROUP', 'group_tree_classifier_dev')

# ==================== API ENDPOINTS ====================
class APIEndpoints:
    SEARCH_SEGMENTS: Final[str] = os.getenv('SEARCH_SEGMENTS_ENDPOINT')
    CREATE_EMBEDDINGS: Final[str] = os.getenv('CREATE_EMBEDDINGS_ENDPOINT')
    LLMS_ANSWER: Final[str] = os.getenv('LLMS_ANSWER_ENDPOINT')
    LLMS_ANSWERS: Final[str] = os.getenv('LLMS_ANSWERS_ENDPOINT')
    EXTRACT_PARTS: Final[str] = os.getenv('EXTRACT_PARTS_URL')
    EXTRACT_AND_CLASSIFY: Final[str] = os.getenv('EXTRACT_AND_CLASSIFY_URL')
    EXTRACT_FIELDS: Final[str] = os.getenv('EXTRACT_FIELDS_URL')    
    SEARCH_CONTENT: Final[str] = os.getenv('SEARCH_CONTENT_ENDPOINT')
    DOWNLOAD_DOCX: Final[str] = os.getenv('DOWNLOAD_DOCX_ENDPOINT')
    SEMANTIC_SEARCH: Final[str] = os.getenv('SEMANTIC_SEARCH_KNOWLEDGE_ENDPOINT')

# ==================== APPLICATION SETTINGS ====================
class AppConfig:
    APP_NAME: Final[str] = os.getenv('APP_NAME', 'v03-sync-services')
    API_SERVICE_HOST: Final[str] = os.getenv('API_SERVICE_HOST')
    API_SERVICE_PORT: Final[str] = os.getenv('API_SERVICE_PORT')
    
    EXTRACT_NORM_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_NUMBER_WORKER', 4))      
    UPLOAD_DIR: Final[str] = os.getenv('UPLOAD_DIR', 'uploads')    
    
    IMPORT_TREE_NUMBER_WORKER: Final[int] = int(os.getenv('IMPORT_TREE_NUMBER_WORKER', 4))
    TRAIN_TREE_NUMBER_WORKER: Final[int] = int(os.getenv('TRAIN_TREE_NUMBER_WORKER', 2))
    
    SEMANTIC_SEARCH_KNOWLEDGE_NAME: Final[str] = os.getenv('SEMANTIC_SEARCH_KNOWLEDGE_NAME')
    SEMANTIC_SEARCH_KNOWLEDGE_NAME_MODEL: Final[str] = os.getenv('SEMANTIC_SEARCH_KNOWLEDGE_NAME_MODEL')

    SEMANTIC_SEARCH_KNOWLEDGE_CONTENT: Final[str] = os.getenv('SEMANTIC_SEARCH_KNOWLEDGE_CONTENT')
    SEMANTIC_SEARCH_KNOWLEDGE_CONTENT_MODEL: Final[str] = os.getenv('SEMANTIC_SEARCH_KNOWLEDGE_CONTENT_MODEL')
    
    EXTRACT_NORM_KEYWORDS_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_KEYWORDS_NUMBER_WORKER', 2))
    EXTRACT_NORM_METADATA_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_METADATA_NUMBER_WORKER', 2))
    EXTRACT_NORM_RELATIONSHIP_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_RELATIONSHIP_NUMBER_WORKER', 2))
    EXTRACT_NORM_RELATIONSHIP_ARTICLE_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_RELATIONSHIP_ARTICLE_NUMBER_WORKER', 2))
    EXTRACT_ARTICLE_RELATIONSHIP_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_ARTICLE_RELATIONSHIP_NUMBER_WORKER', os.getenv('EXTRACT_NORM_RELATIONSHIP_ARTICLE_NUMBER_WORKER', '2')))
    EXTRACT_NORM_REGULATED_ENTITY_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_REGULATED_ENTITY_NUMBER_WORKER', 2))
    EXTRACT_NORM_REGULATED_OBJECT_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_REGULATED_OBJECT_NUMBER_WORKER', 2))
    EXTRACT_NORM_SOCIAL_RELATION_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_SOCIAL_RELATION_NUMBER_WORKER', 2))
    EXTRACT_NORM_LAW_AUTHORITY_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_NORM_LAW_AUTHORITY_NUMBER_WORKER', 2))
    EXTRACT_ARTICLE_CLASS_NUMBER_WORKER: Final[int] = int(os.getenv('EXTRACT_ARTICLE_CLASS_NUMBER_WORKER', 2))

    INDEX_ELASTIC_NUMBER_WORKER: Final[int] = int(os.getenv('INDEX_ELASTIC_NUMBER_WORKER', 2))
    TITLE_EMBEDDING_NUMBER_WORKER: Final[int] = int(os.getenv('TITLE_EMBEDDING_NUMBER_WORKER', 2))
    CONTENT_EMBEDDING_NUMBER_WORKER: Final[int] = int(os.getenv('CONTENT_EMBEDDING_NUMBER_WORKER', 2))
    ARTICLE_EMBEDDING_NUMBER_WORKER: Final[int] = int(os.getenv('ARTICLE_EMBEDDING_NUMBER_WORKER', 2))
    


# ********************* LLMs CONFIGURATION *********************
# ==================== COMMON LLMs CONFIGURATION ====================
class LLMsConfig:
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL')        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH'))    
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME')        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT')        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE')
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P')
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K')
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS')
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE')
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY')
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL')
    
    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK', 'false').lower() == 'true'


# ==================== KEYWORDS LLMs CONFIGURATION ====================
class LLMsConfigExtractKeywords(LLMsConfig):
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL_KEYWORDS', LLMsConfig.LLMS_BASE_URL)        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH_KEYWORDS', LLMsConfig.LLMS_BATCH))
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME_KEYWORDS', LLMsConfig.LLMS_MODEL_NAME)        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT_KEYWORDS', LLMsConfig.PARAM_CONTENT)        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE_KEYWORDS', LLMsConfig.PARAM_TEMPERATURE)
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P_KEYWORDS', LLMsConfig.PARAM_TOP_P)
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K_KEYWORDS', LLMsConfig.PARAM_TOP_K)
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS_KEYWORDS', LLMsConfig.PARAM_MAX_NEW_TOKENS)
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE_KEYWORDS', LLMsConfig.PARAM_DO_SAMPLE)
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY_KEYWORDS', LLMsConfig.PARAM_REPETITION_PENALTY)    
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL_KEYWORDS')
    
    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA_KEYWORDS', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK_KEYWORDS', 'false').lower() == 'true'
    

# ==================== METADATA LLMs CONFIGURATION ====================
class LLMsConfigExtractMetadata(LLMsConfig):
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL_METADATA', LLMsConfig.LLMS_BASE_URL)        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH_METADATA', LLMsConfig.LLMS_BATCH))
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME_METADATA', LLMsConfig.LLMS_MODEL_NAME)        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT_METADATA', LLMsConfig.PARAM_CONTENT)        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE_METADATA', LLMsConfig.PARAM_TEMPERATURE)
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P_METADATA', LLMsConfig.PARAM_TOP_P)
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K_METADATA', LLMsConfig.PARAM_TOP_K)
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS_METADATA', LLMsConfig.PARAM_MAX_NEW_TOKENS)
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE_METADATA', LLMsConfig.PARAM_DO_SAMPLE)
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY_METADATA', LLMsConfig.PARAM_REPETITION_PENALTY)
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL_METADATA')
    
    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA_METADATA', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK_METADATA', 'false').lower() == 'true'


# =================== RELATIONSHIP LLMs CONFIGURATION ====================
class LLMsConfigExtractRelationship(LLMsConfig):
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL_RELATIONSHIP', LLMsConfig.LLMS_BASE_URL)        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH_RELATIONSHIP', LLMsConfig.LLMS_BATCH))
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME_RELATIONSHIP', LLMsConfig.LLMS_MODEL_NAME)        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT_RELATIONSHIP', LLMsConfig.PARAM_CONTENT)        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE_RELATIONSHIP', LLMsConfig.PARAM_TEMPERATURE)
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P_RELATIONSHIP', LLMsConfig.PARAM_TOP_P)
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K_RELATIONSHIP', LLMsConfig.PARAM_TOP_K)
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS_RELATIONSHIP', LLMsConfig.PARAM_MAX_NEW_TOKENS)
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE_RELATIONSHIP', LLMsConfig.PARAM_DO_SAMPLE)
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY_RELATIONSHIP', LLMsConfig.PARAM_REPETITION_PENALTY)
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL_RELATIONSHIP')

    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA_RELATIONSHIP', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK_RELATIONSHIP', 'false').lower() == 'true'


# ==================== SOCIAL RELATIONSHIP LLMs CONFIGURATION ====================
class LLMsConfigExtractSocialRelationship(LLMsConfig):
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL_SOCIAL_RELATIONSHIP', LLMsConfig.LLMS_BASE_URL)        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH_SOCIAL_RELATIONSHIP', LLMsConfig.LLMS_BATCH))
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME_SOCIAL_RELATIONSHIP', LLMsConfig.LLMS_MODEL_NAME)        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT_SOCIAL_RELATIONSHIP', LLMsConfig.PARAM_CONTENT)        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE_SOCIAL_RELATIONSHIP', LLMsConfig.PARAM_TEMPERATURE)
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P_SOCIAL_RELATIONSHIP', LLMsConfig.PARAM_TOP_P)
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K_SOCIAL_RELATIONSHIP', LLMsConfig.PARAM_TOP_K)
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS_SOCIAL_RELATIONSHIP', LLMsConfig.PARAM_MAX_NEW_TOKENS)
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE_SOCIAL_RELATIONSHIP', LLMsConfig.PARAM_DO_SAMPLE)
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY_SOCIAL_RELATIONSHIP', LLMsConfig.PARAM_REPETITION_PENALTY)
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL_SOCIAL_RELATIONSHIP')

    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA_SOCIAL_RELATIONSHIP', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK_SOCIAL_RELATIONSHIP', 'false').lower() == 'true'


# ==================== SYNTHESIS CONTENT LLMs CONFIGURATION ====================
class LLMsConfigSynthesisContent(LLMsConfig):
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL_SYNTHESIS_CONTENT', LLMsConfig.LLMS_BASE_URL)        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH_SYNTHESIS_CONTENT', LLMsConfig.LLMS_BATCH))
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME_SYNTHESIS_CONTENT', LLMsConfig.LLMS_MODEL_NAME)        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT_SYNTHESIS_CONTENT', LLMsConfig.PARAM_CONTENT)        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE_SYNTHESIS_CONTENT', LLMsConfig.PARAM_TEMPERATURE)
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P_SYNTHESIS_CONTENT', LLMsConfig.PARAM_TOP_P)
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K_SYNTHESIS_CONTENT', LLMsConfig.PARAM_TOP_K)
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS_SYNTHESIS_CONTENT', LLMsConfig.PARAM_MAX_NEW_TOKENS)
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE_SYNTHESIS_CONTENT', LLMsConfig.PARAM_DO_SAMPLE)
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY_SYNTHESIS_CONTENT', LLMsConfig.PARAM_REPETITION_PENALTY)
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL_SYNTHESIS_CONTENT')

    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA_SYNTHESIS_CONTENT', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK_SYNTHESIS_CONTENT', 'false').lower() == 'true'


# ==================== RELATIONSHIP ARTICLES LLMs CONFIGURATION ====================
class LLMsConfigExtractRelationshipArticle(LLMsConfig):
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL_RELATIONSHIP_ARTICLE', LLMsConfig.LLMS_BASE_URL)        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH_RELATIONSHIP_ARTICLE', LLMsConfig.LLMS_BATCH))
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME_RELATIONSHIP_ARTICLE', LLMsConfig.LLMS_MODEL_NAME)        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT_RELATIONSHIP_ARTICLE', LLMsConfig.PARAM_CONTENT)        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE_RELATIONSHIP_ARTICLE', LLMsConfig.PARAM_TEMPERATURE)
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P_RELATIONSHIP_ARTICLE', LLMsConfig.PARAM_TOP_P)
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K_RELATIONSHIP_ARTICLE', LLMsConfig.PARAM_TOP_K)
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS_RELATIONSHIP_ARTICLE', LLMsConfig.PARAM_MAX_NEW_TOKENS)
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE_RELATIONSHIP_ARTICLE', LLMsConfig.PARAM_DO_SAMPLE)
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY_RELATIONSHIP_ARTICLE', LLMsConfig.PARAM_REPETITION_PENALTY)
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL_RELATIONSHIP_ARTICLE')

    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA_RELATIONSHIP_ARTICLE', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK_RELATIONSHIP_ARTICLE', 'false').lower() == 'true'


# ==================== CLASSIFICATION LLMs CONFIGURATION ====================
class LLMsConfigExtractClassification(LLMsConfig):
    LLMS_BASE_URL: Final[str] = os.getenv('LLMS_BASE_URL_CLASSIFICATION', LLMsConfig.LLMS_BASE_URL)        
    LLMS_BATCH: Final[int] = int(os.getenv('LLMS_BATCH_CLASSIFICATION', LLMsConfig.LLMS_BATCH))
    LLMS_MODEL_NAME: Final[str] = os.getenv('LLMS_MODEL_NAME_CLASSIFICATION', LLMsConfig.LLMS_MODEL_NAME)        

    PARAM_CONTENT: Final[str] = os.getenv('PARAM_CONTENT_CLASSIFICATION', LLMsConfig.PARAM_CONTENT)        
    PARAM_TEMPERATURE: Final[float] = os.getenv('PARAM_TEMPERATURE_CLASSIFICATION', LLMsConfig.PARAM_TEMPERATURE)
    PARAM_TOP_P: Final[float] = os.getenv('PARAM_TOP_P_CLASSIFICATION', LLMsConfig.PARAM_TOP_P)
    PARAM_TOP_K: Final[int] = os.getenv('PARAM_TOP_K_CLASSIFICATION', LLMsConfig.PARAM_TOP_K)
    PARAM_MAX_NEW_TOKENS: Final[int] = os.getenv('PARAM_MAX_NEW_TOKENS_CLASSIFICATION', LLMsConfig.PARAM_MAX_NEW_TOKENS)
    PARAM_DO_SAMPLE: Final[str] = os.getenv('PARAM_DO_SAMPLE_CLASSIFICATION', LLMsConfig.PARAM_DO_SAMPLE)
    PARAM_REPETITION_PENALTY: Final[float] = os.getenv('PARAM_REPETITION_PENALTY_CLASSIFICATION', LLMsConfig.PARAM_REPETITION_PENALTY)
    LLMS_OLLAMA_BASE_URL: Final[str] = os.getenv('LLMS_OLLAMA_BASE_URL_CLASSIFICATION')
    
    USE_OLLAMA: Final[bool] = os.getenv('USE_OLLAMA_CLASSIFICATION', 'false').lower() == 'true'
    NO_THINK: Final[bool] = os.getenv('NO_THINK_CLASSIFICATION', 'false').lower() == 'true'


class EmbeddingConfig:
    DEFAULT_MODEL_EMBEDDING: Final[str] = os.getenv('DEFAULT_MODEL_EMBEDDING')            
    DEFAULT_COLLECTION: Final[str] = os.getenv('DEFAULT_COLLECTION')            
    MAX_CHUNK_SIZE: Final[int] = int(os.getenv('MAX_CHUNK_SIZE'))
    TOP_K: Final[int] = int(os.getenv('TOP_K'))
    THRESHOLD: Final[float] = float(os.getenv('THRESHOLD'))


class PreprocessTopics:
    # Extract keywords
    EXTRACT_KEYWORD_QUERY_TOPIC: Final[str] = os.getenv('EXTRACT_KEYWORD_QUERY_TOPIC', 'v03_EXTRACT_KEYWORD_QUERY_TOPIC_DEV')
    EXTRACT_KEYWORD_RESPONSE_TOPIC: Final[str] = os.getenv('EXTRACT_KEYWORD_RESPONSE_TOPIC', 'v03_EXTRACT_KEYWORD_RESPONSE_TOPIC_DEV')
    EXTRACT_KEYWORD_GROUP: Final[str] = os.getenv('EXTRACT_KEYWORD_GROUP', 'v03_group_extract_keywords_dev')

    # Extract metadata
    EXTRACT_METADATA_QUERY_TOPIC: Final[str] = os.getenv('EXTRACT_METADATA_QUERY_TOPIC', 'v03_EXTRACT_METADATA_QUERY_TOPIC_DEV')
    EXTRACT_METADATA_RESPONSE_TOPIC: Final[str] = os.getenv('EXTRACT_METADATA_RESPONSE_TOPIC', 'v03_EXTRACT_METADATA_RESPONSE_TOPIC_DEV')
    EXTRACT_METADATA_GROUP: Final[str] = os.getenv('EXTRACT_METADATA_GROUP', 'v03_group_extract_metadata_dev')

    # Extract relationship
    EXTRACT_RELATIONSHIP_QUERY_TOPIC: Final[str] = os.getenv('EXTRACT_RELATIONSHIP_QUERY_TOPIC', 'v03_EXTRACT_RELATIONSHIP_QUERY_TOPIC_DEV')
    EXTRACT_RELATIONSHIP_RESPONSE_TOPIC: Final[str] = os.getenv('EXTRACT_RELATIONSHIP_RESPONSE_TOPIC', 'v03_EXTRACT_RELATIONSHIP_RESPONSE_TOPIC_DEV')
    EXTRACT_RELATIONSHIP_GROUP: Final[str] = os.getenv('EXTRACT_RELATIONSHIP_GROUP', 'v03_group_extract_relationship_dev')
        
    # Article to article relationship extraction
    EXTRACT_ARTICLE_RELATIONSHIP_QUERY_TOPIC: Final[str] = os.getenv('EXTRACT_ARTICLE_RELATIONSHIP_QUERY_TOPIC', 'v03_EXTRACT_ARTICLE_RELATIONSHIP_QUERY_TOPIC_DEV')
    EXTRACT_ARTICLE_RELATIONSHIP_RESPONSE_TOPIC: Final[str] = os.getenv('EXTRACT_ARTICLE_RELATIONSHIP_RESPONSE_TOPIC', 'v03_EXTRACT_ARTICLE_RELATIONSHIP_RESPONSE_TOPIC_DEV')
    EXTRACT_ARTICLE_RELATIONSHIP_GROUP: Final[str] = os.getenv('EXTRACT_ARTICLE_RELATIONSHIP_GROUP', 'v03_group_extract_article_relationship_dev')
    
    # Subject of regulation extraction  
    EXTRACT_REGULATED_ENTITIES_QUERY_TOPIC: Final[str] = os.getenv('EXTRACT_REGULATED_ENTITIES_QUERY_TOPIC', 'v03_EXTRACT_REGULATED_ENTITIES_QUERY_TOPIC_DEV')
    EXTRACT_REGULATED_ENTITIES_RESPONSE_TOPIC: Final[str] = os.getenv('EXTRACT_REGULATED_ENTITIES_RESPONSE_TOPIC', 'v03_EXTRACT_REGULATED_ENTITIES_RESPONSE_TOPIC_DEV')
    EXTRACT_REGULATED_ENTITIES_GROUP: Final[str] = os.getenv('EXTRACT_REGULATED_ENTITIES_GROUP', 'v03_group_extract_regulation_subject_dev')
    
    # Social relationship extraction
    EXTRACT_SOCIAL_RELATION_QUERY_TOPIC: Final[str] = os.getenv('EXTRACT_SOCIAL_RELATION_QUERY_TOPIC', 'v03_EXTRACT_SOCIAL_RELATIONSHIP_QUERY_TOPIC_DEV')
    EXTRACT_SOCIAL_RELATION_RESPONSE_TOPIC: Final[str] = os.getenv('EXTRACT_SOCIAL_RELATION_RESPONSE_TOPIC', 'v03_EXTRACT_SOCIAL_RELATIONSHIP_RESPONSE_TOPIC_DEV')
    EXTRACT_SOCIAL_RELATION_GROUP: Final[str] = os.getenv('EXTRACT_SOCIAL_RELATION_GROUP', 'v03_group_extract_social_relationship_dev')
    
    # Law authority extraction
    EXTRACT_LAW_AUTHORITY_QUERY_TOPIC: Final[str] = os.getenv('EXTRACT_LAW_AUTHORITY_QUERY_TOPIC', 'v03_EXTRACT_LAW_AUTHORITY_QUERY_TOPIC_DEV')
    EXTRACT_LAW_AUTHORITY_RESPONSE_TOPIC: Final[str] = os.getenv('EXTRACT_LAW_AUTHORITY_RESPONSE_TOPIC', 'v03_EXTRACT_LAW_AUTHORITY_RESPONSE_TOPIC_DEV')
    EXTRACT_LAW_AUTHORITY_GROUP: Final[str] = os.getenv('EXTRACT_LAW_AUTHORITY_GROUP', 'v03_group_extract_law_authority_dev')
    
    # Law index to elastic
    INDEX_ELASTIC_QUERY_TOPIC: Final[str] = os.getenv('INDEX_ELASTIC_QUERY_TOPIC', 'v03_INDEX_ELASTIC_QUERY_TOPIC_DEV')
    INDEX_ELASTIC_GROUP: Final[str] = os.getenv('INDEX_ELASTIC_GROUP', 'v03_group_index_elastic_dev')

    # Law index title to qrant
    TITLE_EMBEDDING_QUERY_TOPIC: Final[str] = os.getenv('TITLE_EMBEDDING_QUERY_TOPIC', 'v03_TITLE_EMBEDDING_QUERY_TOPIC_DEV')
    TITLE_EMBEDDING_GROUP: Final[str] = os.getenv('TITLE_EMBEDDING_GROUP', 'v03_index_qdrant_title_dev')

    # Law index content to qrant
    CONTENT_EMBEDDING_QUERY_TOPIC: Final[str] = os.getenv('CONTENT_EMBEDDING_QUERY_TOPIC', 'v03_CONTENT_EMBEDDING_QUERY_TOPIC_DEV')
    CONTENT_EMBEDDING_GROUP: Final[str] = os.getenv('CONTENT_EMBEDDING_GROUP', 'v03_content_embedding_group_dev')

    # Law index article to qrant
    ARTICLE_EMBEDDING_QUERY_TOPIC: Final[str] = os.getenv('ARTICLE_EMBEDDING_QUERY_TOPIC', 'v03_ARTICLE_EMBEDDING_QUERY_TOPIC_DEV')
    ARTICLE_EMBEDDING_GROUP: Final[str] = os.getenv('ARTICLE_EMBEDDING_GROUP', 'v03_article_embedding_group_dev')

    # Classification Article
    CLASSIFICATION_ARTICLE_QUERY_TOPIC: Final[str] = os.getenv('CLASSIFICATION_ARTICLE_QUERY_TOPIC', 'v03_CLASSIFICATION_ARTICLE_QUERY_TOPIC_DEV')
    CLASSIFICATION_ARTICLE_GROUP: Final[str] = os.getenv('CLASSIFICATION_ARTICLE_GROUP', 'v03_classification_article_group_dev')


class MigrateConfig:    
    MIGRATE_RAW_DB: Final[str] = os.getenv('MIGRATE_RAW_DB', 'vo3_standardize_210425')
    MIGRATE_CORE_DB: Final[str] = os.getenv('MIGRATE_CORE_DB', 'v03_core_210425')
    MIGRATE_CRAWLER_DB: Final[str] = os.getenv('MIGRATE_CRAWLER_DB', 'law_ai_crawler')

    MIGRATE_EMBEDDING: Final[str] = os.getenv('MIGRATE_EMBEDDING', 'dekEmbedding')
    MIGRATE_EMBEDDING_LONG_CONTEXT: Final[str] = os.getenv('MIGRATE_EMBEDDING_LONG_CONTEXT', 'vietnameseEmbeddingLongContext')
    MIGRATE_EMBEDDING_VERSION: Final[str] = os.getenv('MIGRATE_EMBEDDING_VERSION', '1_0')
    MIGRATE_EMBEDDING_KNOWLEDGE_NAME: Final[str] = os.getenv('MIGRATE_EMBEDDING_KNOWLEDGE_NAME', 'LawAI_V03_Clauds_Level_{MODEL}_{VERSION}')
    MIGRATE_EMBEDDING_STATUS_FIELD: Final[str] = os.getenv('MIGRATE_EMBEDDING_STATUS_FIELD', 'is_in_LawAI_V03_Clauds_Level_{MODEL}_{VERSION}')    
    MIGRATE_EMBEDDING_MAX_WORKERS: Final[int] = os.getenv('MIGRATE_EMBEDDING_MAX_WORKERS', 50)
    MIGRATE_EMBEDDING_EMBEDDING_SIZE: Final[int] = os.getenv('MIGRATE_EMBEDDING_EMBEDDING_SIZE', 768)
    
    MIGRATE_EMBEDDING_SENTENCE_LEVEL: Final[str] = os.getenv('MIGRATE_EMBEDDING_SENTENCE_LEVEL', 'vietnameseEmbedding')    
    MIGRATE_EMBEDDING_KNOWLEDGE_NAME_SENTENCE_LEVEL: Final[str] = os.getenv('MIGRATE_EMBEDDING_KNOWLEDGE_NAME_SENTENCE_LEVEL', 'LawAI_V03_Sentences_Level_{MODEL}_{VERSION}')
    MIGRATE_EMBEDDING_STATUS_FIELD_SENTENCE_LEVEL: Final[str] = os.getenv('MIGRATE_EMBEDDING_STATUS_FIELD_SENTENCE_LEVEL', 'is_in_LawAI_V03_Sentences_Level_{MODEL}_{VERSION}')    
    
    MIGRATE_CLASSIFY_ARTICLE_LEVEL: Final[str] = os.getenv('MIGRATE_CLASSIFY_ARTICLE_LEVEL', 'QwQ_32B_Version_1')
    MIGRATE_CLASSIFY_ARTICLE_LEVEL_OLLAMA: Final[str] = os.getenv('MIGRATE_CLASSIFY_ARTICLE_LEVEL_OLLAMA', 'Qwen3_30B_Version_1')
    MIGRATE_CLASSIFY_CLAUD_LEVEL: Final[str] = os.getenv('MIGRATE_CLASSIFY_CLAUD_LEVEL', 'QwQ_32B_Version_1')

    MIGRATE_EMBEDDING_KNOWLEDGE_TITLE: Final[str] = os.getenv('MIGRATE_EMBEDDING_KNOWLEDGE_TITLE', 'V03_Doc_Titles_vietnameseEmbedding_1_1')
    MIGRATE_EMBEDDING_KNOWLEDGE_SENTENCE: Final[str] = os.getenv('MIGRATE_EMBEDDING_KNOWLEDGE_SENTENCE', 'LawAI_V03_Sentences_Level_vietnameseEmbedding_1_5_Name')
    MIGRATE_EMBEDDING_KNOWLEDGE_ARTICLE: Final[str] = os.getenv('MIGRATE_EMBEDDING_KNOWLEDGE_ARTICLE', 'LawAI_V03_Clauds_Level_dekEmbedding_1_5')
    MIGRATE_EMBEDDING_MODEL_TITLE: Final[str] = os.getenv('MIGRATE_EMBEDDING_MODEL_TITLE', 'vietnameseEmbedding')
    MIGRATE_EMBEDDING_MODEL_SENTENCE: Final[str] = os.getenv('MIGRATE_EMBEDDING_MODEL_SENTENCE', 'vietnameseEmbedding')
    MIGRATE_EMBEDDING_MODEL_ARTICLE: Final[str] = os.getenv('MIGRATE_EMBEDDING_MODEL_ARTICLE', 'dekEmbedding')

class ElasticConfig:
    ELASTIC_HOST: Final[str] = os.getenv('ELASTIC_HOST')
    ELASTIC_USERNAME: Final[str] = os.getenv('ELASTIC_USERNAME', '')
    ELASTIC_PASSWORD: Final[str] = os.getenv('ELASTIC_PASSWORD', '')
    ELASTIC_INDEX: Final[str] = os.getenv('ELASTIC_INDEX')
    ELASTIC_INDEX_CORE: Final[str] = os.getenv('ELASTIC_INDEX_CORE')
    
class ImportTreeConfig:
    PARENT_FIELD: Final[str] = os.getenv('PARENT_FIELD', 'Cấp cha')
    CHILD_FIELD: Final[str] = os.getenv('CHILD_FIELD', 'Cấp con')
    NAME_FIELD: Final[str] = os.getenv('NAME_FIELD', 'Văn bản thuộc nội dung của đề mục')

    IMPORT_TREE_QUERY_TOPIC: Final[str] = os.getenv('IMPORT_TREE_QUERY_TOPIC', 'MANAGE_TREE_QUERY_TOPIC_DEV')
    IMPORT_TREE_RESPONSE_TOPIC: Final[str] = os.getenv('IMPORT_TREE_RESPONSE_TOPIC', 'MANAGE_TREE_RESPONSE_TOPIC_DEV')
    IMPORT_TREE_GROUP: Final[str] = os.getenv('IMPORT_TREE_GROUP', 'group_import_tree_dev')
    
class MinioConfig:
    ENDPOINT: Final[str] = os.getenv('MINIO_ENDPOINT')
    ACCESS_KEY: Final[str] = os.getenv('MINIO_ACCESS_KEY')
    SECRET_KEY: Final[str] = os.getenv('MINIO_SECRET_KEY')
    DEFAULT_BUCKET_NAME: Final[str] = os.getenv('MINIO_BUCKET_NAME')
    UPLOAD_BUCKET_NAME: Final[str] = os.getenv('MINIO_UPLOAD_BUCKET_NAME')

class SignalRConfig:
    API_URL: Final[str] = os.getenv('SIGNALR_API_URL', 'http://192.168.1.200:5097/broadcast')
    
    UPLOAD_TOPIC: Final[str] = os.getenv('SIGNALR_UPLOAD_TOPIC', 'V03_UPLOAD_RECORD_TOPIC_DEV')
    IMPORT_TREE_TOPIC: Final[str] = os.getenv('SIGNALR_IMPORT_TREE_TOPIC', 'V03_IMPORT_TREE_TOPIC_DEV')
    TREE_CLASSIFIER_TOPIC: Final[str] = os.getenv('SIGNALR_TREE_CLASSIFIER_TOPIC', 'CORE_TREE_CLASSIFIER_TOPIC_v0')
    

# ==================== VALIDATION TOPICS ====================
class ValidationTopics:
    VALIDATE_CONTENT_QUERY_TOPIC: Final[str] = os.getenv('VALIDATE_CONTENT_QUERY_TOPIC')
    VALIDATE_CONTENT_RESPONSE_TOPIC: Final[str] = os.getenv('VALIDATE_CONTENT_RESPONSE_TOPIC')
    VALIDATE_CONTENT_GROUP: Final[str] = os.getenv('VALIDATE_CONTENT_GROUP')

    VALIDATE_EFFECT_QUERY_TOPIC: Final[str] = os.getenv('VALIDATE_EFFECT_QUERY_TOPIC')
    VALIDATE_EFFECT_RESPONSE_TOPIC: Final[str] = os.getenv('VALIDATE_EFFECT_RESPONSE_TOPIC')
    VALIDATE_EFFECT_GROUP: Final[str] = os.getenv('VALIDATE_EFFECT_GROUP')

    VALIDATE_ROLE_QUERY_TOPIC: Final[str] = os.getenv('VALIDATE_ROLE_QUERY_TOPIC')
    VALIDATE_ROLE_RESPONSE_TOPIC: Final[str] = os.getenv('VALIDATE_ROLE_RESPONSE_TOPIC')
    VALIDATE_ROLE_GROUP: Final[str] = os.getenv('VALIDATE_ROLE_GROUP')

    VALIDATE_BASE_QUERY_TOPIC: Final[str] = os.getenv('VALIDATE_BASE_QUERY_TOPIC')
    VALIDATE_BASE_RESPONSE_TOPIC: Final[str] = os.getenv('VALIDATE_BASE_RESPONSE_TOPIC')
    VALIDATE_BASE_GROUP: Final[str] = os.getenv('VALIDATE_BASE_GROUP')

    VALIDATE_AUTHORITY_QUERY_TOPIC: Final[str] = os.getenv('VALIDATE_AUTHORITY_QUERY_TOPIC')
    VALIDATE_AUTHORITY_RESPONSE_TOPIC: Final[str] = os.getenv('VALIDATE_AUTHORITY_RESPONSE_TOPIC')
    VALIDATE_AUTHORITY_GROUP: Final[str] = os.getenv('VALIDATE_AUTHORITY_GROUP')

    VALIDATE_SOCIAL_RELATION_QUERY_TOPIC: Final[str] = os.getenv('VALIDATE_SOCIAL_RELATION_QUERY_TOPIC')
    VALIDATE_SOCIAL_RELATION_RESPONSE_TOPIC: Final[str] = os.getenv('VALIDATE_SOCIAL_RELATION_RESPONSE_TOPIC')
    VALIDATE_SOCIAL_RELATION_GROUP: Final[str] = os.getenv('VALIDATE_SOCIAL_RELATION_GROUP')
    
    VALIDATE_REGULATED_OBJECT_QUERY_TOPIC: Final[str] = os.getenv('VALIDATE_REGULATED_OBJECT_QUERY_TOPIC')
    VALIDATE_REGULATED_OBJECT_RESPONSE_TOPIC: Final[str] = os.getenv('VALIDATE_REGULATED_OBJECT_RESPONSE_TOPIC')
    VALIDATE_REGULATED_OBJECT_GROUP: Final[str] = os.getenv('VALIDATE_REGULATED_OBJECT_GROUP')
    
        
    USE_OLLAMA: Final[str] = os.getenv('USE_OLLAMA_VALIDATION', True)


class MongoDBCollectionConfig:
    LAW_DOCUMENT_COLLECTION_NAME: Final[str] = os.getenv('LAW_DOCUMENT_COLLECTION_NAME', 'law_documents')
    LAW_ARTICLE_COLLECTION_NAME: Final[str] = os.getenv('LAW_ARTICLE_COLLECTION_NAME', 'law_articles')
    LAW_CLAUSE_COLLECTION_NAME: Final[str] = os.getenv('LAW_CLAUSE_COLLECTION_NAME', 'law_clauses')
    LAW_DOCUMENT_TYPE_COLLECTION_NAME: Final[str] = os.getenv('LAW_DOCUMENT_TYPE_COLLECTION_NAME', 'law_doc_types')
    LAW_DOCUMENT_CATEGORY_COLLECTION_NAME: Final[str] = os.getenv('LAW_DOCUMENT_CATEGORY_COLLECTION_NAME', 'law_doc_category')
    LAW_ARTICLE_CLASS_COLLECTION_NAME: Final[str] = os.getenv('LAW_ARTICLE_CLASS_COLLECTION_NAME', 'law_article_class')
    LAW_REFERENCE_ARTICLE_COLLECTION_NAME: Final[str] = os.getenv('LAW_REFERENCE_ARTICLE_COLLECTION_NAME', 'law_references_article')
    # Draft article references: cross-document references whose target document is
    # NOT in the DB (mapping_document failed). Stored with raw display fields
    # (target_doc_name / target_doc_code) so the FE can render them directly.
    LAW_REFERENCE_ARTICLE_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_REFERENCE_ARTICLE_DRAFT_COLLECTION_NAME', 'law_references_article_draft')
    LAW_REFERENCE_COLLECTION_NAME: Final[str] = os.getenv('LAW_REFERENCE_COLLECTION_NAME', 'law_references')
    LAW_CORE_MODELS_COLLECTION_NAME: Final[str] = os.getenv('LAW_CORE_MODELS_COLLECTION_NAME', 'law_core_models')
    LAW_RELATIONSHIP_ARTICLE_COLLECTION_NAME: Final[str] = os.getenv('LAW_RELATIONSHIP_ARTICLE_COLLECTION_NAME', 'law_relationship_article')
    LAW_RELATIONSHIP_DOCUMENT_COLLECTION_NAME: Final[str] = os.getenv('LAW_RELATIONSHIP_DOCUMENT_COLLECTION_NAME', 'law_relationship_document')

    LAW_TREE_COLLECTION_NAME: Final[str] = os.getenv('LAW_TREE_COLLECTION_NAME', 'law_tree')
    LAW_TREE_COMPONENT_COLLECTION_NAME: Final[str] = os.getenv('LAW_TREE_COMPONENT_COLLECTION_NAME', 'law_tree_component')
    LAW_KEYWORD_COLLECTION_NAME: Final[str] = os.getenv('LAW_KEYWORD_COLLECTION_NAME', 'law_keywords')
    LAW_REGULATED_OBJECT_COLLECTION_NAME: Final[str] = os.getenv('LAW_REGULATED_OBJECT_COLLECTION_NAME', 'law_regulated_object')
    LAW_REGULATED_OBJECT_MAPPING_COLLECTION_NAME: Final[str] = os.getenv('LAW_REGULATED_OBJECT_MAPPING_COLLECTION_NAME', 'law_regulated_object_mapping')

    LAW_AGENCIES_COLLECTION_NAME: Final[str] = os.getenv('LAW_AGENCIES_COLLECTION_NAME', 'law_agencies')
    LAW_ASSIGNED_SCOPE_COLLECTION_NAME: Final[str] = os.getenv('LAW_ASSIGNED_SCOPE_COLLECTION_NAME', 'law_assigned_scope')
    LAW_AUTHORITY_COLLECTION_NAME: Final[str] = os.getenv('LAW_AUTHORITY_COLLECTION_NAME', 'law_authority')
    LAW_AUTHORITY_MAPPING_COLLECTION_NAME: Final[str] = os.getenv('LAW_AUTHORITY_MAPPING_COLLECTION_NAME', 'law_authority_mapping')
    LAW_SOCIAL_RELATION_COLLECTION_NAME: Final[str] = os.getenv('LAW_SOCIAL_RELATION_COLLECTION_NAME', 'law_social_relation')
    LAW_SOCIAL_RELATION_MAPPING_COLLECTION_NAME: Final[str] = os.getenv('LAW_SOCIAL_RELATION_MAPPING_COLLECTION_NAME', 'law_social_relation_mapping')
    LAW_SOCIAL_RELATION_GROUP_COLLECTION_NAME: Final[str] = os.getenv('LAW_SOCIAL_RELATION_GROUP_COLLECTION_NAME', 'law_social_relation_group')
    LAW_ISSUING_LEVEL_COLLECTION_NAME: Final[str] = os.getenv('LAW_ISSUING_LEVEL_COLLECTION_NAME', 'law_issuing_level')
    LAW_SIGNERS_COLLECTION_NAME: Final[str] = os.getenv('LAW_SIGNERS_COLLECTION_NAME', 'law_signers')
    LAW_POSITIONS_COLLECTION_NAME: Final[str] = os.getenv('LAW_POSITIONS_COLLECTION_NAME', 'law_positions')
    LAW_INDUSTRY_SECTORS_COLLECTION_NAME: Final[str] = os.getenv('LAW_INDUSTRY_SECTORS_COLLECTION_NAME', 'law_industry_sectors') 
    LAW_DECREE_STATUS_COLLECTION_NAME: Final[str] = os.getenv('LAW_DECREE_STATUS_COLLECTION_NAME', 'law_decree_status')
    LAW_EFFECTIVE_STATUS_COLLECTION_NAME: Final[str] = os.getenv('LAW_EFFECTIVE_STATUS_COLLECTION_NAME', 'law_effective_status')
    
    LAW_REFERENCE_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_REFERENCE_DRAFT_COLLECTION_NAME', 'law_reference_draft')
    LAW_ARTICLE_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_ARTICLE_DRAFT_COLLECTION_NAME', 'law_articles_draft')
    LAW_SOCIAL_RELATION_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_SOCIAL_RELATION_DRAFT_COLLECTION_NAME', 'law_social_relation_draft')
    LAW_SOCIAL_RELATION_MAPPING_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_SOCIAL_RELATION_MAPPING_DRAFT_COLLECTION_NAME', 'law_social_relation_mapping_draft')
    LAW_REGULATED_OBJECT_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_REGULATED_OBJECT_DRAFT_COLLECTION_NAME', 'law_regulated_object_draft')
    LAW_REGULATED_OBJECT_MAPPING_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_REGULATED_OBJECT_MAPPING_DRAFT_COLLECTION_NAME', 'law_regulated_object_mapping_draft')
    LAW_AUTHORITY_STATUS_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_AUTHORITY_STATUS_DRAFT_COLLECTION_NAME', 'law_authority_status_draft')
    LAW_AUTHORITY_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_AUTHORITY_DRAFT_COLLECTION_NAME', 'law_authority_draft')
    LAW_AUTHORITY_MAPPING_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_AUTHORITY_MAPPING_DRAFT_COLLECTION_NAME', 'law_authority_mapping_draft')
    LAW_REFERENCES_ARTICLE_DRAFT_COLLECTION_NAME: Final[str] = os.getenv('LAW_REFERENCES_ARTICLE_DRAFT_COLLECTION_NAME', 'law_references_article_draft')
    LAW_EFFECTIVE_STATUS_COLLECTION_NAME: Final[str] = os.getenv('LAW_EFFECTIVE_STATUS_COLLECTION_NAME', 'law_effective_status')
    LAW_PROCESS_MANAGE_COLLECTION_NAME: Final[str] = os.getenv('LAW_PROCESS_MANAGE_COLLECTION_NAME', 'law_process_manage')
    
    PIPELINE_DOCUMENT_STATE_COLLECTION_NAME: Final[str] = os.getenv('PIPELINE_DOCUMENT_STATE_COLLECTION_NAME', 'pipeline_document_state')
    PIPELINE_ARTICLE_STATE_COLLECTION_NAME: Final[str] = os.getenv('PIPELINE_ARTICLE_STATE_COLLECTION_NAME', 'pipeline_article_state')    

    BIZ_UPLOAD_RECORD_COLLECTION_NAME: Final[str] = os.getenv('BIZ_UPLOAD_RECORD_COLLECTION_NAME', 'biz_upload_record')
    BIZ_UPLOAD_DOCUMENTS_COLLECTION_NAME: Final[str] = os.getenv('BIZ_UPLOAD_DOCUMENTS_COLLECTION_NAME', 'biz_upload_documents')
    BIZ_UPLOAD_ARTICLES_COLLECTION_NAME: Final[str] = os.getenv('BIZ_UPLOAD_ARTICLES_COLLECTION_NAME', 'biz_upload_articles')
    BIZ_EXTRACT_ARTICLES_STATUS_COLLECTION_NAME: Final[str] = os.getenv('BIZ_EXTRACT_ARTICLES_STATUS_COLLECTION_NAME', 'biz_extract_articles_status')
    BIZ_EXTRACT_ARTICLES_TYPE_COLLECTION_NAME: Final[str] = os.getenv('BIZ_EXTRACT_ARTICLES_TYPE_COLLECTION_NAME', 'biz_extract_articles_type')
    BIZ_REVIEW_RECORDS_COLLECTION_NAME: Final[str] = os.getenv('BIZ_REVIEW_RECORDS_COLLECTION_NAME', 'biz_review_records')
    BIZ_SUMMARY_COLLECTION_NAME: Final[str] = os.getenv('BIZ_SUMMARY_COLLECTION_NAME', 'biz_summary')
    BIZ_TRAINING_PROCESS_COLLECTION_NAME: Final[str] = os.getenv('BIZ_TRAINING_PROCESS_COLLECTION_NAME', 'biz_training_process')
    
    LAW_DOCUMENT_STORAGE_COLLECTION_NAME: Final[str] = os.getenv('LAW_DOCUMENT_STORAGE_COLLECTION_NAME', 'law_document_storage')
    RAW_DOCUMENTS_SEGMENTS_COLLECTION_NAME: Final[str] = os.getenv('RAW_DOCUMENTS_SEGMENTS_COLLECTION_NAME', 'document_segment')
class RecommendDocumentConfig:
    RECOMMEND_TYPE: Final[list] = os.getenv('RECOMMEND_TYPE', ['TYPE_1', 'TYPE_2', 'TYPE_3', 'TYPE_4', 'TYPE_5'])

class RelationshipConfig:
    VALID_RELATION_TYPES: Final[list] = [
        'replace', 
        'repeal_full', 
        'repeal_apart', 
        'amend', 
        'add', 
        'base', 
        'detail'
    ]

class ExtractBatchConfig:
    SOCIAL_RELATION_BATCH_SIZE: Final[int] = int(os.getenv('SOCIAL_RELATION_BATCH_SIZE', '20'))
    RELATIONSHIP_BATCH_SIZE: Final[int] = int(os.getenv('RELATIONSHIP_BATCH_SIZE', '20'))
    RELATIONSHIP_ARTICLE_BATCH_SIZE: Final[int] = int(os.getenv('RELATIONSHIP_ARTICLE_BATCH_SIZE', '20'))
    LAW_AUTHORITY_BATCH_SIZE: Final[int] = int(os.getenv('LAW_AUTHORITY_BATCH_SIZE', '20'))
    KEYWORD_BATCH_SIZE: Final[int] = int(os.getenv('KEYWORD_BATCH_SIZE', '20'))
    REGULATED_OBJECT_BATCH_SIZE: Final[int] = int(os.getenv('REGULATED_OBJECT_BATCH_SIZE', '20'))
    METADATA_BATCH_SIZE: Final[int] = int(os.getenv('METADATA_BATCH_SIZE', '20'))