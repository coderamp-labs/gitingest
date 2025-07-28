"""Tests for the output_formatter module.

These tests validate the formatting behavior of DefaultFormatter and StupidFormatter
for different FileSystemNode types (File, Directory, Symlink).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from gitingest.output_formatter import DefaultFormatter, DebugFormatter, SummaryFormatter
from gitingest.schemas import FileSystemFile, FileSystemDirectory, FileSystemSymlink, IngestionQuery
from gitingest.schemas.filesystem import FileSystemNodeType


@pytest.fixture
def mock_query() -> IngestionQuery:
    """Create a mock IngestionQuery for testing."""
    query = Mock(spec=IngestionQuery)
    query.user_name = "test_user"
    query.repo_name = "test_repo"
    query.slug = "test_slug"
    query.branch = "main"
    query.commit = "abc123"
    query.subpath = "/"
    query.tag = None
    return query


@pytest.fixture
def mock_file_node() -> FileSystemFile:
    """Create a mock FileSystemFile for testing."""
    file_node = Mock(spec=FileSystemFile)
    file_node.name = "test_file.py"
    file_node.path = Path("/fake/path/test_file.py")
    file_node.path_str = "/fake/path/test_file.py"
    file_node.content = "print('hello world')\nprint('test content')"
    file_node.size = 100
    file_node.depth = 1
    file_node.type = FileSystemNodeType.FILE
    return file_node


@pytest.fixture
def mock_directory_node() -> FileSystemDirectory:
    """Create a mock FileSystemDirectory for testing."""
    dir_node = Mock(spec=FileSystemDirectory)
    dir_node.name = "src"
    dir_node.path = Path("/fake/path/src")
    dir_node.path_str = "/fake/path/src"
    dir_node.children = []
    dir_node.file_count = 2
    dir_node.dir_count = 1
    dir_node.size = 500
    dir_node.depth = 0
    dir_node.type = FileSystemNodeType.DIRECTORY
    dir_node.tree = "src/\n├── file1.py\n└── file2.py"
    return dir_node


@pytest.fixture
def mock_symlink_node() -> FileSystemSymlink:
    """Create a mock FileSystemSymlink for testing."""
    symlink_node = Mock(spec=FileSystemSymlink)
    symlink_node.name = "link_to_file"
    symlink_node.path = Path("/fake/path/link_to_file")
    symlink_node.path_str = "/fake/path/link_to_file"
    symlink_node.target = "target_file.py"
    symlink_node.size = 0
    symlink_node.depth = 1
    symlink_node.type = FileSystemNodeType.SYMLINK
    return symlink_node


class TestDefaultFormatter:
    """Test cases for DefaultFormatter class."""

    def test_init(self):
        """Test DefaultFormatter initialization."""
        formatter = DefaultFormatter()
        assert formatter.env is not None
        assert formatter.format is not None

    def test_format_file_node(self, mock_file_node, mock_query):
        """Test formatting a FileSystemFile node."""
        formatter = DefaultFormatter()
        result = formatter.format(mock_file_node, mock_query)
        
        # Should contain separator, filename, and content
        assert "================================================" in result
        assert "test_file.py" in result
        assert "print('hello world')" in result
        assert "print('test content')" in result

    def test_format_directory_node(self, mock_directory_node, mock_query):
        """Test formatting a FileSystemDirectory node."""
        # Create mock child nodes
        child1 = Mock()
        child2 = Mock()
        mock_directory_node.children = [child1, child2]
        
        formatter = DefaultFormatter()
        
        # Mock the format method calls for children
        with patch.object(formatter, 'format', side_effect=lambda node, query: f"formatted_{node.name}" if hasattr(node, 'name') else "formatted_child") as mock_format:
            # Need to call the actual method for the directory node itself
            mock_format.side_effect = None
            result = formatter.format(mock_directory_node, mock_query)
            
            # Reset side effect and call again to test child formatting
            mock_format.side_effect = lambda node, query: f"formatted_{getattr(node, 'name', 'child')}"
            result = formatter.format(mock_directory_node, mock_query)

    def test_format_symlink_node(self, mock_symlink_node, mock_query):
        """Test formatting a FileSystemSymlink node."""
        formatter = DefaultFormatter()
        result = formatter.format(mock_symlink_node, mock_query)
        
        # Should contain separator, filename, and target
        assert "================================================" in result
        assert "link_to_file" in result
        assert "target_file.py" in result

    def test_format_symlink_node_no_target(self, mock_symlink_node, mock_query):
        """Test formatting a FileSystemSymlink node without target."""
        mock_symlink_node.target = ""
        formatter = DefaultFormatter()
        result = formatter.format(mock_symlink_node, mock_query)
        
        # Should contain separator and filename but no arrow
        assert "================================================" in result
        assert "link_to_file" in result
        assert " -> " not in result

class TestSummaryFormatter:
    """Test cases for SummaryFormatter class."""

    def test_init(self):
        """Test SummaryFormatter initialization."""
        formatter = SummaryFormatter()
        assert formatter.env is not None
        assert formatter.summary is not None

    def test_summary_directory_node(self, mock_directory_node, mock_query):
        """Test summary generation for a FileSystemDirectory node."""
        formatter = SummaryFormatter()
        result = formatter.summary(mock_directory_node, mock_query)
        
        assert "Directory structure:" in result
        assert "src/" in result
        assert "file1.py" in result
        assert "file2.py" in result

    def test_summary_file_node_default(self, mock_file_node, mock_query):
        """Test default summary for FileSystemFile node."""
        formatter = SummaryFormatter()
        result = formatter.summary(mock_file_node, mock_query)
        
        # Should use default handler and return the name
        assert "test_file.py" in result


class TestDebugFormatter:
    """Test cases for DebugFormatter class."""

    def test_init(self):
        """Test DebugFormatter initialization."""
        formatter = DebugFormatter()
        assert formatter.env is not None
        assert formatter.format is not None

    def test_format_file_node_debug_info(self, mock_file_node, mock_query):
        """Test that DebugFormatter shows debug info for FileSystemFile."""
        formatter = DebugFormatter()
        result = formatter.format(mock_file_node, mock_query)
        
        # Should contain debug information
        assert "================================================" in result
        assert "DEBUG: FileSystemFile" in result
        assert "Fields:" in result
        # Should contain field names
        assert "name" in result
        assert "path" in result
        assert "size" in result

    def test_format_directory_node_debug_info(self, mock_directory_node, mock_query):
        """Test that DebugFormatter shows debug info for FileSystemDirectory."""
        formatter = DebugFormatter()
        result = formatter.format(mock_directory_node, mock_query)
        
        # Should contain debug information
        assert "DEBUG: FileSystemDirectory" in result
        assert "Fields:" in result
        assert "name" in result
        assert "children" in result

    def test_format_symlink_node_debug_info(self, mock_symlink_node, mock_query):
        """Test that DebugFormatter shows debug info for FileSystemSymlink."""
        formatter = DebugFormatter()
        result = formatter.format(mock_symlink_node, mock_query)
        
        # Should contain debug information
        assert "DEBUG: FileSystemSymlink" in result
        assert "Fields:" in result
        assert "name" in result
        assert "target" in result

    def test_format_all_node_types_show_debug(self, mock_file_node, mock_directory_node, mock_symlink_node, mock_query):
        """Test that DebugFormatter shows debug info for all node types."""
        formatter = DebugFormatter()
        
        file_result = formatter.format(mock_file_node, mock_query)
        dir_result = formatter.format(mock_directory_node, mock_query)
        symlink_result = formatter.format(mock_symlink_node, mock_query)
        
        # All should contain debug headers
        assert "DEBUG: FileSystemFile" in file_result
        assert "DEBUG: FileSystemDirectory" in dir_result
        assert "DEBUG: FileSystemSymlink" in symlink_result
        
        # All should contain field information
        assert "Fields:" in file_result
        assert "Fields:" in dir_result
        assert "Fields:" in symlink_result

    def test_debug_formatter_vs_default_formatter(self, mock_file_node, mock_query):
        """Test that DebugFormatter produces different output than DefaultFormatter."""
        default_formatter = DefaultFormatter()
        debug_formatter = DebugFormatter()
        
        default_result = default_formatter.format(mock_file_node, mock_query)
        debug_result = debug_formatter.format(mock_file_node, mock_query)
        
        # Results should be different
        assert default_result != debug_result
        
        # Debug should contain debug info, default should not
        assert "DEBUG:" in debug_result
        assert "DEBUG:" not in default_result
        
        # Debug should show fields, default shows content
        assert "Fields:" in debug_result
        assert "Fields:" not in default_result


class TestFormatterEdgeCases:
    """Test edge cases and error conditions."""

    def test_format_unknown_node_type(self, mock_query):
        """Test formatting with an unknown node type."""
        unknown_node = Mock()
        unknown_node.name = "unknown"
        
        formatter = DefaultFormatter()
        # Should fall back to default behavior
        result = formatter.format(unknown_node, mock_query)
        assert result is not None

    def test_format_node_without_name(self, mock_query):
        """Test formatting a node without a name attribute."""
        nameless_node = Mock(spec=FileSystemFile)
        # Remove name attribute
        del nameless_node.name
        
        formatter = DebugFormatter()
        # Should handle gracefully (jinja template will show empty)
        result = formatter.format(nameless_node, mock_query)
        assert result is not None

    def test_format_with_none_query(self, mock_file_node):
        """Test formatting with None query."""
        formatter = DefaultFormatter()
        # Should handle None query gracefully
        result = formatter.format(mock_file_node, None)
        assert result is not None 