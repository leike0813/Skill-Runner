import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from server.services.schema_validator import SchemaValidator
from server.models import SkillManifest

@pytest.fixture
def mock_skill(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    
    # Create schema files
    input_schema = {
        "type": "object",
        "properties": {"input_file": {"type": "string"}},
        "required": ["input_file"]
    }
    param_schema = {
        "type": "object",
        "properties": {"divisor": {"type": "integer"}},
        "required": ["divisor"]
    }
    
    (skill_dir / "input.schema.json").write_text(json.dumps(input_schema))
    (skill_dir / "parameter.schema.json").write_text(json.dumps(param_schema))
    
    return SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json"
        }
    )

def test_validate_schema_valid(mock_skill):
    validator = SchemaValidator()
    
    # Test valid parameter
    errors = validator.validate_schema(mock_skill, {"divisor": 10}, "parameter")
    assert len(errors) == 0

    # Test valid input (file names only)
    errors = validator.validate_schema(mock_skill, {"input_file": "path/to/file"}, "input")
    assert len(errors) == 0

def test_validate_schema_invalid_type(mock_skill):
    validator = SchemaValidator()
    
    # Invalid integer
    errors = validator.validate_schema(mock_skill, {"divisor": "not-an-int"}, "parameter")
    assert len(errors) > 0
    assert "validation error" in errors[0]

def test_validate_schema_missing_required(mock_skill):
    validator = SchemaValidator()
    
    # Missing required 'divisor'
    errors = validator.validate_schema(mock_skill, {}, "parameter")
    assert len(errors) > 0
    assert "divisor" in errors[0]

def test_get_schema_keys(mock_skill):
    validator = SchemaValidator()
    
    keys = validator.get_schema_keys(mock_skill, "parameter")
    assert "divisor" in keys
    
    keys = validator.get_schema_keys(mock_skill, "input")
    assert "input_file" in keys

def test_get_schema_required(mock_skill):
    validator = SchemaValidator()
    required_params = validator.get_schema_required(mock_skill, "parameter")
    assert "divisor" in required_params

    required_inputs = validator.get_schema_required(mock_skill, "input")
    assert "input_file" in required_inputs

def test_get_schema_required_empty_list(tmp_path):
    validator = SchemaValidator()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}}
    }
    (skill_dir / "parameter.schema.json").write_text(json.dumps(schema))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"parameter": "parameter.schema.json"}
    )
    required_params = validator.get_schema_required(skill, "parameter")
    assert required_params == []

def test_get_schema_required_missing_schema_file(tmp_path):
    validator = SchemaValidator()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"input": "missing.schema.json"}
    )
    required_inputs = validator.get_schema_required(skill, "input")
    assert required_inputs == []


def test_get_input_sources_defaults_to_file(tmp_path):
    validator = SchemaValidator()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    schema = {
        "type": "object",
        "properties": {
            "input_file": {"type": "string"},
            "query": {"type": "string", "x-input-source": "inline"},
        },
        "required": ["input_file", "query"],
    }
    (skill_dir / "input.schema.json").write_text(json.dumps(schema))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"input": "input.schema.json"}
    )

    sources = validator.get_input_sources(skill)
    assert sources["input_file"] == "file"
    assert sources["query"] == "inline"
    assert validator.get_input_keys_by_source(skill, "file", required_only=True) == ["input_file"]
    assert validator.get_input_keys_by_source(skill, "inline", required_only=True) == ["query"]


def test_validate_inline_input_create_rejects_file_source_key(tmp_path):
    validator = SchemaValidator()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    schema = {
        "type": "object",
        "properties": {
            "input_file": {"type": "string"},
            "query": {"type": "string", "x-input-source": "inline"},
        },
        "required": ["query"],
    }
    (skill_dir / "input.schema.json").write_text(json.dumps(schema))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"input": "input.schema.json"}
    )
    errors = validator.validate_inline_input_create(skill, {"input_file": "abc"})
    assert errors
    assert "file-sourced" in errors[0]


def test_build_input_context_mixed_file_and_inline(tmp_path):
    validator = SchemaValidator()
    run_dir = tmp_path / "run"
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    (uploads_dir / "input_file").write_text("data")

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    schema = {
        "type": "object",
        "properties": {
            "input_file": {"type": "string"},
            "query": {"type": "string", "x-input-source": "inline"},
        },
        "required": ["input_file", "query"],
    }
    (skill_dir / "input.schema.json").write_text(json.dumps(schema))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"input": "input.schema.json"}
    )

    ctx, missing = validator.build_input_context(skill, run_dir, {"input": {"query": "hello"}})
    assert missing == []
    assert "input_file" in ctx
    assert ctx["query"] == "hello"


def test_validate_input_for_execution_reports_missing_required_file(tmp_path):
    validator = SchemaValidator()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    schema = {
        "type": "object",
        "properties": {
            "input_file": {"type": "string"},
            "query": {"type": "string", "x-input-source": "inline"},
        },
        "required": ["input_file", "query"],
    }
    (skill_dir / "input.schema.json").write_text(json.dumps(schema))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"input": "input.schema.json"}
    )

    errors = validator.validate_input_for_execution(skill, run_dir, {"input": {"query": "hello"}})
    assert errors
    assert any("Missing required input files" in e for e in errors)
