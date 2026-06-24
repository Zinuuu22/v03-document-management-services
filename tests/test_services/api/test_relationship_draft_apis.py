import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime
from bson import ObjectId
from flask import Flask
from flask_restful import Api
from pymongo import MongoClient

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

# Import the API resources
from services.api.biz.relationship import (
    RelationshipDraftGetAPI, RelationshipDraftAddAPI, 
    RelationshipDraftUpdateAPI, RelationshipDraftDeleteAPI,
    biz_upload_documents_collection,
    law_references_collection
)


# Test data
TEST_DRAFT_ID = 'DRAFT001'
TEST_DOCUMENT_ID = 'DOC001'
TEST_RELATIONSHIPS = {
    'replace': ['DOC002', 'DOC003'],
    'amend': ['DOC004']
}

# Create test Flask app
def create_test_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Initialize API
    api = Api(app)
    
    # Add resources
    api.add_resource(RelationshipDraftAddAPI, '/relationship-draft/add/<string:idOrCode>')
    api.add_resource(RelationshipDraftUpdateAPI, '/relationship-draft/update/<string:idOrCode>')
    api.add_resource(RelationshipDraftGetAPI, '/relationship-draft/get/<string:idOrCode>')
    api.add_resource(RelationshipDraftDeleteAPI, '/relationship-draft/delete/<string:idOrCode>')
    
    return app

# Fixtures
@pytest.fixture
def mock_mongo(monkeypatch):
    """Fixture to mock MongoDB client and collections."""
    # Create mock collections
    mock_collections = {
        'biz_upload_documents': MagicMock(),
        'law_references': MagicMock()
    }
    
    # Create a mock database that returns our mock collections
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda x: mock_collections[x]
    
    # Set collection attributes directly on the mock_db
    for name, collection in mock_collections.items():
        setattr(mock_db, name, collection)
    
    # Create a mock client that returns our mock database
    mock_client = MagicMock()
    mock_client.__getitem__.side_effect = lambda x: mock_db
    
    # Patch the MongoClient to return our mock client
    with patch('pymongo.MongoClient', return_value=mock_client):
        # Also patch the collection references in the module
        with patch('services.api.biz.relationship.biz_upload_documents_collection', mock_collections['biz_upload_documents']):
            with patch('services.api.biz.relationship.law_references_collection', mock_collections['law_references']):
                # Set default return values for find operations
                mock_collections['biz_upload_documents'].find_one.return_value = None
                mock_collections['biz_upload_documents'].update_one.return_value.matched_count = 1
                mock_collections['biz_upload_documents'].delete_one.return_value.deleted_count = 1
                mock_collections['law_references'].delete_many.return_value.deleted_count = 1
                
                # Yield both the client and the collections for tests to use
                yield {
                    'client': mock_client,
                    'db': mock_db,
                    'collections': mock_collections
                }

@pytest.fixture
def client(mock_mongo):
    # Patch the collections in the module
    with patch('services.api.biz.relationship.biz_upload_documents_collection', mock_mongo['collections']['biz_upload_documents']), \
         patch('services.api.biz.relationship.law_references_collection', mock_mongo['collections']['law_references']):
        
        app = create_test_app()
        with app.test_client() as test_client:
            with app.app_context():
                yield test_client

@pytest.fixture
def mock_db(mock_mongo):
    return mock_mongo

class TestRelationshipDraftAddAPI:
    def test_add_relationships_success(self, client, mock_db):
        # Get mock collections
        mock_docs = mock_db['collections']['biz_upload_documents']
        
        # Setup mock - document doesn't exist yet
        mock_docs.find_one.return_value = None
        mock_docs.insert_one.return_value.inserted_id = 'test_id_123'
        
        # Test data
        test_data = {
            'replace': ['DOC002', 'DOC003'],
            'amend': ['DOC004']
        }
        
        # Make request
        response = client.post(
            f'/relationship-draft/add/{TEST_DRAFT_ID}',
            json=test_data,
            content_type='application/json'
        )
        
        # Assertions
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['code'] == '201'
        assert 'successfully created new draft' in data['message'].lower()
        
        # Verify database calls
        mock_docs.insert_one.assert_called_once()
        
    def test_add_relationships_draft_already_exists(self, client, mock_db):
        # Get mock collections
        mock_docs = mock_db['collections']['biz_upload_documents']
        
        # Setup mock - document already exists
        mock_docs.find_one.return_value = {'record_id': TEST_DRAFT_ID}
        
        # Test data
        test_data = {'replace': ['DOC001']}
        
        # Make request
        response = client.post(
            f'/relationship-draft/add/{TEST_DRAFT_ID}',
            json=test_data,
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['code'] == '409'
        assert 'already exists' in data['message'].lower()
        
    def test_add_relationships_invalid_data(self, client, mock_db):
        # Get mock collections
        mock_docs = mock_db['collections']['biz_upload_documents']
        
        # Setup mock - document doesn't exist
        mock_docs.find_one.return_value = None
        
        # Test invalid data (not a list)
        test_data = {'replace': 'not_a_list'}
        
        # Make request
        response = client.post(
            f'/relationship-draft/add/{TEST_DRAFT_ID}',
            json=test_data,
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['code'] == '400'
        assert 'must be a list' in data['message'].lower()

class TestRelationshipDraftUpdateAPI:
    def test_update_relationships_success(self, client, mock_db):
        # Setup test data
        test_data = {
            'replace': ['DOC002', 'DOC003'],
            'amend': ['DOC004']
        }
        
        # Get mock collections
        mock_docs = mock_db['collections']['biz_upload_documents']
        mock_law_refs = mock_db['collections']['law_references']
        
        # Mock database response
        mock_docs.find_one.return_value = {
            'record_id': TEST_DRAFT_ID,
            'replace': [],
            'amend': []
        }
        
        # Make request
        response = client.post(
            f'/relationship-draft/update/{TEST_DRAFT_ID}',
            json=test_data,
            content_type='application/json'
        )
        
        # Assert response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        assert 'updated relationships in draft' in data['message'].lower()
        
        # Verify database operations
        mock_docs.update_one.assert_called_once()
        mock_law_refs.delete_many.assert_called_once()

class TestRelationshipDraftGetAPI:
    def test_get_relationships_success(self, client, mock_db):
        # Setup test data
        test_doc = {
            'record_id': TEST_DRAFT_ID,
            'replace': ['DOC002', 'DOC003'],
            'amend': ['DOC004'],
            'created_date': '2023-01-01T00:00:00',
            'last_modified': '2023-01-02T00:00:00'
        }
        
        # Get mock collection and set return value
        mock_docs = mock_db['collections']['biz_upload_documents']
        mock_docs.find_one.return_value = test_doc
        
        # Make request
        response = client.get(f'/relationship-draft/get/{TEST_DRAFT_ID}')
        
        # Assert response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        
        # Check that all expected fields are present in the response
        response_data = data['data']
        assert response_data['code'] == test_doc['record_id']
        assert response_data['replace'] == test_doc['replace']
        assert response_data['amend'] == test_doc['amend']
        # Check that additional fields are present
        assert 'add' in response_data
        assert 'base' in response_data
        assert 'detail' in response_data

class TestRelationshipDraftDeleteAPI:
    def test_delete_document_success(self, client, mock_db):
        # Get mock collections
        mock_docs = mock_db['collections']['biz_upload_documents']
        mock_law_refs = mock_db['collections']['law_references']
        
        # Setup - document exists
        mock_docs.find_one.return_value = {
            'record_id': TEST_DRAFT_ID
        }
        
        # Make request
        response = client.post(f'/relationship-draft/delete/{TEST_DRAFT_ID}')
        
        # Assert response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == '200'
        assert 'deleted successfully' in data['message'].lower()
        
        # Verify database operation
        mock_docs.delete_one.assert_called_once_with({'record_id': TEST_DRAFT_ID})

    def test_delete_document_not_found(self, client, mock_db):
        # Get mock collection
        mock_docs = mock_db['collections']['biz_upload_documents']
        
        # Setup - document doesn't exist
        mock_docs.find_one.return_value = None
        
        # Make request
        response = client.post(f'/relationship-draft/delete/{TEST_DRAFT_ID}')
        
        # Assert response
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['code'] == '404'
        assert 'not found' in data['message'].lower()
