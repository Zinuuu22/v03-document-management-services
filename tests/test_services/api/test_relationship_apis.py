import os
import sys
import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime
from flask import Flask
from flask_restful import Api
from bson import ObjectId
import json

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

# Import the API resources to test
from services.api.biz.relationship import (
    RelationshipDraftGetAPI, RelationshipDraftAddAPI, 
    RelationshipDraftUpdateAPI, RelationshipDraftDeleteAPI,
    ArticleRelationshipGetAPI, ArticleRelationshipCreateAPI,
    ArticleRelationshipUpdateAPI, ArticleRelationshipDeleteAPI,
    DocumentRelationshipGetAPI, DocumentRelationshipCreateAPI,
    DocumentRelationshipUpdateAPI, DocumentRelationshipDeleteAPI
)


# Import MongoDB collections
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig

# Test data
TEST_DRAFT_ID = "test_draft_123"
TEST_ARTICLE_RELATIONSHIP_ID = str(ObjectId())
TEST_DOCUMENT_REFERENCE_ID = str(ObjectId())

# Mock MongoDB collections
mock_biz_upload_documents = MagicMock()
mock_law_references_article = MagicMock()
mock_law_references = MagicMock()

# Mock the database and collections
mock_db = MagicMock()
mock_db.biz_upload_documents = mock_biz_upload_documents
mock_db.law_references_article = mock_law_references_article
mock_db.law_references = mock_law_references

# Mock the MongoDB client
mock_client = MagicMock()
mock_client.__getitem__.return_value = mock_db

# Create test Flask app
def create_test_app():
    app = Flask(__name__)
    app.testing = True
    api = Api(app)
    
    # Add resources
    api.add_resource(RelationshipDraftGetAPI, '/relationship-draft/get/<string:idOrCode>')
    api.add_resource(RelationshipDraftAddAPI, '/relationship-draft/add/<string:idOrCode>')
    api.add_resource(RelationshipDraftUpdateAPI, '/relationship-draft/update/<string:idOrCode>')
    api.add_resource(RelationshipDraftDeleteAPI, '/relationship-draft/delete/<string:idOrCode>')
    
    api.add_resource(ArticleRelationshipGetAPI, '/article-relationship/get/<string:relationship_id>')
    api.add_resource(ArticleRelationshipCreateAPI, '/article-relationship/create')
    api.add_resource(ArticleRelationshipUpdateAPI, '/article-relationship/update/<string:relationship_id>')
    api.add_resource(ArticleRelationshipDeleteAPI, '/article-relationship/delete/<string:relationship_id>')
    
    api.add_resource(DocumentRelationshipGetAPI, '/document-relationship/get/<string:reference_id>')
    api.add_resource(DocumentRelationshipCreateAPI, '/document-relationship/create')
    api.add_resource(DocumentRelationshipUpdateAPI, '/document-relationship/update/<string:reference_id>')
    api.add_resource(DocumentRelationshipDeleteAPI, '/document-relationship/delete/<string:reference_id>')
    
    return app

# Fixtures
@pytest.fixture
def client():
    app = create_test_app()
    with app.test_client() as client:
        with app.app_context():
            yield client

# Helper functions
def get_mock_draft_document():
    return {
        'record_id': TEST_DRAFT_ID,
        'replace': ['doc1', 'doc2'],
        'repeal_full': ['doc3'],
        'repeal_apart': [],
        'amend': ['doc4'],
        'add': [],
        'base': ['doc5'],
        'detail': ['doc6'],
        'decree_status': 'CÓ HIỆU LỰC',
        'created_date': '2023-01-01T00:00:00',
        'last_modified_by': 'test_user'
    }

def get_mock_article_relationship():
    return {
        '_id': ObjectId(TEST_ARTICLE_RELATIONSHIP_ID),
        'relationship_id': TEST_ARTICLE_RELATIONSHIP_ID,
        'source_doc_id': 'source_doc_1',
        'source_article_id': 'article_1',
        'target_doc_id': 'target_doc_1',
        'target_article_id': 'article_2',
        'relationship_type': 'AMEND',
        'created_by': 'test_user',
        'created_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'ACTIVE'
    }

def get_mock_document_relationship():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        '_id': ObjectId(TEST_DOCUMENT_REFERENCE_ID),
        'reference_id': TEST_DOCUMENT_REFERENCE_ID,
        'source_id': 'source_doc_1',
        'source_type': 'DOCUMENT',
        'target_id': 'target_doc_1',
        'target_type': 'DOCUMENT',
        'reference_type': 'REPLACE',
        'reference_status': 'ACTIVE',
        'created_date': now,
        'last_modified': now,
        'last_modified_by': 'test_user'
    }

# Test classes
class TestDraftRelationshipAPIs:
    def test_get_draft_relationship_success(self, client):
        # Mock the database response
        mock_doc = get_mock_draft_document()
        mock_biz_upload_documents.find_one.return_value = mock_doc
        
        # Make the request
        response = client.get(f'/relationship-draft/get/{TEST_DRAFT_ID}')
        
        # Assertions
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        assert data['data']['code'] == TEST_DRAFT_ID
        assert data['data']['replace'] == mock_doc['replace']
        
    def test_update_draft_relationship_success(self, client):
        # Setup test data
        test_data = {
            'type': 'replace',
            'items': ['new_doc1', 'new_doc2']
        }
        
        # Mock the database responses
        mock_biz_upload_documents.update_one.return_value.matched_count = 1
        mock_biz_upload_documents.find_one.return_value = get_mock_draft_document()
        
        # Make the request
        response = client.post(
            f'/relationship-draft/update/{TEST_DRAFT_ID}',
            json=test_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        mock_biz_upload_documents.update_one.assert_called_once()

    def test_get_nonexistent_draft_relationship(self, client):
        # Mock the database to return None (not found)
        mock_biz_upload_documents.find_one.return_value = None
        
        # Make the request with non-existent ID
        response = client.get('/relationship-draft/get/non_existent_id')
        
        # Assertions
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['code'] == '404'
        assert 'not found' in data['message'].lower()

    def test_update_nonexistent_draft_relationship(self, client):
        # Mock the database to return None (not found)
        mock_biz_upload_documents.find_one.return_value = None
        
        # Test data
        test_data = {
            'type': 'replace',
            'items': ['new_doc1', 'new_doc2']
        }
        
        # Make the request
        response = client.post(
            '/relationship-draft/update/non_existent_id',
            json=test_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['code'] == '404'
        assert 'failed to fetch' in data['message'].lower()

    def test_update_draft_invalid_data(self, client):
        # Test with invalid data (missing required fields)
        invalid_data = {'type': 'invalid_type'}
        
        # Make the request
        response = client.post(
            f'/relationship-draft/update/{TEST_DRAFT_ID}',
            json=invalid_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['code'] == '400'
        assert 'invalid' in data['message'].lower() or 'missing' in data['message'].lower()

class TestArticleRelationshipAPIs:
    def test_get_article_relationship_success(self, client):
        # Mock the database response
        mock_rel = get_mock_article_relationship()
        mock_law_references_article.find_one.return_value = mock_rel
        
        # Make the request
        response = client.get(f'/article-relationship/get/{TEST_ARTICLE_RELATIONSHIP_ID}')
        
        # Assertions
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        assert data['data']['relationship_id'] == TEST_ARTICLE_RELATIONSHIP_ID
        
    def test_create_article_relationship_success(self, client):
        # Test data
        test_data = {
            'relationship_id': 'new_rel_123',
            'source_doc_id': 'source_doc_1',
            'source_article_id': 'article_1',
            'source_clause': 'clause_1',
            'source_point': 'point_1',
            'target_doc_id': 'target_doc_1',
            'target_article_id': 'article_2',
            'target_article': 'Article 1',
            'target_clause': 'clause_1',
            'target_point': 'point_1',
            'relationship_type': 'AMEND',
            'created_by': 'test_user'
        }
        
        # Mock the database response
        mock_law_references_article.find_one.return_value = None
        mock_law_references_article.insert_one.return_value.inserted_id = ObjectId()
        
        # Make the request
        response = client.post(
            '/article-relationship/create',
            json=test_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        mock_law_references_article.insert_one.assert_called_once()

    def test_get_nonexistent_article_relationship(self, client):
        # Mock the database to return None (not found)
        mock_law_references_article.find_one.return_value = None
        
        # Make the request with non-existent ID
        response = client.get('/article-relationship/get/non_existent_id')
        
        # Assertions
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['code'] == '404'
        assert 'not found' in data['message'].lower()

    def test_create_duplicate_article_relationship(self, client):
        # Mock the database to return existing relationship
        mock_law_references_article.find_one.return_value = get_mock_article_relationship()
        
        # Test data with existing relationship_id and all required fields
        test_data = {
            'relationship_id': 'duplicate_id',
            'source_doc_id': 'source_doc_1',
            'source_article_id': 'article_1',
            'source_clause': 'clause_1',
            'source_point': 'point_1',
            'target_doc_id': 'target_doc_1',
            'target_article_id': 'article_2',
            'target_article': 'Article 1',
            'target_clause': 'clause_1',
            'target_point': 'point_1',
            'relationship_type': 'AMEND',
            'created_by': 'test_user'
        }
        
        # Make the request
        response = client.post(
            '/article-relationship/create',
            json=test_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['code'] == '409'
        assert 'already exists' in data['message'].lower()

    def test_create_article_relationship_invalid_data(self, client):
        # Test with invalid data (missing required fields)
        invalid_data = {
            'relationship_id': 'new_rel_123',
            'source_doc_id': 'source_doc_1',
            # Missing required fields
        }
        
        # Make the request
        response = client.post(
            '/article-relationship/create',
            json=invalid_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['code'] == '400'
        assert 'missing' in data['message'].lower() or 'invalid' in data['message'].lower()

class TestDocumentRelationshipAPIs:
    def test_get_document_relationship_success(self, client):
        # Get the mock data
        mock_rel = get_mock_document_relationship()
        
        # Mock the database response
        mock_law_references.find_one.return_value = mock_rel
        
        # Make the request
        response = client.get(f'/document-relationship/get/{TEST_DOCUMENT_REFERENCE_ID}')
        
        # Assertions
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        assert data['data']['reference_id'] == TEST_DOCUMENT_REFERENCE_ID
        assert data['data']['source_id'] == 'source_doc_1'
        assert data['data']['target_id'] == 'target_doc_1'
        assert data['data']['reference_type'] == 'REPLACE'
        assert data['data']['reference_status'] == 'ACTIVE'
        assert 'created_date' in data['data']
        assert 'last_modified' in data['data']
        assert 'last_modified_by' in data['data']
        
    def test_create_document_relationship_success(self, client):
        # Test data
        test_data = {
            'reference_id': 'new_ref_123',
            'source_id': 'source_doc_1',
            'source_type': 'DOCUMENT',
            'target_id': 'target_doc_1',
            'target_type': 'DOCUMENT',
            'reference_type': 'REPLACE',
            'reference_status': 'ACTIVE',
            'last_modified_by': 'test_user'
        }
        
        # Mock the database response
        mock_law_references.find_one.return_value = None
        mock_law_references.insert_one.return_value.inserted_id = ObjectId()
        
        # Make the request
        response = client.post(
            '/document-relationship/create',
            json=test_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        mock_law_references.insert_one.assert_called_once()

    def test_get_nonexistent_document_relationship(self, client):
        # Mock the database to return None (not found)
        mock_law_references.find_one.return_value = None
        
        # Make the request with non-existent ID
        response = client.get('/document-relationship/get/non_existent_id')
        
        # Assertions
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['code'] == '404'
        assert 'not found' in data['message'].lower()

    def test_create_duplicate_document_relationship(self, client):
        # Mock the database to return existing relationship
        mock_law_references.find_one.return_value = get_mock_document_relationship()
        
        # Test data with existing reference_id
        test_data = {
            'reference_id': TEST_DOCUMENT_REFERENCE_ID,  # Existing ID
            'source_id': 'source_doc_1',
            'source_type': 'DOCUMENT',
            'target_id': 'target_doc_1',
            'target_type': 'DOCUMENT',
            'reference_type': 'REPLACE',
            'reference_status': 'ACTIVE',
            'last_modified_by': 'test_user'
        }
        
        # Make the request
        response = client.post(
            '/document-relationship/create',
            json=test_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['code'] == '409'
        assert 'already exists' in data['message'].lower()

    def test_create_document_relationship_invalid_data(self, client):
        # Test with invalid data (missing required fields)
        invalid_data = {
            'reference_id': 'new_ref_123',
            # Missing required fields
        }
        
        # Make the request
        response = client.post(
            '/document-relationship/create',
            json=invalid_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['code'] == '400'
        assert 'missing' in data['message'].lower() or 'invalid' in data['message'].lower()

    def test_get_document_relationship_database_error(self, client):
        # Mock database to raise an exception
        mock_law_references.find_one.side_effect = Exception("Database error")
        
        # Make the request
        response = client.get(f'/document-relationship/get/{TEST_DOCUMENT_REFERENCE_ID}')
        
        # Assertions
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['code'] == '500'
        assert 'error' in data['message'].lower()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Mock the database connection in the module under test
@pytest.fixture(autouse=True)
def mock_database_connection(monkeypatch):
    from services.api.biz import relationship
    
    # Mock the database client and collections
    monkeypatch.setattr(relationship, 'client', mock_client)
    monkeypatch.setattr(relationship, 'biz_upload_documents_collection', mock_biz_upload_documents)
    monkeypatch.setattr(relationship, 'law_references_article_collection', mock_law_references_article)
    monkeypatch.setattr(relationship, 'law_references_collection', mock_law_references)
    
    # Mock the add_relationship_to_db function
    monkeypatch.setattr(relationship, 'add_relationship_to_db', lambda x: True)
    
    yield
