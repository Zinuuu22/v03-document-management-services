import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime, timedelta
from bson import ObjectId
from flask import Flask
from flask_restful import Api

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging
setup_logging()
logger = structlog.get_logger()

# Import the API resources
from services.api.biz.regulated_object import (
    ListRegulatedObjectsAPI,
    CreateRegulatedObjectAPI,
    UpdateRegulatedObjectAPI,
    DeleteRegulatedObjectAPI,
    GetRegulatedObjectAPI,
    ListRegulatedObjectMappingsAPI,
    CreateRegulatedObjectMappingAPI,
    UpdateRegulatedObjectMappingAPI,
    DeleteRegulatedObjectMappingAPI,
    GetRegulatedObjectMappingAPI
)

# Test data
TEST_REGULATED_OBJECT_ID = 'RO-001-2024'
TEST_MAPPING_ID = '680c7e5fc9b0edc6b7e236ed'
TEST_DOC_ID = 'DOC-001-2024'
TEST_USER = 'testuser'

# Current time for testing
CURRENT_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Sample test data (will be made serializable later)
SAMPLE_REGULATED_OBJECT_RAW = {
    '_id': ObjectId('680c7e5fc9b0edc6b7e236ec'),
    'regulated_object_id': TEST_REGULATED_OBJECT_ID,
    'regulated_object_name': 'Đối tượng điều chỉnh pháp luật',
    'description': 'Mô tả đối tượng điều chỉnh',
    'regulated_object_name_norm': 'doi tuong dieu chinh phap luat',
    'status': 'Active',
    'created_date': CURRENT_TIME - timedelta(days=7),
    'created_by': 'user1',
    'last_modified': CURRENT_TIME - timedelta(days=1),
    'last_modified_by': 'user1',
    'metadata': {}
}

SAMPLE_MAPPING_RAW = {
    '_id': ObjectId(TEST_MAPPING_ID),
    'doc_id': TEST_DOC_ID,
    'regulated_object_id': TEST_REGULATED_OBJECT_ID,
    'relation_type': 'PRIMARY',
    'created_date': CURRENT_TIME - timedelta(days=3),
    'created_by': 'user1',
    'last_modified': CURRENT_TIME - timedelta(hours=5),
    'last_modified_by': 'user1',
    'metadata': {}
}

# Request bodies for testing
CREATE_REGULATED_OBJECT_BODY = {
    'regulated_object_id': 'RO-NEW-001',
    'regulated_object_name': 'Đối tượng mới',
    'description': 'Mô tả đối tượng mới',
    'regulated_object_name_norm': 'doi tuong moi',
    'status': 'Active',
    'created_by': TEST_USER,
    'metadata': {}
}

UPDATE_REGULATED_OBJECT_BODY = {
    'regulated_object_name': 'Đối tượng cập nhật',
    'description': 'Mô tả đã cập nhật',
    'status': 'Inactive',
    'last_modified_by': TEST_USER,
    'metadata': {'key': 'value'}
}

CREATE_MAPPING_BODY = {
    'doc_id': 'DOC-NEW-001',
    'regulated_object_id': 'RO-NEW-001',
    'relation_type': 'SECONDARY',
    'created_by': TEST_USER,
    'metadata': {}
}

UPDATE_MAPPING_BODY = {
    'relation_type': 'SECONDARY',
    'last_modified_by': TEST_USER,
    'metadata': {'updated': True}
}

# Success responses
SUCCESS_RESPONSES = {
    'list': {'code': 200, 'message': 'Success'},
    'create': {'code': 200, 'message': 'Regulated object created successfully'},
    'get': {'code': 200, 'message': 'Success'},
    'update': {'code': 200, 'message': 'Regulated object updated successfully'},
    'delete': {'code': 200, 'message': f'Regulated object {TEST_REGULATED_OBJECT_ID} deleted successfully'},
    'create_mapping': {'code': 200, 'message': 'Regulated object mapping created successfully'},
    'update_mapping': {'code': 200, 'message': 'Regulated object mapping updated successfully'},
    'delete_mapping': {'code': 200, 'message': f'Regulated object mapping {TEST_MAPPING_ID} deleted successfully'}
}

# Error responses
ERROR_RESPONSES = {
    'not_found': {'code': 404, 'message': 'Resource not found'},
    'missing_fields': {'code': 400, 'message': {'regulated_object_id': 'Regulated object ID is required'}},
    'validation_error': {'code': 400, 'message': 'Validation error'},
    'duplicate': {'code': 400, 'message': 'Duplicate entry'}
}

def make_serializable(data):
    """Convert non-serializable objects in test data to strings."""
    if isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [make_serializable(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    return data

# Make test data serializable
SAMPLE_REGULATED_OBJECT = make_serializable(SAMPLE_REGULATED_OBJECT_RAW)
SAMPLE_MAPPING = make_serializable(SAMPLE_MAPPING_RAW)



def create_test_app():
    """Create and configure a test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Initialize API
    api = Api(app)
    
    # Regulated Objects
    api.add_resource(ListRegulatedObjectsAPI, '/regulated-objects')
    api.add_resource(CreateRegulatedObjectAPI, '/regulated-objects/create')
    api.add_resource(GetRegulatedObjectAPI, '/regulated-objects/<string:regulated_object_id>')
    api.add_resource(UpdateRegulatedObjectAPI, '/regulated-objects/<string:regulated_object_id>/update')
    api.add_resource(DeleteRegulatedObjectAPI, '/regulated-objects/<string:regulated_object_id>/delete')

    # Regulated Object Mappings
    api.add_resource(ListRegulatedObjectMappingsAPI, '/regulated-object-mappings')
    api.add_resource(CreateRegulatedObjectMappingAPI, '/regulated-object-mappings/create')
    api.add_resource(UpdateRegulatedObjectMappingAPI, '/regulated-object-mappings/<string:mapping_id>/update')
    api.add_resource(GetRegulatedObjectMappingAPI, '/regulated-object-mappings/<string:mapping_id>')
    api.add_resource(DeleteRegulatedObjectMappingAPI, '/regulated-object-mappings/<string:mapping_id>/delete')

    return app.test_client()

@pytest.fixture
def client():
    """Create a test client for the application."""
    test_client = create_test_app()
    with test_client.application.app_context():
        yield test_client

@pytest.fixture
def mock_model():
    """Create a mock model for testing with JSON-serializable return values."""
    mock = MagicMock()
    
    # Mock for regulated objects
    mock.list_regulated_objects.return_value = {
        'data': [SAMPLE_REGULATED_OBJECT],
        'pagination': {
            'total': 1,
            'page': 1,
            'limit': 10,
            'total_pages': 1
        }
    }
    
    mock.get_regulated_object_by_id.return_value = SAMPLE_REGULATED_OBJECT
    mock.create_regulated_object.return_value = SAMPLE_REGULATED_OBJECT
    mock.update_regulated_object.return_value = True
    mock.delete_regulated_object.return_value = True
    
    # Mock for regulated object mappings
    mock.list_mappings.return_value = {
        'data': [SAMPLE_MAPPING],
        'pagination': {
            'total': 1,
            'page': 1,
            'limit': 10,
            'total_pages': 1
        }
    }
    
    mock.get_mapping_by_id.return_value = SAMPLE_MAPPING
    mock.get_mapping_by_doc_and_object.return_value = None
    mock.create_regulated_object_mapping.return_value = SAMPLE_MAPPING
    mock.update_regulated_object_mapping.return_value = True
    mock.delete_regulated_object_mapping.return_value = True
    
    return mock

class TestRegulatedObjectAPIs:
    """Test suite for Regulated Object APIs"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, client, mock_model):
        """Setup test environment and reset mocks before each test."""
        self.client = client
        self.mock_model = mock_model
        
        # Reset all mocks before each test
        mock_model.reset_mock()
        
        # Set up default return values
        mock_model.list_regulated_objects.return_value = {
            'data': [SAMPLE_REGULATED_OBJECT],
            'pagination': {
                'total': 1,
                'page': 1,
                'limit': 10,
                'total_pages': 1
            }
        }
        
        mock_model.get_regulated_object_by_id.return_value = SAMPLE_REGULATED_OBJECT
        mock_model.create_regulated_object.return_value = SAMPLE_REGULATED_OBJECT
        mock_model.update_regulated_object.return_value = True
        mock_model.delete_regulated_object.return_value = True
        
        mock_model.list_regulated_object_mappings.return_value = {
            'data': [SAMPLE_MAPPING],
            'pagination': {
                'total': 1,
                'page': 1,
                'limit': 10,
                'total_pages': 1
            }
        }
        
        mock_model.get_mapping_by_id.return_value = SAMPLE_MAPPING
        mock_model.get_mapping_by_doc_and_object.return_value = None  # No existing mapping by default
        mock_model.create_regulated_object_mapping.return_value = SAMPLE_MAPPING
        mock_model.update_regulated_object_mapping.return_value = True
        mock_model.delete_regulated_object_mapping.return_value = True
        
        # Set up the patcher
        self.regulated_object_patcher = patch(
            'services.api.biz.regulated_object.regulated_object_model',
            new_callable=lambda: mock_model
        )
        self.regulated_object_patcher.start()
        
        yield        
        # Cleanup
        self.regulated_object_patcher.stop()
    
    # Test cases for Regulated Objects
    def test_list_regulated_objects_success(self):
        """Test listing regulated objects with pagination."""
        response = self.client.get('/regulated-objects')
        assert response.status_code == 200
        data = json.loads(response.data)
        logger.debug("test_list_regulated_objects_success", action="test_list_regulated_objects_success", data=data)

        assert data['code'] == 200
        assert len(data['data']) == 1
        assert data['data'][0]['regulated_object_id'] == TEST_REGULATED_OBJECT_ID
    
    def test_get_regulated_object_success(self):
        """Test getting a single regulated object by ID."""
        response = self.client.get(f'/regulated-objects/{TEST_REGULATED_OBJECT_ID}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == 200
        assert data['data']['regulated_object_id'] == TEST_REGULATED_OBJECT_ID
    
    def test_create_regulated_object_success(self):
        """Test creating a new regulated object."""
        response = self.client.post(
            '/regulated-objects/create',
            data=json.dumps(CREATE_REGULATED_OBJECT_BODY),
            content_type='application/json'
        )
        logger.debug("test_create_regulated_object_success", action="test_create_regulated_object_success", response_text=response.text)
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['code'] == 201
        assert data['message'] == 'Regulated object created successfully'
    
    def test_update_regulated_object_success(self):
        """Test updating an existing regulated object."""
        response = self.client.put(
            f'/regulated-objects/{TEST_REGULATED_OBJECT_ID}/update',
            data=json.dumps(UPDATE_REGULATED_OBJECT_BODY),
            content_type='application/json'
        )
        logger.debug("test_update_regulated_object_success", action="test_update_regulated_object_success", response_text=response.text)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == 200
        assert data['message'] == 'Regulated object updated successfully'
    
    def test_delete_regulated_object_success(self):
        """Test deleting a regulated object."""
        response = self.client.delete(f'/regulated-objects/{TEST_REGULATED_OBJECT_ID}/delete')
        logger.debug("test_delete_regulated_object_success", action="test_delete_regulated_object_success", response_text=response.text)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == 200
        assert data['message'] == f'Regulated object {TEST_REGULATED_OBJECT_ID} deleted successfully'
    
    # Test cases for Regulated Object Mappings
    def test_list_regulated_object_mappings_success(self):
        """Test listing regulated object mappings with pagination."""
        response = self.client.get('/regulated-object-mappings')
        assert response.status_code == 200
        response_data = json.loads(response.data)
        logger.debug("test_list_regulated_object_mappings_success", action="test_list_regulated_object_mappings_success", response_data=response_data)
        
        assert response_data['code'] == 200
        assert response_data['message'] == 'Successfully retrieved regulated object mappings'
        
        # The actual mappings are in response_data['data']['data']
        assert len(response_data['data']['data']) == 1
        assert response_data['data']['data'][0]['regulated_object_id'] == TEST_REGULATED_OBJECT_ID
        
        # Verify pagination
        assert response_data['data']['pagination'] == {
            'total': 1,
            'page': 1,
            'limit': 10,
            'total_pages': 1
        }
        
    def test_get_regulated_object_mapping_success(self):
        """Test getting a single regulated object mapping by ID."""
        response = self.client.get(f'/regulated-object-mappings/{TEST_MAPPING_ID}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == 200
        assert data['data']['_id'] == TEST_MAPPING_ID
    
    def test_create_regulated_object_mapping_success(self):
        """Test creating a new regulated object mapping."""
        # Configure mocks
        self.mock_model.get_mapping_by_doc_and_object.return_value = None
        self.mock_model.create_mapping.return_value = SAMPLE_MAPPING  # Return the sample mapping
        
        logger.debug("test_create_regulated_object_mapping_success", action="test_create_regulated_object_mapping_success", request_data=CREATE_MAPPING_BODY)
        response = self.client.post(
            '/regulated-object-mappings/create',
            data=json.dumps(CREATE_MAPPING_BODY),
            content_type='application/json'
        )
        
        # Assert the response
        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert response_data['code'] == 201
        assert response_data['message'] == 'Regulated object mapping created successfully'
        assert response_data['data']['_id'] == TEST_MAPPING_ID
        assert response_data['data']['doc_id'] == 'DOC-001-2024'  # From SAMPLE_MAPPING
        assert response_data['data']['regulated_object_id'] == 'RO-001-2024'  # From SAMPLE_MAPPING
    
    def test_update_regulated_object_mapping_success(self):
        """Test updating an existing regulated object mapping."""
        # Create a proper object-like dictionary for the response
        class ObjectView(dict):
            def __init__(self, d):
                super().__init__(d)
                self.__dict__ = self

        # Create an updated version of the sample mapping
        updated_mapping = ObjectView(SAMPLE_MAPPING.copy())
        updated_mapping.update({
            'relation_type': 'SECONDARY',
            'last_modified': datetime.now().strftime("%Y-%m-%d %H:%M:%S").isoformat(),
            'last_modified_by': 'testuser',
            'metadata': {'updated': True}
        })
        
        # Configure the mocks
        self.mock_model.get_mapping_by_id.return_value = ObjectView(SAMPLE_MAPPING)
        self.mock_model.update_mapping.return_value = updated_mapping
        
        response = self.client.put(
            f'/regulated-object-mappings/{TEST_MAPPING_ID}/update',
            data=json.dumps(UPDATE_MAPPING_BODY),
            content_type='application/json'
        )
        
        # Debug output
        logger.debug("test_update_regulated_object_mapping_success", action="test_update_regulated_object_mapping_success", status_code=response.status_code, response_body=response.data)
        
        # Assert the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['code'] == 200
        assert response_data['message'] == 'Regulated object mapping updated successfully'
        assert response_data['data']['relation_type'] == 'SECONDARY'
        assert response_data['data']['metadata'] == {'updated': True}
    
    def test_delete_regulated_object_mapping_success(self):
        """Test deleting a regulated object mapping."""
        response = self.client.delete(f'/regulated-object-mappings/{TEST_MAPPING_ID}/delete')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['code'] == 200
        assert data['message'] == f'Regulated object mapping {TEST_MAPPING_ID} deleted successfully'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])