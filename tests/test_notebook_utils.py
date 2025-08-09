"""Tests for the ``notebook`` utils module.

These tests validate how notebooks are processed into Python-like output, ensuring that markdown/raw cells are
converted to triple-quoted blocks, code cells remain executable code, and various edge cases (multiple worksheets,
empty cells, outputs, etc.) are handled appropriately.
"""

import pytest

from gitingest.utils.notebook import process_notebook
from tests.conftest import WriteNotebookFunc


def test_process_notebook_all_cells(write_notebook: WriteNotebookFunc) -> None:
    """Test processing a notebook containing markdown, code, and raw cells.

    Given a notebook with:
      - One markdown cell
      - One code cell
      - One raw cell
    When ``process_notebook`` is invoked,
    Then markdown and raw cells should appear in triple-quoted blocks, and code cells remain as normal code.
    """
    expected_count = 4
    notebook_content = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Markdown cell"]},
            {"cell_type": "code", "source": ['print("Hello Code")']},
            {"cell_type": "raw", "source": ["<raw content>"]},
        ],
    }
    nb_path = write_notebook("all_cells.ipynb", notebook_content)
    result = process_notebook(nb_path)

    assert result.count('"""') == expected_count, (
        "Two non-code cells => 2 triple-quoted blocks => 4 total triple quotes."
    )

    # Ensure markdown and raw cells are in triple quotes
    assert "# Markdown cell" in result
    assert "<raw content>" in result

    # Ensure code cell is not in triple quotes
    assert 'print("Hello Code")' in result
    assert '"""\nprint("Hello Code")\n"""' not in result


def test_process_notebook_with_worksheets(write_notebook: WriteNotebookFunc) -> None:
    """Test a notebook containing the (as of IPEP-17 deprecated) ``worksheets`` key.

    Given a notebook that uses the ``worksheets`` key with a single worksheet,
    When ``process_notebook`` is called,
    Then a ``DeprecationWarning`` should be raised, and the content should match an equivalent notebook
    that has top-level ``cells``.
    """
    with_worksheets = {
        "worksheets": [
            {
                "cells": [
                    {"cell_type": "markdown", "source": ["# Markdown cell"]},
                    {"cell_type": "code", "source": ['print("Hello Code")']},
                    {"cell_type": "raw", "source": ["<raw content>"]},
                ],
            },
        ],
    }
    without_worksheets = with_worksheets["worksheets"][0]  # same, but no 'worksheets' key

    nb_with = write_notebook("with_worksheets.ipynb", with_worksheets)
    nb_without = write_notebook("without_worksheets.ipynb", without_worksheets)

    result_with = process_notebook(nb_with)

    # Should not raise a warning
    result_without = process_notebook(nb_without)

    assert result_with == result_without, "Content from the single worksheet should match the top-level equivalent."


def test_process_notebook_multiple_worksheets(write_notebook: WriteNotebookFunc) -> None:
    """Test a notebook containing multiple ``worksheets``.

    Given a notebook with two worksheets:
      - First with a markdown cell
      - Second with a code cell
    When ``process_notebook`` is called,
    Then a warning about multiple worksheets should be raised, and the second worksheet's content should appear
    in the final output.
    """
    multi_worksheets = {
        "worksheets": [
            {"cells": [{"cell_type": "markdown", "source": ["# First Worksheet"]}]},
            {"cells": [{"cell_type": "code", "source": ["# Second Worksheet"]}]},
        ],
    }

    single_worksheet = {
        "worksheets": [
            {"cells": [{"cell_type": "markdown", "source": ["# First Worksheet"]}]},
        ],
    }

    nb_multi = write_notebook("multiple_worksheets.ipynb", multi_worksheets)
    nb_single = write_notebook("single_worksheet.ipynb", single_worksheet)

    result_multi = process_notebook(nb_multi)

    result_single = process_notebook(nb_single)

    assert result_multi != result_single, "Two worksheets should produce more content than one."
    assert len(result_multi) > len(result_single), "The multi-worksheet notebook should have extra code content."
    assert "# First Worksheet" in result_single
    assert "# Second Worksheet" not in result_single
    assert "# First Worksheet" in result_multi
    assert "# Second Worksheet" in result_multi


def test_process_notebook_code_only(write_notebook: WriteNotebookFunc) -> None:
    """Test a notebook containing only code cells.

    Given a notebook with code cells only:
    When ``process_notebook`` is called,
    Then no triple quotes should appear in the output.
    """
    notebook_content = {
        "cells": [
            {"cell_type": "code", "source": ["print('Code Cell 1')"]},
            {"cell_type": "code", "source": ["x = 42"]},
        ],
    }
    nb_path = write_notebook("code_only.ipynb", notebook_content)
    result = process_notebook(nb_path)

    assert '"""' not in result, "No triple quotes expected when there are only code cells."
    assert "print('Code Cell 1')" in result
    assert "x = 42" in result


def test_process_notebook_markdown_only(write_notebook: WriteNotebookFunc) -> None:
    """Test a notebook with only markdown cells.

    Given a notebook with two markdown cells:
    When ``process_notebook`` is called,
    Then each markdown cell should become a triple-quoted block (2 blocks => 4 triple quotes total).
    """
    expected_count = 4
    notebook_content = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Markdown Header"]},
            {"cell_type": "markdown", "source": ["Some more markdown."]},
        ],
    }
    nb_path = write_notebook("markdown_only.ipynb", notebook_content)
    result = process_notebook(nb_path)

    assert result.count('"""') == expected_count, "Two markdown cells => 2 blocks => 4 triple quotes total."
    assert "# Markdown Header" in result
    assert "Some more markdown." in result


def test_process_notebook_raw_only(write_notebook: WriteNotebookFunc) -> None:
    """Test a notebook with only raw cells.

    Given two raw cells:
    When ``process_notebook`` is called,
    Then each raw cell should become a triple-quoted block (2 blocks => 4 triple quotes total).
    """
    expected_count = 4
    notebook_content = {
        "cells": [
            {"cell_type": "raw", "source": ["Raw content line 1"]},
            {"cell_type": "raw", "source": ["Raw content line 2"]},
        ],
    }
    nb_path = write_notebook("raw_only.ipynb", notebook_content)
    result = process_notebook(nb_path)

    assert result.count('"""') == expected_count, "Two raw cells => 2 blocks => 4 triple quotes."
    assert "Raw content line 1" in result
    assert "Raw content line 2" in result


def test_process_notebook_empty_cells(write_notebook: WriteNotebookFunc) -> None:
    """Test that cells with an empty ``source`` are skipped.

    Given a notebook with 4 cells, 3 of which have empty ``source``:
    When ``process_notebook`` is called,
    Then only the non-empty cell should appear in the output (1 block => 2 triple quotes).
    """
    expected_count = 2
    notebook_content = {
        "cells": [
            {"cell_type": "markdown", "source": []},
            {"cell_type": "code", "source": []},
            {"cell_type": "raw", "source": []},
            {"cell_type": "markdown", "source": ["# Non-empty markdown"]},
        ],
    }
    nb_path = write_notebook("empty_cells.ipynb", notebook_content)
    result = process_notebook(nb_path)

    assert result.count('"""') == expected_count, "Only one non-empty cell => 1 block => 2 triple quotes"
    assert "# Non-empty markdown" in result


def test_process_notebook_invalid_cell_type(write_notebook: WriteNotebookFunc) -> None:
    """Test a notebook with an unknown cell type.

    Given a notebook cell whose ``cell_type`` is unrecognized:
    When ``process_notebook`` is called,
    Then a ValueError should be raised.
    """
    notebook_content = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Valid markdown"]},
            {"cell_type": "unknown", "source": ["Unrecognized cell type"]},
        ],
    }
    nb_path = write_notebook("invalid_cell_type.ipynb", notebook_content)

    with pytest.raises(ValueError, match="Unknown cell type: unknown"):
        process_notebook(nb_path)


def test_process_notebook_with_output(write_notebook: WriteNotebookFunc) -> None:
    """Test a notebook that has code cells with outputs.

    Given a code cell and multiple output objects:
    When ``process_notebook`` is called with ``include_output=True``,
    Then the outputs should be appended as commented lines under the code.
    """
    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": [
                    "import matplotlib.pyplot as plt\n",
                    "print('my_data')\n",
                    "my_data = [1, 2, 3, 4, 5]\n",
                    "plt.plot(my_data)\n",
                    "my_data",
                ],
                "outputs": [
                    {"output_type": "stream", "text": ["my_data"]},
                    {"output_type": "execute_result", "data": {"text/plain": ["[1, 2, 3, 4, 5]"]}},
                    {"output_type": "display_data", "data": {"text/plain": ["<Figure size 640x480 with 1 Axes>"]}},
                ],
            },
        ],
    }

    nb_path = write_notebook("with_output.ipynb", notebook_content)
    with_output = process_notebook(nb_path, include_output=True)
    without_output = process_notebook(nb_path, include_output=False)

    expected_source = (
        "# Jupyter notebook converted to Python script.\n\n"
        "import matplotlib.pyplot as plt\n"
        "print('my_data')\n"
        "my_data = [1, 2, 3, 4, 5]\n"
        "plt.plot(my_data)\n"
        "my_data\n"
    )

    expected_output = "# Output:\n#   my_data\n#   [1, 2, 3, 4, 5]\n#   <Figure size 640x480 with 1 Axes>\n"

    expected_combined = expected_source + expected_output

    assert with_output == expected_combined, "Should include source code and comment-ified output."
    assert without_output == expected_source, "Should include only the source code without output."
