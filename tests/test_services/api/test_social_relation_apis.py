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
from services.api.biz.social_relation import (
    ListSocialRelationsAPI,
    CreateSocialRelationAPI,
    UpdateSocialRelationAPI,
    DeleteSocialRelationAPI,
    GetSocialRelationAPI,
    ListSocialRelationMappingsAPI,
    CreateSocialRelationMappingAPI,
    UpdateSocialRelationMappingAPI,
    DeleteSocialRelationMappingAPI,
    GetSocialRelationMappingAPI
)

# Test data
TEST_SOCIAL_RELATION_ID = 'SR-001-2024'
TEST_MAPPING_ID = '680c7e5fc9b0edc6b7e236ed'
TEST_DOC_ID = 'DOC-001-2024'
TEST_ARTICLE_ID = 'ART-001-2024'
TEST_USER = 'testuser'

# Current time for testing
CURRENT_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Sample test data (will be made serializable later)
SAMPLE_SOCIAL_RELATION_RAW = {
    '_id': ObjectId('680c7e5fc9b0edc6b7e236ec'),
    'social_relation_id': TEST_SOCIAL_RELATION_ID,
    'social_relation_name': 'Quan hệ giáo dục và phát triển xã hội',
    'description': 'Mối quan hệ liên quan đến giáo dục và phát triển cộng đồng.',
    'social_relation_name_norm': 'quan he giao duc va phat trien xa hoi',
    'status': 'Active',
    'created_date': CURRENT_TIME - timedelta(days=7),
    'created_by': 'user1',
    'last_modified': CURRENT_TIME - timedelta(days=1),
    'last_modified_by': 'user1'
}

SAMPLE_MAPPING_RAW = {
    '_id': ObjectId(TEST_MAPPING_ID),
    'doc_id': TEST_DOC_ID,
    'article_id': TEST_ARTICLE_ID,
    'social_relation_id': TEST_SOCIAL_RELATION_ID,
    'relation_type': 'PRIMARY',
    'created_date': CURRENT_TIME - timedelta(days=3),
    'created_by': 'user1',
    'last_modified': CURRENT_TIME - timedelta(hours=5),
    'last_modified_by': 'user1'
}

# Request bodies for testing
CREATE_SOCIAL_RELATION_BODY = {
    'social_relation_id': 'SR-NEW-001',
    'social_relation_name': 'Quan hệ mới',
    'description': 'Mô tả quan hệ mới',
    'social_relation_name_norm': 'quan he moi',
    'status': 'Active',
    'created_by': TEST_USER
}

UPDATE_SOCIAL_RELATION_BODY = {
    'social_relation_name': 'Quan hệ cập nhật',
    'description': 'Mô tả đã cập nhật',
    'status': 'Inactive',
    'last_modified_by': TEST_USER
}

CREATE_MAPPING_BODY = {
    'doc_id': 'DOC-NEW-001',
    'article_id': 'ART-NEW-001',
    'social_relation_id': 'SR-NEW-001',
    'relation_type': 'SECONDARY',
    'created_by': TEST_USER
}

UPDATE_MAPPING_BODY = {
    'relation_type': 'Tertiary',
    'last_modified_by': TEST_USER
}

# Success responses
SUCCESS_RESPONSES = {
    'list': {'code': 0, 'message': 'Success'},
    'create': {'code': 0, 'message': 'Social relation created successfully'},
    'get': {'code': 0, 'message': 'Success'},
    'update': {'code': 0, 'message': 'Social relation updated successfully'},
    'delete': {'code': 0, 'message': f'Social relation {TEST_SOCIAL_RELATION_ID} deleted successfully'},
    'create_mapping': {'code': 0, 'message': 'Social relation mapping created successfully'},
    'update_mapping': {'code': 0, 'message': 'Social relation mapping updated successfully'},
    'delete_mapping': {'code': 0, 'message': f'Social relation mapping {TEST_MAPPING_ID} deleted successfully'}
}

# Error responses
ERROR_RESPONSES = {
    'missing_fields': {'code': 400, 'message': {'social_relation_id': 'Social relation ID is required'}},
    'not_found': {'code': 404, 'message': 'Resource not found'},
    'validation_error': {'code': 400, 'message': 'Validation error'},
    'duplicate': {'code': 400, 'message': 'Duplicate entry'}
}

# Helper function to make test data JSON-serializable
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
SAMPLE_SOCIAL_RELATION = make_serializable({
    '_id': ObjectId('680c7e5fc9b0edc6b7e236ec'),
    'social_relation_id': TEST_SOCIAL_RELATION_ID,
    'social_relation_name': 'Quan hệ giáo dục và phát triển xã hội',
    'description': 'Mối quan hệ liên quan đến giáo dục và phát triển cộng đồng.',
    'social_relation_name_norm': 'quan he giao duc va phat trien xa hoi',
    'status': 'Active',
    'created_date': CURRENT_TIME - timedelta(days=7),
    'created_by': 'user1',
    'last_modified': CURRENT_TIME - timedelta(days=1),
    'last_modified_by': 'user1'
})

SAMPLE_MAPPING = make_serializable({
    '_id': TEST_MAPPING_ID,
    'doc_id': TEST_DOC_ID,
    'article_id': TEST_ARTICLE_ID,
    'social_relation_id': TEST_SOCIAL_RELATION_ID,
    'relation_type': 'PRIMARY',
    'created_date': CURRENT_TIME - timedelta(days=3),
    'created_by': 'user1',
    'last_modified': CURRENT_TIME - timedelta(hours=5),
    'last_modified_by': 'user1'
})

# Error responses
ERROR_RESPONSES = {
    'not_found': {'code': 1000, 'message': 'Social relation not found'},
    'missing_fields': {'code': 1001, 'message': 'Social relation ID is required'},
    'duplicate_id': {'code': 1002, 'message': 'Social relation ID already exists'},
    'invalid_data': {'code': 1003, 'message': 'Invalid data provided'},
    'server_error': {'code': 2000, 'message': 'Internal server error'}
}


# Create test Flask app
def create_test_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Initialize API
    api = Api(app)
    
    # Add Social Relations resources
    api.add_resource(ListSocialRelationsAPI, '/social-relations')
    api.add_resource(CreateSocialRelationAPI, '/social-relations/create')
    api.add_resource(GetSocialRelationAPI, '/social-relations/<string:social_relation_id>')
    api.add_resource(UpdateSocialRelationAPI, '/social-relations/<string:social_relation_id>/update')
    api.add_resource(DeleteSocialRelationAPI, '/social-relations/<string:social_relation_id>/delete')
    
    # Add Social Relation Mappings resources
    api.add_resource(ListSocialRelationMappingsAPI, '/social-relation-mappings')
    api.add_resource(CreateSocialRelationMappingAPI, '/social-relation-mappings/create')
    api.add_resource(GetSocialRelationMappingAPI, '/social-relation-mappings/<string:mapping_id>')
    api.add_resource(UpdateSocialRelationMappingAPI, '/social-relation-mappings/<string:mapping_id>/update')
    api.add_resource(DeleteSocialRelationMappingAPI, '/social-relation-mappings/<string:mapping_id>/delete')
    
    return app.test_client()


@pytest.fixture
def client():
    """Create a test client for the application."""
    # create_test_app() already returns a test client
    test_client = create_test_app()
    with test_client.application.app_context():
        yield test_client

@pytest.fixture
def mock_model():
    """Create a mock model for testing with JSON-serializable return values."""
    mock = MagicMock()
    
    # Convert raw samples to serializable format
    serialized_relation = make_serializable({
        **SAMPLE_SOCIAL_RELATION_RAW,
        'social_relation_id': 'SR-001-2024',
        'created_date': SAMPLE_SOCIAL_RELATION_RAW['created_date'].isoformat(),
        'last_modified': SAMPLE_SOCIAL_RELATION_RAW['last_modified'].isoformat()
    })
    
    serialized_mapping = make_serializable({
        **SAMPLE_MAPPING_RAW,
        'created_date': SAMPLE_MAPPING_RAW['created_date'].isoformat(),
        'last_modified': SAMPLE_MAPPING_RAW['last_modified'].isoformat()
    })
    
    # Common mock returns with serialized data
    mock.get_social_relation_by_id.return_value = serialized_relation
    mock.get_social_relation_mapping_by_id.return_value = serialized_mapping
    
    # Mock return values for social relation operations
    mock.create_social_relation.return_value = {
        **serialized_relation,
        'social_relation_id': 'SR-NEW-001'
    }
    
    mock.update_social_relation.return_value = {
        **serialized_relation,
        'status': 'Inactive',
        'last_modified': datetime.now().strftime("%Y-%m-%d %H:%M:%S").isoformat(),
        'last_modified_by': 'testuser'
    }
    
    mock.delete_social_relation.return_value = {
        'status': 'success',
        'deleted_count': 1,
        'message': f'Xóa quan hệ xã hội SR-001-2024 thành công'
    }
    
    # Mock return values for mapping operations
    mock.create_social_relation_mapping.return_value = {
        **serialized_mapping,
        'doc_id': 'DOC-NEW-001',
        'created_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S").isoformat()
    }
    
    mock.update_social_relation_mapping.return_value = {
        **serialized_mapping,
        'relation_type': 'Tertiary'
    }
    
    # Setup other mock return values
    mock.list_social_relations.return_value = [serialized_relation]
    mock.get_social_relations.return_value = [serialized_relation]
    mock.get_social_relation_mappings.return_value = [serialized_mapping]
    mock.get_social_relation_by_id.return_value = serialized_relation
    mock.get_social_relation_mapping_by_id.return_value = serialized_mapping
    mock.create_social_relation.return_value = {'code': 0, 'message': 'Success'}
    mock.update_social_relation.return_value = {'code': 0, 'message': 'Success'}
    mock.delete_social_relation.return_value = {'code': 0, 'message': 'Success'}
    mock.create_social_relation_mapping.return_value = {'code': 0, 'message': 'Success'}
    mock.update_social_relation_mapping.return_value = {'code': 0, 'message': 'Success'}
    mock.delete_social_relation_mapping.return_value = {'code': 0, 'message': 'Success'}
    
    # Mock error responses
    def create_social_relation_side_effect(*args, **kwargs):
        if not kwargs.get('social_relation_id'):
            return {
                'code': 1001,
                'message': {'social_relation_id': 'Social relation ID is required'}
            }
        return {
            'code': 0,
            'message': 'Success',
            'data': {
                'social_relation_id': kwargs.get('social_relation_id'),
                'social_relation_name': kwargs.get('social_relation_name', ''),
                'status': kwargs.get('status', 'Active')
            }
        }
        
    mock.create_social_relation.side_effect = create_social_relation_side_effect
    
    return mock

class TestSocialRelationAPIs:
    """Test suite for Social Relations APIs"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, client, mock_model):
        """Setup test environment"""
        self.client = client
        self.mock_model = mock_model
        
        # Patch the model in all API resources
        self.patcher = patch('services.api.biz.social_relation.social_relation_model', self.mock_model)
        self.mock_model_patcher = self.patcher.start()
        
        yield  # this is where the testing happens
        
        # Teardown
        self.patcher.stop()
    
    @pytest.mark.parametrize('endpoint,method,data,status_code,expected', [
        # List social relations
        ('/social-relations', 'GET', None, 200, SUCCESS_RESPONSES['list']),
        
        # Create social relation - success
        ('/social-relations/create', 'POST', CREATE_SOCIAL_RELATION_BODY, 201, 
         SUCCESS_RESPONSES['create']),
        
        # Create social relation - missing required field
        ('/social-relations/create', 'POST', {'social_relation_name': 'Test'}, 400, 
         ERROR_RESPONSES['missing_fields']),
        
        # Get social relation - success
        (f'/social-relations/{TEST_SOCIAL_RELATION_ID}', 'GET', None, 200, 
         SUCCESS_RESPONSES['get']),
        
        # Update social relation - success
        (f'/social-relations/{TEST_SOCIAL_RELATION_ID}/update', 'PUT', UPDATE_SOCIAL_RELATION_BODY, 200,
         SUCCESS_RESPONSES['update']),
         
        # Delete social relation - success
        (f'/social-relations/{TEST_SOCIAL_RELATION_ID}/delete', 'DELETE', None, 200,
         SUCCESS_RESPONSES['delete']),
         
        # Create mapping - success
        ('/social-relation-mappings/create', 'POST', CREATE_MAPPING_BODY, 201,
         SUCCESS_RESPONSES['create_mapping']),
         
        # Update mapping - success
        (f'/social-relation-mappings/{TEST_MAPPING_ID}/update', 'PUT', UPDATE_MAPPING_BODY, 200,
         SUCCESS_RESPONSES['update_mapping']),
    ])
    def test_api_endpoints(self, endpoint, method, data, status_code, expected):
        """Test API endpoints with various scenarios"""
        # Setup mock based on test case
        if 'not_found' in str(expected):
            self.mock_model.get_social_relation_by_id.return_value = None
            self.mock_model.get_social_relation_mapping_by_id.return_value = None
    
        # Prepare request data
        request_data = None
        if data is not None:
            request_data = json.dumps(data)
        
        # Make the request
        if method == 'GET':
            response = self.client.get(endpoint)
        elif method == 'POST':
            response = self.client.post(
                endpoint,
                data=request_data,
                content_type='application/json'
            )
        elif method == 'PUT':
            response = self.client.put(
                endpoint,
                data=request_data,
                content_type='application/json'
            )
        elif method == 'DELETE':
            response = self.client.delete(endpoint)
    
        # Verify response
        assert response.status_code == status_code, \
            f"Expected status code {status_code}, but got {response.status_code}. Response: {response.data}"
            
        response_data = json.loads(response.data)
        
        # For error responses, check the structure
        if status_code >= 400:
            if isinstance(expected, dict) and 'code' in expected:
                logger.debug("verify_response", action="test_api_endpoints", response_data=response_data)
                if 'code' in response_data:
                    assert response_data['code'] == expected['code'], \
                        f"Expected error code {expected['code']}, but got {response_data.get('code')}"
                
            if 'message' in response_data and isinstance(response_data['message'], dict):
                # If message is a dict, check if any of the expected messages match
                if isinstance(expected.get('message'), dict):
                    for key, msg in expected['message'].items():
                        assert key in response_data['message'], \
                            f"Expected error message for '{key}' not found in {response_data['message']}"
                        assert msg in str(response_data['message'][key]), \
                            f"Expected message '{msg}' not found in '{response_data['message'][key]}'"
                else:
                    assert expected.get('message') in str(response_data['message']), \
                        f"Expected message '{expected.get('message')}' not found in '{response_data['message']}'"
        else:
            # For success responses
            if method == 'GET':
                if 'data' in response_data:
                    if isinstance(response_data['data'], list) or 'items' in response_data['data']:
                        items = response_data['data'] if isinstance(response_data['data'], list) else response_data['data'].get('items', [])
                        assert isinstance(items, list), \
                            f"Expected list data, got {type(items).__name__}"
                else:
                    assert 'data' in response_data, \
                        f"Success response missing 'data' field. Response: {response_data}"
            
            # Verify the response code matches expected
            if isinstance(expected, dict) and 'code' in expected:
                assert response_data.get('code') == expected.get('code'), \
                    f"Expected code {expected.get('code')}, but got {response_data.get('code')}"
        
        # For successful responses, check if data is present
        if status_code in (200, 201):
            assert 'data' in response_data

    def test_list_social_relations_success(self):
        """Test listing social relations with pagination"""
        # Arrange
        mock_result = {
            'status': 'success',
            'data': [SAMPLE_SOCIAL_RELATION],
            'pagination': {
                'page': 1,
                'limit': 10,
                'total': 1
            }
        }
        self.mock_model.list_social_relations.return_value = mock_result
        
        # Act
        response = self.client.get('/social-relations?page=1&limit=10')
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        assert 'data' in response_data
        self.mock_model.list_social_relations.assert_called_once()
    
    def test_list_social_relations_with_filters(self):
        """Test listing social relations with filters"""
        # Arrange
        mock_result = {
            'status': 'success',
            'data': [SAMPLE_SOCIAL_RELATION],
            'pagination': {
                'page': 1,
                'limit': 10,
                'total': 1
            }
        }
        self.mock_model.list_social_relations.return_value = mock_result
        
        # Act
        response = self.client.get(
            '/social-relations?social_relation_name=giáo dục&status=Active&page=1&limit=10'
        )

        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        
        # Verify filters were passed
        call_args = self.mock_model.list_social_relations.call_args
        filters = call_args[1]['filters']
        assert 'social_relation_name' in filters
        assert filters['social_relation_name'] == 'giáo dục'
        assert filters['status'] == 'Active'
    
    def test_get_social_relation_success(self):
        """Test getting a single social relation by ID"""
        # Arrange
        self.mock_model.get_social_relation_by_id.return_value = SAMPLE_SOCIAL_RELATION
        
        # Act
        response = self.client.get(f'/social-relations/{TEST_SOCIAL_RELATION_ID}')
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        assert response_data['data']['social_relation_id'] == TEST_SOCIAL_RELATION_ID
        self.mock_model.get_social_relation_by_id.assert_called_once_with(TEST_SOCIAL_RELATION_ID)
    
    def test_get_social_relation_not_found(self):
        """Test getting a non-existent social relation"""
        # Arrange
        self.mock_model.get_social_relation_by_id.return_value = None
        
        # Act
        response = self.client.get('/social-relations/NON-EXISTENT')
        
        # Assert
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    def test_create_social_relation_success(self):
        """Test creating a new social relation"""
        # Arrange
        new_relation = {
            'social_relation_id': 'SR-002-2024',
            'social_relation_name': 'Quan hệ kinh tế và thương mại',
            'description': 'Mối quan hệ về kinh tế',
            'social_relation_name_norm': 'Quan he kinh te va thuong mai',
            'status': 'Active',
            'created_by': 'user1'
        }
        
        created_relation = {**new_relation, '_id': '680c7e5fc9b0edc6b7e236ee'}
        self.mock_model.create_social_relation.return_value = created_relation
        
        # Act
        response = self.client.post(
            '/social-relations/create',
            json=new_relation,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 201
        response_data = response.get_json()
        assert response_data['code'] == 0
        assert 'data' in response_data
        self.mock_model.create_social_relation.assert_called_once()
    
    def test_create_social_relation_duplicate(self):
        """Test creating a duplicate social relation"""
        # Arrange
        new_relation = {
            'social_relation_id': TEST_SOCIAL_RELATION_ID,
            'social_relation_name': 'Duplicate',
            'description': 'Test',
            'social_relation_name_norm': 'duplicate',
            'status': 'Active',
            'created_by': 'user1'
        }
        
        self.mock_model.create_social_relation.side_effect = ValueError(
            f"Social relation with ID {TEST_SOCIAL_RELATION_ID} already exists"
        )
        
        # Act
        response = self.client.post(
            '/social-relations/create',
            json=new_relation,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    def test_create_social_relation_missing_required_fields(self):
        """Test creating a social relation with missing required fields"""
        # Arrange
        incomplete_relation = {
            'social_relation_id': 'SR-003-2024',
            'social_relation_name': 'Test'
            # Missing: social_relation_name_norm, created_by
        }
        
        # Act
        response = self.client.post(
            '/social-relations/create',
            json=incomplete_relation,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.get_json()
        assert 'message' in response_data
    
    def test_update_social_relation_success(self):
        """Test updating an existing social relation"""
        # Arrange
        update_data = {
            'social_relation_name': 'Updated Name',
            'description': 'Updated description',
            'status': 'Inactive',
            'last_modified_by': 'user2'
        }
        
        updated_relation = {**SAMPLE_SOCIAL_RELATION, **update_data}
        self.mock_model.update_social_relation.return_value = updated_relation
        
        # Act
        response = self.client.put(
            f'/social-relations/{TEST_SOCIAL_RELATION_ID}/update',
            json=update_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        self.mock_model.update_social_relation.assert_called_once()
        
        # Verify the call args
        call_args = self.mock_model.update_social_relation.call_args[0]
        assert call_args[0] == TEST_SOCIAL_RELATION_ID
    
    def test_update_social_relation_not_found(self):
        """Test updating a non-existent social relation"""
        # Arrange
        update_data = {
            'social_relation_name': 'Updated Name',
            'last_modified_by': 'user2'
        }
        
        self.mock_model.update_social_relation.side_effect = ValueError(
            "Social relation with ID NON-EXISTENT not found"
        )
        
        # Act
        response = self.client.put(
            '/social-relations/NON-EXISTENT/update',
            json=update_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    def test_delete_social_relation_success(self):
        """Test deleting a social relation"""
        # Arrange
        self.mock_model.delete_social_relation.return_value = {
            'social_relation_id': TEST_SOCIAL_RELATION_ID,
            'deleted': True,
            'deleted_mappings': 3
        }
        
        # Act
        response = self.client.delete(f'/social-relations/{TEST_SOCIAL_RELATION_ID}/delete')
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        self.mock_model.delete_social_relation.assert_called_once_with(
            TEST_SOCIAL_RELATION_ID, 
            delete_mappings=True
        )
    
    def test_delete_social_relation_not_found(self):
        """Test deleting a non-existent social relation"""
        # Arrange
        self.mock_model.delete_social_relation.side_effect = ValueError(
            "Social relation with ID NON-EXISTENT not found"
        )
        
        # Act
        response = self.client.delete('/social-relations/NON-EXISTENT/delete')
        
        # Assert
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    # ==================== SOCIAL RELATION MAPPING TESTS ====================
    
    def test_list_social_relation_mappings_success(self):
        """Test listing social relation mappings with pagination"""
        # Arrange
        mock_result = {
            'status': 'success',
            'data': [SAMPLE_MAPPING],
            'pagination': {
                'page': 1,
                'limit': 10,
                'total': 1
            }
        }
        self.mock_model.list_social_relation_mappings.return_value = mock_result
        
        # Act
        response = self.client.get('/social-relation-mappings?page=1&limit=10')
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        assert 'data' in response_data
        self.mock_model.list_social_relation_mappings.assert_called_once()
    
    def test_list_social_relation_mappings_with_filters(self):
        """Test listing mappings with filters"""
        # Arrange
        mock_result = {
            'status': 'success',
            'data': [SAMPLE_MAPPING],
            'pagination': {
                'page': 1,
                'limit': 10,
                'total': 1
            }
        }
        self.mock_model.list_social_relation_mappings.return_value = mock_result
        
        # Act
        response = self.client.get(
            f'/social-relation-mappings?doc_id={TEST_DOC_ID}&article_id={TEST_ARTICLE_ID}&page=1&limit=10'
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        
        # Verify filters were passed
        call_args = self.mock_model.list_social_relation_mappings.call_args
        filters = call_args[1]['filters']
        assert 'doc_id' in filters
        assert filters['doc_id'] == TEST_DOC_ID
        assert filters['article_id'] == TEST_ARTICLE_ID
    
    def test_get_social_relation_mapping_success(self):
        """Test getting a single social relation mapping by ID"""
        # Arrange
        self.mock_model.get_social_relation_mapping_by_id.return_value = SAMPLE_MAPPING
        
        # Act
        response = self.client.get(f'/social-relation-mappings/{TEST_MAPPING_ID}')
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        assert response_data['data']['_id'] == TEST_MAPPING_ID
        self.mock_model.get_social_relation_mapping_by_id.assert_called_once_with(TEST_MAPPING_ID)
    
    def test_get_social_relation_mapping_not_found(self):
        """Test getting a non-existent mapping"""
        # Arrange
        self.mock_model.get_social_relation_mapping_by_id.return_value = None
        
        # Act
        response = self.client.get('/social-relation-mappings/680c7e5fc9b0edc6b7e99999')
        
        # Assert
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    def test_create_social_relation_mapping_success(self):
        """Test creating a new social relation mapping"""
        # Arrange
        new_mapping = {
            'doc_id': 'DOC-003',
            'article_id': 'ART-003',
            'social_relation_id': TEST_SOCIAL_RELATION_ID,
            'relation_type': 'SECONDARY',
            'created_by': 'user1'
        }
        
        created_mapping = {**new_mapping, '_id': '680c7e5fc9b0edc6b7e236ef'}
        self.mock_model.create_social_relation_mapping.return_value = created_mapping
        
        # Act
        response = self.client.post(
            '/social-relation-mappings/create',
            json=new_mapping,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 201
        response_data = response.get_json()
        assert response_data['code'] == 0
        assert 'data' in response_data
        self.mock_model.create_social_relation_mapping.assert_called_once()
    
    def test_create_social_relation_mapping_invalid_relation_id(self):
        """Test creating a mapping with invalid social_relation_id"""
        # Arrange
        new_mapping = {
            'doc_id': 'DOC-003',
            'article_id': 'ART-003',
            'social_relation_id': 'INVALID-ID',
            'relation_type': 'PRIMARY',
            'created_by': 'user1'
        }
        
        self.mock_model.create_social_relation_mapping.side_effect = ValueError(
            "Social relation INVALID-ID does not exist"
        )
        
        # Act
        response = self.client.post(
            '/social-relation-mappings/create',
            json=new_mapping,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    def test_create_social_relation_mapping_duplicate(self):
        """Test creating a duplicate mapping"""
        # Arrange
        new_mapping = {
            'doc_id': TEST_DOC_ID,
            'article_id': TEST_ARTICLE_ID,
            'social_relation_id': TEST_SOCIAL_RELATION_ID,
            'relation_type': 'PRIMARY',
            'created_by': 'user1'
        }
        
        self.mock_model.create_social_relation_mapping.side_effect = ValueError(
            "This mapping already exists"
        )
        
        # Act
        response = self.client.post(
            '/social-relation-mappings/create',
            json=new_mapping,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    def test_update_social_relation_mapping_success(self):
        """Test updating an existing social relation mapping"""
        # Arrange
        update_data = {
            'relation_type': 'SECONDARY',
            'last_modified_by': 'user2'
        }
        
        updated_mapping = {**SAMPLE_MAPPING, **update_data}
        self.mock_model.update_social_relation_mapping.return_value = updated_mapping
        
        # Act
        response = self.client.put(
            f'/social-relation-mappings/{TEST_MAPPING_ID}/update',
            json=update_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        self.mock_model.update_social_relation_mapping.assert_called_once()
        
        # Verify the call args
        call_args = self.mock_model.update_social_relation_mapping.call_args[0]
        assert call_args[0] == TEST_MAPPING_ID
    
    def test_update_social_relation_mapping_not_found(self):
        """Test updating a non-existent mapping"""
        # Arrange
        update_data = {
            'relation_type': 'SECONDARY',
            'last_modified_by': 'user2'
        }
        
        self.mock_model.update_social_relation_mapping.side_effect = ValueError(
            "Social relation mapping with ID INVALID not found"
        )
        
        # Act
        response = self.client.put(
            '/social-relation-mappings/680c7e5fc9b0edc6b7e99999/update',
            json=update_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Assert
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    def test_delete_social_relation_mapping_success(self):
        """Test deleting a social relation mapping"""
        # Arrange
        self.mock_model.delete_social_relation_mapping.return_value = {
            'mapping_id': TEST_MAPPING_ID,
            'deleted': True
        }
        
        # Act
        response = self.client.delete(f'/social-relation-mappings/{TEST_MAPPING_ID}/delete')
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['code'] == 0
        self.mock_model.delete_social_relation_mapping.assert_called_once_with(TEST_MAPPING_ID)
    
    def test_delete_social_relation_mapping_not_found(self):
        """Test deleting a non-existent mapping"""
        # Arrange
        self.mock_model.delete_social_relation_mapping.side_effect = ValueError(
            "Social relation mapping with ID INVALID not found"
        )
        
        # Act
        response = self.client.delete('/social-relation-mappings/680c7e5fc9b0edc6b7e99999/delete')
        
        # Assert
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['code'] == 1000
    
    # ==================== ERROR HANDLING TESTS ====================
    
    def test_internal_server_error_on_unexpected_exception(self):
        """Test handling of unexpected exceptions"""
        # Arrange
        self.mock_model.list_social_relations.side_effect = Exception("Database connection error")
        
        # Act
        response = self.client.get('/social-relations')
        
        # Assert
        assert response.status_code == 500
        response_data = response.get_json()
        assert response_data['code'] == 2000
        assert 'Database connection error' in response_data['message']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
