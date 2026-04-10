from pathlib import Path

from mcp_code_review.conventions import load_conventions, auto_detect_language


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_conventions_from_yaml():
    conventions = load_conventions(FIXTURES / "sample_codereview.yml")
    assert conventions.language == "python"
    assert conventions.locale == "it"
    assert "*/migrations/*" in conventions.ignore_patterns
    assert conventions.severity_overrides.get("E501") == "info"
    assert conventions.custom_rules.get("max_file_lines") == 500


def test_load_conventions_file_not_found():
    conventions = load_conventions(Path("/nonexistent/.codereview.yml"))
    assert conventions.language == "unknown"
    assert conventions.locale == "en"


def test_auto_detect_python_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    lang, framework = auto_detect_language(tmp_path)
    assert lang == "python"


def test_auto_detect_django(tmp_path):
    settings = tmp_path / "myapp" / "settings.py"
    settings.parent.mkdir()
    settings.write_text("INSTALLED_APPS = ['django.contrib.admin']")
    lang, framework = auto_detect_language(tmp_path)
    assert lang == "python"
    assert framework == "django"


def test_auto_detect_unknown(tmp_path):
    lang, framework = auto_detect_language(tmp_path)
    assert lang == "unknown"
    assert framework is None
