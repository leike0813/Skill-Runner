# API Integration Tests

This directory contains API and UI contract integration tests that use
in-process FastAPI/TestClient flows and monkeypatch-based fixtures.

These tests are intentionally separated from engine execution integration suites
to avoid mixing contract validation with real engine execution paths.
