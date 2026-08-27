# Cross-cutting tests

Reserved for integration/end-to-end tests that span the backend and frontend together (e.g. a real HTTP round-trip against a running Docker Compose stack). Phase 1 has no such tests yet - see `backend/tests/` for the current unit/integration test suite, and `frontend/src/App.test.tsx` for the frontend smoke test. This directory will be populated starting in Phase 2, once there is cross-service behavior worth testing end-to-end.
