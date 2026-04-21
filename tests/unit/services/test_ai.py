"""
Unit tests for AIAnalysisService.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import json


class TestAIAnalysisService:
    """Tests for AIAnalysisService."""

    def test_analyze_rules_no_warehouse(self, app, sample_rules):
        """Test analyze_rules fails without warehouse ID."""
        from app.services.ai import AIAnalysisService

        mock_client = MagicMock()

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = None

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog.schema.table",
                    "test prompt"
                )

        assert result["success"] is False
        assert "warehouse" in result["error"].lower()

    def test_analyze_rules_success(self, app, sample_rules):
        """Test analyze_rules with successful AI response."""
        from app.services.ai import AIAnalysisService

        mock_response = MagicMock()
        mock_response.statement_id = "stmt-123"
        mock_response.status.state.value = "SUCCEEDED"
        mock_response.result.data_array = [[json.dumps({
            "summary": "Test summary",
            "rule_analysis": [],
            "coverage_assessment": "Good",
            "recommendations": [],
            "overall_quality_score": 8
        })]]

        mock_client = MagicMock()
        mock_client.statement_execution.execute_statement.return_value = mock_response
        mock_client.statement_execution.get_statement.return_value = mock_response

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = "wh-123"

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog.schema.table",
                    "test prompt"
                )

        assert result["success"] is True
        assert "analysis" in result
        assert result["analysis"]["summary"] == "Test summary"

    def test_analyze_rules_handles_exception(self, app, sample_rules):
        """Test analyze_rules handles exceptions gracefully."""
        from app.services.ai import AIAnalysisService

        mock_client = MagicMock()
        mock_client.statement_execution.execute_statement.side_effect = Exception("API Error")

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = "wh-123"

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog.schema.table",
                    "test prompt"
                )

        assert result["success"] is False
        assert "error" in result

    def test_analyze_rules_raw_response(self, app, sample_rules):
        """Test analyze_rules with non-JSON response."""
        from app.services.ai import AIAnalysisService

        mock_response = MagicMock()
        mock_response.statement_id = "stmt-123"
        mock_response.status.state.value = "SUCCEEDED"
        mock_response.result.data_array = [["This is a plain text analysis without JSON"]]

        mock_client = MagicMock()
        mock_client.statement_execution.execute_statement.return_value = mock_response
        mock_client.statement_execution.get_statement.return_value = mock_response

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = "wh-123"

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog.schema.table",
                    "test prompt"
                )

        assert result["success"] is True
        assert result["analysis"]["raw_response"] is True

    def test_analyze_rules_query_failed(self, app, sample_rules):
        """Test analyze_rules when query fails."""
        from app.services.ai import AIAnalysisService

        # First response - pending
        mock_initial_response = MagicMock()
        mock_initial_response.statement_id = "stmt-123"

        # Failed status response
        mock_failed_response = MagicMock()
        mock_failed_response.status.state.value = "FAILED"
        mock_failed_response.status.error.message = "Query execution failed"

        mock_client = MagicMock()
        mock_client.statement_execution.execute_statement.return_value = mock_initial_response
        mock_client.statement_execution.get_statement.return_value = mock_failed_response

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = "wh-123"

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog.schema.table",
                    "test prompt"
                )

        assert result["success"] is False
        assert "Query failed" in result["error"]

    def test_analyze_rules_empty_response(self, app, sample_rules):
        """Test analyze_rules with empty response."""
        from app.services.ai import AIAnalysisService

        mock_response = MagicMock()
        mock_response.statement_id = "stmt-123"
        mock_response.status.state.value = "SUCCEEDED"
        mock_response.result.data_array = []

        mock_client = MagicMock()
        mock_client.statement_execution.execute_statement.return_value = mock_response
        mock_client.statement_execution.get_statement.return_value = mock_response

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = "wh-123"

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog.schema.table",
                    "test prompt"
                )

        assert result["success"] is False
        assert "No response" in result["error"]

    def test_analyze_rules_with_special_characters(self, app, sample_rules):
        """Test analyze_rules escapes special characters in prompts."""
        from app.services.ai import AIAnalysisService

        mock_response = MagicMock()
        mock_response.statement_id = "stmt-123"
        mock_response.status.state.value = "SUCCEEDED"
        mock_response.result.data_array = [[json.dumps({
            "summary": "Test with special chars",
            "rule_analysis": [],
            "coverage_assessment": "Good",
            "recommendations": [],
            "overall_quality_score": 7
        })]]

        mock_client = MagicMock()
        mock_client.statement_execution.execute_statement.return_value = mock_response
        mock_client.statement_execution.get_statement.return_value = mock_response

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = "wh-123"

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog's.schema.table",  # Contains apostrophe
                    "Check user's data isn't null"  # Contains apostrophe
                )

        assert result["success"] is True

    def test_analyze_rules_canceled_state(self, app, sample_rules):
        """Test analyze_rules when query is canceled."""
        from app.services.ai import AIAnalysisService

        mock_initial_response = MagicMock()
        mock_initial_response.statement_id = "stmt-123"

        mock_canceled_response = MagicMock()
        mock_canceled_response.status.state.value = "CANCELED"
        mock_canceled_response.status.error = None

        mock_client = MagicMock()
        mock_client.statement_execution.execute_statement.return_value = mock_initial_response
        mock_client.statement_execution.get_statement.return_value = mock_canceled_response

        with patch('app.services.ai.databricks_service') as mock_service:
            mock_service.client = mock_client
            mock_service.get_sql_warehouse_id.return_value = "wh-123"

            with app.test_request_context():
                result = AIAnalysisService.analyze_rules(
                    sample_rules,
                    "catalog.schema.table",
                    "test prompt"
                )

        assert result["success"] is False
