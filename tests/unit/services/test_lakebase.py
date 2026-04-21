"""
Unit tests for LakebaseService.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestLakebaseServiceConnection:
    """Tests for LakebaseService connection methods."""

    def test_check_connection_not_configured(self, app):
        """Test check_connection when Lakebase not configured."""
        from app.services.lakebase import LakebaseService
        from app.config import Config

        original = Config.LAKEBASE_HOST
        Config.LAKEBASE_HOST = None

        with app.test_request_context():
            result = LakebaseService.check_connection()

        assert result["connected"] is False
        assert result["configured"] is False

        Config.LAKEBASE_HOST = original

    def test_check_connection_no_token(self, app):
        """Test check_connection without OAuth token."""
        from app.services.lakebase import LakebaseService
        from app.config import Config

        original = Config.LAKEBASE_HOST
        Config.LAKEBASE_HOST = "test-host.cloud.databricks.com"

        with app.test_request_context():
            result = LakebaseService.check_connection()

        assert result["connected"] is False
        assert result["configured"] is True
        assert "OAuth token" in result["message"] or "authenticated" in result["message"]

        Config.LAKEBASE_HOST = original

    def test_get_user_oauth_credentials_no_token(self, app):
        """Test get_user_oauth_credentials raises without token."""
        from app.services.lakebase import LakebaseService

        with app.test_request_context():
            with pytest.raises(Exception) as exc_info:
                LakebaseService.get_user_oauth_credentials()

            assert "OAuth token" in str(exc_info.value) or "authenticated" in str(exc_info.value)


class TestLakebaseServiceOperations:
    """Tests for LakebaseService data operations."""

    def test_get_next_version_default(self, app, sample_rules):
        """Test get_next_version returns 1 on error."""
        from app.services.lakebase import LakebaseService

        with patch.object(LakebaseService, 'get_connection') as mock_conn:
            mock_conn.side_effect = Exception("Connection failed")

            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token'}
            ):
                version = LakebaseService.get_next_version("catalog.schema.table")

        assert version == 1

    def test_save_rules_success(self, app, sample_rules):
        """Test save_rules with mocked connection."""
        from app.services.lakebase import LakebaseService
        import uuid
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            str(uuid.uuid4()),
            1,
            datetime.now()
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(LakebaseService, 'get_connection', return_value=mock_conn):
            with patch.object(LakebaseService, 'init_table', return_value=True):
                with patch.object(LakebaseService, 'get_next_version', return_value=1):
                    with app.test_request_context(
                        headers={'x-forwarded-access-token': 'test-token'}
                    ):
                        result = LakebaseService.save_rules(
                            table_name="catalog.schema.table",
                            rules=sample_rules,
                            user_prompt="test prompt"
                        )

        assert result["success"] is True
        assert result["version"] == 1

    def test_get_history_success(self, app):
        """Test get_history with mocked connection."""
        from app.services.lakebase import LakebaseService
        import uuid
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                uuid.uuid4(),
                1,
                [{"check": {"function": "is_not_null"}}],
                "test prompt",
                {"summary": "test"},
                datetime.now(),
                True
            )
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(LakebaseService, 'get_connection', return_value=mock_conn):
            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token'}
            ):
                result = LakebaseService.get_history("catalog.schema.table")

        assert result["success"] is True
        assert len(result["history"]) == 1
        assert result["history"][0]["version"] == 1

    def test_get_history_error(self, app):
        """Test get_history handles errors gracefully."""
        from app.services.lakebase import LakebaseService

        with patch.object(LakebaseService, 'get_connection') as mock_conn:
            mock_conn.side_effect = Exception("Connection failed")

            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token'}
            ):
                result = LakebaseService.get_history("catalog.schema.table")

        assert result["success"] is False
        assert "error" in result

    def test_save_rules_error(self, app, sample_rules):
        """Test save_rules handles errors gracefully."""
        from app.services.lakebase import LakebaseService

        with patch.object(LakebaseService, 'init_table', return_value=True):
            with patch.object(LakebaseService, 'get_connection') as mock_conn:
                mock_conn.side_effect = Exception("Database error")

                with app.test_request_context(
                    headers={'x-forwarded-access-token': 'test-token'}
                ):
                    result = LakebaseService.save_rules(
                        table_name="catalog.schema.table",
                        rules=sample_rules,
                        user_prompt="test prompt"
                    )

        assert result["success"] is False
        assert "error" in result

    def test_save_rules_with_metadata(self, app, sample_rules):
        """Test save_rules with optional metadata and ai_summary."""
        from app.services.lakebase import LakebaseService
        import uuid
        from datetime import datetime

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            str(uuid.uuid4()),
            2,
            datetime.now()
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(LakebaseService, 'get_connection', return_value=mock_conn):
            with patch.object(LakebaseService, 'init_table', return_value=True):
                with patch.object(LakebaseService, 'get_next_version', return_value=2):
                    with app.test_request_context(
                        headers={'x-forwarded-access-token': 'test-token'}
                    ):
                        result = LakebaseService.save_rules(
                            table_name="catalog.schema.table",
                            rules=sample_rules,
                            user_prompt="test prompt",
                            ai_summary={"quality_score": 8},
                            metadata={"source": "test"}
                        )

        assert result["success"] is True
        assert result["version"] == 2


class TestLakebaseServiceInitialization:
    """Tests for LakebaseService table initialization."""

    def test_init_table_success(self, app):
        """Test init_table creates table successfully."""
        from app.services.lakebase import LakebaseService

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(LakebaseService, 'get_connection', return_value=mock_conn):
            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token'}
            ):
                result = LakebaseService.init_table()

        assert result is True
        # Verify CREATE TABLE was called
        assert mock_cursor.execute.call_count >= 1
        mock_conn.commit.assert_called_once()

    def test_init_table_error(self, app):
        """Test init_table handles errors."""
        from app.services.lakebase import LakebaseService

        with patch.object(LakebaseService, 'get_connection') as mock_conn:
            mock_conn.side_effect = Exception("Connection failed")

            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token'}
            ):
                result = LakebaseService.init_table()

        assert result is False

    def test_get_next_version_success(self, app):
        """Test get_next_version returns correct version."""
        from app.services.lakebase import LakebaseService

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(LakebaseService, 'get_connection', return_value=mock_conn):
            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token'}
            ):
                version = LakebaseService.get_next_version("catalog.schema.table")

        assert version == 5


class TestLakebaseServiceCheckConnection:
    """Tests for LakebaseService connection checking."""

    def test_check_connection_success(self, app):
        """Test check_connection with successful connection."""
        from app.services.lakebase import LakebaseService
        from app.config import Config

        original = Config.LAKEBASE_HOST
        Config.LAKEBASE_HOST = "test-host.cloud.databricks.com"

        mock_conn = MagicMock()

        with patch.object(LakebaseService, 'get_connection', return_value=mock_conn):
            with patch.object(
                LakebaseService,
                'get_user_oauth_credentials',
                return_value=("user@example.com", "token")
            ):
                with app.test_request_context(
                    headers={'x-forwarded-access-token': 'test-token'}
                ):
                    result = LakebaseService.check_connection()

        Config.LAKEBASE_HOST = original

        assert result["connected"] is True
        assert result["configured"] is True
        assert result["user"] == "user@example.com"

    def test_check_connection_error(self, app):
        """Test check_connection with connection error."""
        from app.services.lakebase import LakebaseService
        from app.config import Config

        original = Config.LAKEBASE_HOST
        Config.LAKEBASE_HOST = "test-host.cloud.databricks.com"

        with patch.object(LakebaseService, 'get_connection') as mock_conn:
            mock_conn.side_effect = Exception("Connection refused")

            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token'}
            ):
                result = LakebaseService.check_connection()

        Config.LAKEBASE_HOST = original

        assert result["connected"] is False
        assert result["configured"] is True
        assert "error" in result


class TestLakebaseServiceCredentials:
    """Tests for OAuth credentials handling."""

    def test_get_user_oauth_credentials_with_email(self, app):
        """Test get_user_oauth_credentials with email in headers."""
        from app.services.lakebase import LakebaseService

        with app.test_request_context(
            headers={
                'x-forwarded-access-token': 'test-token-123',
                'x-forwarded-email': 'user@example.com'
            }
        ):
            email, token = LakebaseService.get_user_oauth_credentials()

        assert email == "user@example.com"
        assert token == "test-token-123"

    def test_get_user_oauth_credentials_fetches_email(self, app):
        """Test get_user_oauth_credentials fetches email from API."""
        from app.services.lakebase import LakebaseService

        mock_user = MagicMock()
        mock_user.user_name = "fetched@example.com"

        mock_ws = MagicMock()
        mock_ws.current_user.me.return_value = mock_user

        with patch('app.services.lakebase.WorkspaceClient', return_value=mock_ws):
            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token-123'}
            ):
                email, token = LakebaseService.get_user_oauth_credentials()

        assert email == "fetched@example.com"
        assert token == "test-token-123"

    def test_get_user_oauth_credentials_fetch_error(self, app):
        """Test get_user_oauth_credentials raises on fetch error."""
        from app.services.lakebase import LakebaseService

        with patch('app.services.lakebase.WorkspaceClient') as mock_ws:
            mock_ws.return_value.current_user.me.side_effect = Exception("API error")

            with app.test_request_context(
                headers={'x-forwarded-access-token': 'test-token-123'}
            ):
                with pytest.raises(Exception) as exc_info:
                    LakebaseService.get_user_oauth_credentials()

                assert "Could not determine user email" in str(exc_info.value)
