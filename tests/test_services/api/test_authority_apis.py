import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime
from bson import ObjectId
from flask import Flask
from flask_restful import Api

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

# Import the API resources
from services.api.biz.authority import (
    AuthorityListAPI, 
    AuthorityDetailAPI, 
    AuthorityCreateAPI,
    AgencyListAPI
)


# Test data
TEST_AUTHORITY_ID = 'AUTH-001'
TEST_AGENCY_ID = 'AGY-001'
TEST_DOCUMENT_ID = 'DOC-001'
TEST_ARTICLE_ID = 'ART-001'

# Sample test data
SAMPLE_AUTHORITY = {
    'authority_id': TEST_AUTHORITY_ID,
    'document': {
        'id': TEST_DOCUMENT_ID,
        'title': 'Nghị định 01/2023/NĐ-CP'
    },
    'article': {
        'id': TEST_ARTICLE_ID,
        'title': 'Điều 1. Phạm vi điều chỉnh'
    },
    'agency': {
        'id': TEST_AGENCY_ID,
        'name': 'Bộ Tài chính'
    },
    'assigned_content': 'Khoản 1 - Điều 1',
    'effective_date': '2023-01-01T00:00:00Z',
    'status': 'ACTIVE'
}

# Create test Flask app
def create_test_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Initialize API
    api = Api(app)
    
    # Add resources
    api.add_resource(AuthorityListAPI, '/authority/list')
    api.add_resource(AuthorityCreateAPI, '/authority/create')
    api.add_resource(AuthorityDetailAPI, '/authority/<string:authority_id>')
    api.add_resource(AgencyListAPI, '/authority/agencies')
    
    return app

class TestAuthorityAPIs:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Create test client
        self.app = create_test_app()
        self.client = self.app.test_client()
        
        # Create a mock for the AuthorityModel
        self.mock_authority_model = MagicMock()
        
        # Set up return values for the mock
        self.mock_authority_model.collection = MagicMock()
        self.mock_authority_model.agencies_collection = MagicMock()
        
        # Configure the mock collections
        self.mock_authority_model.collection.find_one.return_value = SAMPLE_AUTHORITY
        self.mock_authority_model.collection.find.return_value = [SAMPLE_AUTHORITY]
        self.mock_authority_model.collection.update_one.return_value.modified_count = 1
        self.mock_authority_model.collection.delete_one.return_value.deleted_count = 1
        
        self.mock_authority_model.agencies_collection.find.return_value = [
            {'id': 'AGY-001', 'name': 'Bộ Tài chính', 'status': 'ACTIVE'},
            {'id': 'AGY-002', 'name': 'Bộ Giao thông Vận tải', 'status': 'ACTIVE'}
        ]
        
        # Patch the AuthorityModel in the authority module
        self.patcher = patch('services.api.biz.authority.authority_model', self.mock_authority_model)
        self.patcher.start()
        
        yield
        
        # Cleanup
        self.patcher.stop()
    
    def test_create_authority_success(self):
        # Arrange
        new_authority = {
            'doc_id': 'DOC-002',
            'doc_title': 'Nghị định 02/2023/NĐ-CP',
            'article_id': 'ART-002',
            'article_title': 'Điều 1',
            'article_content': 'Nội dung điều 1',
            'agency_id': 'AGY-002',
            'agency_name': 'Bộ GTVT',
            'authority_content': 'Khoản 1',
            'authority_content_detail': 'Chi tiết khoản 1',
            'effective_date': '2023-01-02T00:00:00Z',
            'expire_date': '2024-01-02T00:00:00Z',
            'status': 'ACTIVE',
            'effective_status': 'Còn hiệu lực'
        }
        
        # Mock the create_authority method to return the authority data with ID
        created_authority = {
            'authority_id': 'AUTH-2023-1234',
            **new_authority
        }
        self.mock_authority_model.create_authority.return_value = created_authority

        # Act
        response = self.client.post(
            '/authority/create',
            json=new_authority,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 201
        response_data = response.get_json()

        assert 'authority_id' in response_data['data']
        assert response_data['code'] == 201

    def test_get_authority_success(self):
        # Mock the get_authority response
        self.mock_authority_model.get_authority.return_value = {
            'authority_id': TEST_AUTHORITY_ID,
            'doc_id': TEST_DOCUMENT_ID,
            'doc_title': 'Test Document',
            'article_id': TEST_ARTICLE_ID,
            'article_title': 'Test Article',
            'article_content': 'Test Content',
            'agency_id': TEST_AGENCY_ID,
            'agency_name': 'Test Agency',
            'authority_content': 'Test Authority Content',
            'authority_content_detail': 'Test Detail',
            'effective_date': '2023-01-01T00:00:00Z',
            'expire_date': '2024-01-01T00:00:00Z',
            'status': 'ACTIVE',
            'effective_status': 'Còn hiệu lực'
        }
        
        # Act
        response = self.client.get(
            f'/authority/{TEST_AUTHORITY_ID}',
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 200
        assert response_data['data']['authority_id'] == TEST_AUTHORITY_ID
        self.mock_authority_model.get_authority.assert_called_once_with(TEST_AUTHORITY_ID)
    
    def test_get_authority_not_found(self):
        # Arrange
        self.mock_authority_model.get_authority.return_value = None
        
        # Act
        response = self.client.get(
            '/authority/NON-EXISTENT',
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['code'] == 404
    
    def test_update_authority_success(self):
        # Arrange - Include all required fields from authority_parser
        update_data = {
            'doc_id': 'DOC-001',
            'doc_title': 'Updated Document Title',
            'article_id': 'ART-001',
            'article_title': 'Updated Article Title',
            'article_content': 'Updated article content',
            'agency_id': 'AGY-001',
            'agency_name': 'Updated Agency',
            'authority_content': 'Khoản 1 - Điều 1 (đã cập nhật)',
            'authority_content_detail': 'Updated detail',
            'effective_date': '2023-01-01T00:00:00Z',
            'expire_date': '2024-01-01T00:00:00Z',
            'status': 'INACTIVE',
            'effective_status': 'Còn hiệu lực'
        }
        
        # Mock the update_authority method
        self.mock_authority_model.update_authority.return_value = True
        
        # Mock get_authority to return a valid authority
        self.mock_authority_model.get_authority.return_value = {
            'authority_id': TEST_AUTHORITY_ID,
            **update_data
        }
        
        # Act
        response = self.client.put(
            f'/authority/{TEST_AUTHORITY_ID}',
            json=update_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        
        assert response_data['code'] == 200
        assert response_data['data']['authority_id'] == TEST_AUTHORITY_ID
        self.mock_authority_model.update_authority.assert_called_once()
        
        # Verify the call args
        call_args = self.mock_authority_model.update_authority.call_args[0]
        assert call_args[0] == TEST_AUTHORITY_ID
        # Check that all expected fields are in the update data
        for field in update_data:
            assert field in call_args[1]
    
    def test_delete_authority_success(self):
        # Mock the delete_authority method
        self.mock_authority_model.delete_authority.return_value = True
        
        # Mock the get_authority response
        self.mock_authority_model.get_authority.return_value = {
            'authority_id': TEST_AUTHORITY_ID,
            'status': 'ACTIVE'
        }
        
        # Act
        response = self.client.delete(
            f'/authority/{TEST_AUTHORITY_ID}',
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 200
        self.mock_authority_model.delete_authority.assert_called_once_with(TEST_AUTHORITY_ID)
    
    def test_list_authorities_success(self):
        # Mock the list_authorities method
        mock_items = [{
            'authority_id': TEST_AUTHORITY_ID,
            'doc_id': TEST_DOCUMENT_ID,
            'doc_title': 'Test Document',
            'article_id': TEST_ARTICLE_ID,
            'article_title': 'Test Article',
            'agency_id': TEST_AGENCY_ID,
            'agency_name': 'Test Agency',
            'authority_content': 'Test Content',
            'effective_date': '2023-01-01T00:00:00Z',
            'expire_date': '2024-01-01T00:00:00Z',
            'status': 'ACTIVE',
            'effective_status': 'Còn hiệu lực'
        }]
        
        self.mock_authority_model.list_authorities.return_value = {
            'items': mock_items,
            'total': len(mock_items)
        }
        
        # Act
        response = self.client.get(
            '/authority/list',
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 200
        assert 'data' in response_data
        assert 'total' in response_data['data']
        assert 'page' in response_data['data']
        assert 'data' in response_data['data']
        assert len(response_data['data']['data']) > 0
        self.mock_authority_model.list_authorities.assert_called_once()
    
    def test_list_agencies_success(self):
        # Arrange - Setup mock data
        mock_agencies = [
            {'id': 'AGY-001', 'name': 'Bộ Tài chính', 'status': 'ACTIVE'},
            {'id': 'AGY-002', 'name': 'Bộ Giao thông Vận tải', 'status': 'ACTIVE'}
        ]
        
        # Mock the list_agencies method
        self.mock_authority_model.list_agencies.return_value = {
            'items': mock_agencies,
            'total': len(mock_agencies)
        }
        
        # Act
        response = self.client.get(
            '/authority/agencies',
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 200
        assert len(response_data['data']) == 2
        assert response_data['data'][0]['agency_name'] == 'Bộ Tài chính'
        assert response_data['data'][1]['agency_name'] == 'Bộ Giao thông Vận tải'
        self.mock_authority_model.list_agencies.assert_called_once_with('', page=1, limit=1000)

    def test_list_agencies_with_search(self):
        # Arrange - Setup mock data
        mock_agencies = [
            {'id': 'AGY-001', 'name': 'Bộ Tài chính', 'status': 'ACTIVE'}
        ]
        
        # Configure the mock to return filtered results based on search term
        def list_agencies_side_effect(search, page, limit):
            if search == 'Tài chính':
                return {'items': mock_agencies, 'total': 1}
            return {'items': [], 'total': 0}
        
        self.mock_authority_model.list_agencies.side_effect = list_agencies_side_effect
        
        # Act
        response = self.client.get(
            '/authority/agencies?search=Tài chính',
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 200
        assert len(response_data['data']) == 1
        assert response_data['data'][0]['agency_name'] == 'Bộ Tài chính'
        
        # Verify the search parameter was passed correctly
        self.mock_authority_model.list_agencies.assert_called_once_with('Tài chính', page=1, limit=1000)