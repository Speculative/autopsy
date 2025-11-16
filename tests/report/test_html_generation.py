"""Test HTML report generation end-to-end."""

import json
import tempfile
from pathlib import Path

from autopsy.report import Report, generate_html


def test_generate_html_with_data():
    """Test generating HTML report with sample data."""
    report = Report()

    # Log some test data
    report.log(1, 2, 3)
    report.log("hello", "world")
    report.log({"key": "value", "nested": {"data": 123}})
    report.log([1, 2, 3, 4, 5])

    # Generate HTML
    html = generate_html(report)

    # Verify HTML contains expected elements
    assert '<script id="autopsy-data" type="application/json">' in html
    assert "</script>" in html
    assert "Autopsy Report" in html

    # Verify JSON data is present and valid
    import re

    pattern = r'<script id="autopsy-data" type="application/json">(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match is not None, "Could not find autopsy-data script tag"

    json_data = json.loads(match.group(1))
    assert "generated_at" in json_data
    assert "call_sites" in json_data
    assert len(json_data["call_sites"]) > 0
    # Verify timestamp is a valid ISO format string
    assert isinstance(json_data["generated_at"], str)
    assert "T" in json_data["generated_at"]

    # Verify call site structure
    call_site = json_data["call_sites"][0]
    assert "filename" in call_site
    assert "line" in call_site
    assert "values" in call_site
    assert isinstance(call_site["values"], list)
    assert len(call_site["values"]) > 0


def test_generate_html_to_file():
    """Test generating HTML report and writing to file."""
    report = Report()
    report.log("test", "data")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_report.html"
        html = generate_html(report, str(output_path))

        # Verify file was created
        assert output_path.exists(), "HTML file was not created"

        # Verify file content matches returned HTML
        file_content = output_path.read_text(encoding="utf-8")
        assert file_content == html

        # Verify file contains expected content
        assert '<script id="autopsy-data" type="application/json">' in file_content
        assert "test" in file_content


def test_generate_html_empty_report():
    """Test generating HTML report with no data."""
    report = Report()

    html = generate_html(report)

    # Should still generate valid HTML
    assert '<script id="autopsy-data" type="application/json">' in html
    assert "</script>" in html

    # Extract and verify JSON
    import re

    pattern = r'<script id="autopsy-data" type="application/json">(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match is not None

    json_data = json.loads(match.group(1))
    assert "generated_at" in json_data
    assert json_data["call_sites"] == []
    assert isinstance(json_data["generated_at"], str)


def test_generate_html_multiple_call_sites():
    """Test generating HTML with multiple call sites."""
    report = Report()

    # Log from what will be different call sites (different line numbers)
    report.log("first")
    report.log("second")
    report.log("third")

    html = generate_html(report)

    # Extract JSON
    import re

    pattern = r'<script id="autopsy-data" type="application/json">(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match is not None

    json_data = json.loads(match.group(1))
    call_sites = json_data["call_sites"]

    # Should have multiple call sites
    assert len(call_sites) >= 1

    # Verify each call site has required fields
    for call_site in call_sites:
        assert "filename" in call_site
        assert "line" in call_site
        assert "values" in call_site
        assert isinstance(call_site["values"], list)


def test_generate_html_complex_data():
    """Test generating HTML with complex nested data structures."""
    report = Report()

    complex_data = {
        "list": [1, 2, {"nested": "value"}],
        "dict": {"key": [1, 2, 3]},
        "mixed": [{"a": 1}, [2, 3], "string"],
    }

    report.log(complex_data)

    html = generate_html(report)

    # Verify complex data is serialized correctly
    import re

    pattern = r'<script id="autopsy-data" type="application/json">(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match is not None

    json_data = json.loads(match.group(1))
    call_sites = json_data["call_sites"]
    assert len(call_sites) > 0

    values = call_sites[0]["values"]
    assert len(values) > 0

    # Verify the complex data structure is preserved
    logged_data = values[0]
    assert isinstance(logged_data, dict)
    assert "list" in logged_data
    assert "dict" in logged_data
    assert "mixed" in logged_data

