from pathlib import Path
from unittest.mock import Mock
from gitingest.output_formatter import DefaultFormatter
from gitingest.schemas.filesystem import ContextV1, GitRepository, FileSystemFile

# Create a mock query
mock_query = Mock()
mock_query.user_name = "test_user"
mock_query.repo_name = "test_repo"

# Create a simple file
mock_file = FileSystemFile(
    name="test.py",
    path_str="test.py", 
    path=Path("test.py"),
)
mock_file.content = "print('hello world')"

# Create a git repository with the file
mock_repo = GitRepository(
    name="test_repo",
    path_str="",
    path=Path("."),
    children=[mock_file]
)

# Create context
context = ContextV1([mock_repo], mock_query)

# Test formatting
formatter = DefaultFormatter()
result = formatter.format(context, mock_query)
print("RESULT:")
print(repr(result))
print("\nFORMATTED:")
print(result) 