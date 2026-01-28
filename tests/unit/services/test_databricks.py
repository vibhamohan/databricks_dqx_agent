"""
Unit tests for DatabricksService.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestDatabricksServiceInit:
    """Tests for DatabricksService initialization."""

    def test_service_initialization(self):
        """Test service initializes correctly."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()
        assert service._sdk_config is None

    def test_get_sql_warehouse_id(self):
        """Test getting SQL warehouse ID from config."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()
        warehouse_id = service.get_sql_warehouse_id()
        # Set in conftest.py
        assert warehouse_id == "test-warehouse-id"


class TestDatabricksServiceHelpers:
    """Tests for DatabricksService helper methods."""

    def test_get_host_from_config(self):
        """Test getting host from config."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()
        host = service._get_host()
        assert host == "https://test-workspace.cloud.databricks.com"

    def test_get_sql_http_path(self):
        """Test SQL HTTP path generation."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()
        http_path = service._get_sql_http_path()
        assert http_path == "/sql/1.0/warehouses/test-warehouse-id"

    def test_get_user_token_no_context(self):
        """Test getting user token outside request context."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()
        token = service._get_user_token()
        assert token is None


class TestDatabricksServiceCatalogOperations:
    """Tests for Unity Catalog operations."""

    def test_get_catalogs_with_mock(self, app):
        """Test get_catalogs with mocked SQL connection."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql') as mock_sql:
            mock_sql.return_value = ["main", "samples", "hive_metastore"]

            with app.test_request_context():
                catalogs = service.get_catalogs()

            assert catalogs == ["main", "samples", "hive_metastore"]
            mock_sql.assert_called_once_with("SHOW CATALOGS")

    def test_get_catalogs_error_returns_main(self, app):
        """Test get_catalogs returns ['main'] on error."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql') as mock_sql:
            mock_sql.side_effect = Exception("Connection error")

            with app.test_request_context():
                catalogs = service.get_catalogs()

            assert catalogs == ["main"]

    def test_get_schemas_with_mock(self, app):
        """Test get_schemas with mocked SQL connection."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql') as mock_sql:
            mock_sql.return_value = ["default", "sales", "analytics"]

            with app.test_request_context():
                schemas = service.get_schemas("main")

            assert schemas == ["default", "sales", "analytics"]
            mock_sql.assert_called_once_with("SHOW SCHEMAS IN `main`")

    def test_get_tables_with_mock(self, app):
        """Test get_tables with mocked SQL connection."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql_with_schema') as mock_sql:
            mock_sql.return_value = {
                "rows": [
                    {"database": "default", "tableName": "customers", "isTemporary": False},
                    {"database": "default", "tableName": "orders", "isTemporary": False}
                ]
            }

            with app.test_request_context():
                tables = service.get_tables("main", "default")

            assert tables == ["customers", "orders"]


class TestDatabricksServiceJobOperations:
    """Tests for job operations."""

    def test_trigger_dq_job_not_configured(self):
        """Test trigger_dq_job when job ID not configured."""
        from app.services.databricks import DatabricksService
        from app.config import Config

        service = DatabricksService()

        original = Config.DQ_GENERATION_JOB_ID
        Config.DQ_GENERATION_JOB_ID = None

        result = service.trigger_dq_job("catalog.schema.table", "test prompt")

        assert "error" in result
        assert "not configured" in result["error"]

        Config.DQ_GENERATION_JOB_ID = original

    def test_trigger_validation_job_not_configured(self):
        """Test trigger_validation_job when job ID not configured."""
        from app.services.databricks import DatabricksService
        from app.config import Config

        service = DatabricksService()

        original = Config.DQ_VALIDATION_JOB_ID
        Config.DQ_VALIDATION_JOB_ID = None

        result = service.trigger_validation_job("catalog.schema.table", [])

        assert "error" in result
        assert "not configured" in result["error"]

        Config.DQ_VALIDATION_JOB_ID = original

    def test_trigger_dq_job_with_mock(self, app):
        """Test trigger_dq_job with mocked WorkspaceClient."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.run_id = 12345
        mock_client.jobs.run_now.return_value = mock_response

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.trigger_dq_job(
                "catalog.schema.table",
                "Validate all columns are not null"
            )

        assert result == {"run_id": 12345}

    def test_trigger_dq_job_with_sample_limit(self, app):
        """Test trigger_dq_job with sample_limit parameter."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.run_id = 12345
        mock_client.jobs.run_now.return_value = mock_response

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.trigger_dq_job(
                "catalog.schema.table",
                "Validate columns",
                sample_limit=500
            )

        assert result == {"run_id": 12345}
        # Verify sample_limit was passed in job_parameters
        call_args = mock_client.jobs.run_now.call_args
        assert "sample_limit" in call_args.kwargs["job_parameters"]
        assert call_args.kwargs["job_parameters"]["sample_limit"] == "500"

    def test_trigger_dq_job_error(self, app):
        """Test trigger_dq_job handles errors."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_client = MagicMock()
        mock_client.jobs.run_now.side_effect = Exception("Job trigger failed")

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.trigger_dq_job(
                "catalog.schema.table",
                "Test prompt"
            )

        assert "error" in result
        assert "Job trigger failed" in result["error"]

    def test_trigger_validation_job_success(self, app):
        """Test trigger_validation_job with mocked WorkspaceClient."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.run_id = 67890
        mock_client.jobs.run_now.return_value = mock_response

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.trigger_validation_job(
                "catalog.schema.table",
                [{"check": {"function": "is_not_null"}}]
            )

        assert result == {"run_id": 67890}

    def test_trigger_validation_job_error(self, app):
        """Test trigger_validation_job handles errors."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_client = MagicMock()
        mock_client.jobs.run_now.side_effect = Exception("Validation job failed")

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.trigger_validation_job(
                "catalog.schema.table",
                []
            )

        assert "error" in result


class TestDatabricksServiceJobStatus:
    """Tests for job status operations."""

    def test_get_job_status_completed_success(self, app):
        """Test get_job_status with completed successful job."""
        from app.services.databricks import DatabricksService
        from databricks.sdk.service.jobs import RunLifeCycleState, RunResultState

        service = DatabricksService()

        mock_run = MagicMock()
        mock_run.state.life_cycle_state = RunLifeCycleState.TERMINATED
        mock_run.state.result_state = RunResultState.SUCCESS
        mock_run.tasks = []
        mock_run.run_id = 12345

        mock_output = MagicMock()
        mock_output.notebook_output.result = '{"rules": []}'

        mock_client = MagicMock()
        mock_client.jobs.get_run.return_value = mock_run
        mock_client.jobs.get_run_output.return_value = mock_output

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.get_job_status(12345)

        assert result["status"] == "completed"
        assert result["result"] == {"rules": []}

    def test_get_job_status_completed_failed(self, app):
        """Test get_job_status with completed failed job."""
        from app.services.databricks import DatabricksService
        from databricks.sdk.service.jobs import RunLifeCycleState, RunResultState

        service = DatabricksService()

        mock_run = MagicMock()
        mock_run.state.life_cycle_state = RunLifeCycleState.TERMINATED
        mock_run.state.result_state = RunResultState.FAILED
        mock_run.state.state_message = "Job execution failed"

        mock_client = MagicMock()
        mock_client.jobs.get_run.return_value = mock_run

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.get_job_status(12345)

        assert result["status"] == "failed"
        assert result["message"] == "Job execution failed"

    def test_get_job_status_running(self, app):
        """Test get_job_status with running job."""
        from app.services.databricks import DatabricksService
        from databricks.sdk.service.jobs import RunLifeCycleState

        service = DatabricksService()

        mock_run = MagicMock()
        mock_run.state.life_cycle_state = RunLifeCycleState.RUNNING

        mock_client = MagicMock()
        mock_client.jobs.get_run.return_value = mock_run

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.get_job_status(12345)

        assert result["status"] == "running"

    def test_get_job_status_internal_error(self, app):
        """Test get_job_status with internal error."""
        from app.services.databricks import DatabricksService
        from databricks.sdk.service.jobs import RunLifeCycleState

        service = DatabricksService()

        mock_run = MagicMock()
        mock_run.state.life_cycle_state = RunLifeCycleState.INTERNAL_ERROR
        mock_run.state.state_message = "Internal cluster error"

        mock_client = MagicMock()
        mock_client.jobs.get_run.return_value = mock_run

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.get_job_status(12345)

        assert result["status"] == "error"
        assert result["message"] == "Internal cluster error"

    def test_get_job_status_exception(self, app):
        """Test get_job_status handles exceptions."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_client = MagicMock()
        mock_client.jobs.get_run.side_effect = Exception("API error")

        with patch.object(service, '_get_client', return_value=mock_client):
            result = service.get_job_status(12345)

        assert result["status"] == "error"
        assert "API error" in result["message"]

    def test_get_job_output_with_tasks(self, app):
        """Test _get_job_output with task-based job."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_task = MagicMock()
        mock_task.run_id = 99999

        mock_run = MagicMock()
        mock_run.tasks = [mock_task]

        mock_output = MagicMock()
        mock_output.notebook_output.result = '{"data": "test"}'

        mock_client = MagicMock()
        mock_client.jobs.get_run_output.return_value = mock_output

        result = service._get_job_output(mock_run, mock_client)
        assert result == {"data": "test"}

    def test_get_job_output_non_json(self, app):
        """Test _get_job_output with non-JSON result."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_run = MagicMock()
        mock_run.tasks = []
        mock_run.run_id = 12345

        mock_output = MagicMock()
        mock_output.notebook_output.result = "Plain text result"

        mock_client = MagicMock()
        mock_client.jobs.get_run_output.return_value = mock_output

        result = service._get_job_output(mock_run, mock_client)
        assert result == "Plain text result"


class TestDatabricksServiceSQLOperations:
    """Tests for SQL operations."""

    def test_execute_sql_success(self, app):
        """Test execute_sql with successful query."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("value1",), ("value2",), ("value3",)]

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(service, '_get_sql_connection', return_value=mock_conn):
            result = service.execute_sql("SELECT name FROM test")

        assert result == ["value1", "value2", "value3"]

    def test_execute_sql_empty_result(self, app):
        """Test execute_sql with empty result."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(service, '_get_sql_connection', return_value=mock_conn):
            result = service.execute_sql("SELECT name FROM empty_table")

        assert result == []

    def test_execute_sql_with_schema_success(self, app):
        """Test execute_sql_with_schema with successful query."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",), ("value",)]
        mock_cursor.fetchall.return_value = [
            (1, "test1", 100),
            (2, "test2", 200)
        ]

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(service, '_get_sql_connection', return_value=mock_conn):
            result = service.execute_sql_with_schema("SELECT * FROM test")

        assert result["columns"] == ["id", "name", "value"]
        assert result["row_count"] == 2
        assert result["rows"][0] == {"id": 1, "name": "test1", "value": 100}

    def test_get_schemas_error(self, app):
        """Test get_schemas returns default on error."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql') as mock_sql:
            mock_sql.side_effect = Exception("Schema query failed")

            with app.test_request_context():
                schemas = service.get_schemas("main")

        assert schemas == ["default"]

    def test_get_tables_error(self, app):
        """Test get_tables returns empty list on error."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql_with_schema') as mock_sql:
            mock_sql.side_effect = Exception("Tables query failed")

            with app.test_request_context():
                tables = service.get_tables("main", "default")

        assert tables == []

    def test_get_tables_empty_result(self, app):
        """Test get_tables with empty result."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql_with_schema') as mock_sql:
            mock_sql.return_value = {"rows": []}

            with app.test_request_context():
                tables = service.get_tables("main", "default")

        assert tables == []

    def test_get_table_sample_success(self, app):
        """Test get_table_sample with successful query."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql_with_schema') as mock_sql:
            mock_sql.return_value = {
                "columns": ["id", "name"],
                "rows": [{"id": 1, "name": "test"}],
                "row_count": 1
            }

            with app.test_request_context():
                result = service.get_table_sample("main.default.test", limit=50)

        assert result["columns"] == ["id", "name"]
        assert result["row_count"] == 1

    def test_get_table_sample_error(self, app):
        """Test get_table_sample returns empty on error."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch.object(service, 'execute_sql_with_schema') as mock_sql:
            mock_sql.side_effect = Exception("Sample query failed")

            with app.test_request_context():
                result = service.get_table_sample("main.default.test")

        assert result["columns"] == []
        assert result["row_count"] == 0
        assert "error" in result


class TestDatabricksServiceAuthentication:
    """Tests for authentication methods."""

    def test_get_user_token_with_token(self, app):
        """Test _get_user_token with token in headers."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with app.test_request_context(
            headers={'x-forwarded-access-token': 'user-token-123'}
        ):
            token = service._get_user_token()

        assert token == "user-token-123"

    def test_get_client_with_user_token(self, app):
        """Test _get_client with user token."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with app.test_request_context(
            headers={'x-forwarded-access-token': 'user-token-123'}
        ):
            with patch('app.services.databricks.WorkspaceClient') as mock_ws:
                mock_ws.return_value = MagicMock()
                client = service._get_client(use_user_token=True)

                mock_ws.assert_called_once()
                call_kwargs = mock_ws.call_args.kwargs
                assert call_kwargs['token'] == 'user-token-123'
                assert call_kwargs['auth_type'] == 'pat'

    def test_get_client_without_user_token(self, app):
        """Test _get_client without user token uses config."""
        from app.services.databricks import DatabricksService
        from app.config import Config

        service = DatabricksService()

        with app.test_request_context():
            with patch('app.services.databricks.WorkspaceClient') as mock_ws:
                mock_ws.return_value = MagicMock()
                client = service._get_client(use_user_token=True)

                # Should use Config values
                mock_ws.assert_called_once()

    def test_get_sdk_config_success(self, app):
        """Test _get_sdk_config successful initialization."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        mock_config = MagicMock()
        with patch('app.services.databricks.SdkConfig', return_value=mock_config):
            result = service._get_sdk_config()

        assert result == mock_config
        assert service._sdk_config == mock_config

    def test_get_sdk_config_failure(self, app):
        """Test _get_sdk_config handles initialization failure."""
        from app.services.databricks import DatabricksService

        service = DatabricksService()

        with patch('app.services.databricks.SdkConfig', side_effect=Exception("Config error")):
            result = service._get_sdk_config()

        assert result is None

    def test_get_host_from_sdk_config(self, app):
        """Test _get_host falls back to SDK config."""
        from app.services.databricks import DatabricksService
        from app.config import Config

        service = DatabricksService()

        # Temporarily clear Config values
        original_host = Config.DATABRICKS_HOST
        Config.DATABRICKS_HOST = None

        mock_sdk_config = MagicMock()
        mock_sdk_config.host = "https://sdk-host.cloud.databricks.com"

        with patch.object(service, '_get_sdk_config', return_value=mock_sdk_config):
            with patch.dict('os.environ', {'DATABRICKS_HOST': ''}):
                host = service._get_host()

        Config.DATABRICKS_HOST = original_host
        assert host == "https://sdk-host.cloud.databricks.com"
