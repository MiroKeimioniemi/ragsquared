# Operations Guide

This document covers log fields, health check responses, metrics, and common failure modes for the AI Auditing System.

## Logging

The system uses structured logging via `structlog` with JSON output by default. Logs include contextual fields for request correlation.

### Log Format

Logs are emitted as JSON by default (set `LOG_JSON=0` for human-readable format). Each log entry includes:

- `timestamp`: ISO 8601 timestamp
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `event`: Log message/event name
- `logger`: Logger name (module path)
- `request_id`: Request ID for API requests (UUID)
- `audit_id`: Audit external ID (when processing audits)
- `chunk_id`: Chunk ID (when processing chunks)

### Context Fields

The following context fields are automatically added to logs:

- **request_id**: Set for each HTTP request (from `X-Request-ID` header or auto-generated)
- **audit_id**: Set when processing an audit (audit external ID)
- **chunk_id**: Set when processing a chunk (chunk ID)

### Example Log Entries

```json
{
  "timestamp": "2025-11-15T12:00:00.123456Z",
  "level": "info",
  "event": "Starting compliance runner",
  "logger": "backend.app.services.compliance_runner",
  "audit_id": "abc123",
  "is_draft": false
}
```

```json
{
  "timestamp": "2025-11-15T12:00:05.456789Z",
  "level": "info",
  "event": "metrics",
  "logger": "backend.app.services.metrics",
  "chunks_processed": 10,
  "chunks_per_minute": 120.0,
  "retry_count": 2,
  "token_usage": 50000,
  "elapsed_seconds": 5.0
}
```

### Log Levels

- **DEBUG**: Detailed diagnostic information (chunk processing steps)
- **INFO**: General informational messages (audit start/complete, metrics)
- **WARNING**: Warning messages (fallback clients, score recording failures)
- **ERROR**: Error conditions (database failures, LLM errors)
- **CRITICAL**: Critical failures (system unavailable)

### Configuration

Set log level via environment variable:
```bash
LOG_LEVEL=DEBUG  # or INFO, WARNING, ERROR, CRITICAL
LOG_JSON=1       # 1 for JSON, 0 for human-readable
```

## Health Check Endpoint

The `/healthz` endpoint provides system health status and is suitable for platform probes (Kubernetes liveness/readiness).

### Endpoint

```
GET /healthz
```

### Response Format

```json
{
  "status": "ok",
  "timestamp": "2025-11-15T12:00:00Z",
  "checks": {
    "data_root": "ok",
    "database": "ok",
    "pending_audits": 0,
    "pending_embeddings": 0
  }
}
```

### Status Values

- **ok**: All checks passed
- **degraded**: Some checks failed but system is operational (e.g., missing data root)
- **unhealthy**: Critical checks failed (e.g., database unavailable)

### HTTP Status Codes

- **200**: System is healthy (status: "ok" or "degraded")
- **503**: System is unhealthy (status: "unhealthy")

### Checks

1. **data_root**: Verifies data root directory exists
2. **database**: Tests database connectivity with a simple query
3. **pending_audits**: Count of audits in "queued" or "running" status
4. **pending_embeddings**: Count of embedding jobs in "pending" status

## Metrics

The system emits metrics to logs periodically (every 60 seconds during processing).

### Metrics Fields

- **chunks_processed**: Total number of chunks processed
- **chunks_per_minute**: Processing rate (chunks/minute)
- **retry_count**: Number of retry attempts (refinement loops)
- **token_usage**: Total tokens consumed (estimated)
- **elapsed_seconds**: Time elapsed since metrics collection started

### Metrics Emission

Metrics are automatically emitted:
- Every 60 seconds during audit processing
- At the end of each audit

### Example Metrics Log

```json
{
  "timestamp": "2025-11-15T12:01:00.123456Z",
  "level": "info",
  "event": "metrics",
  "chunks_processed": 50,
  "chunks_per_minute": 60.0,
  "retry_count": 5,
  "token_usage": 250000,
  "elapsed_seconds": 50.0
}
```

## Common Failure Modes

### Database Connection Errors

**Symptoms**: Health check shows `"database": "error"`, 503 status code

**Causes**:
- Database file locked (SQLite)
- Database file permissions
- Database URL misconfiguration

**Resolution**:
1. Check database file permissions
2. Verify `DATABASE_URL` environment variable
3. Check for concurrent database access
4. Restart the application

### Missing Data Root

**Symptoms**: Health check shows `"data_root": "missing"`, status "degraded"

**Causes**:
- Data root directory not created
- `DATA_ROOT` environment variable misconfigured

**Resolution**:
1. Run `make ensure-dirs` or `python backend/scripts/ensure_dirs.py`
2. Verify `DATA_ROOT` environment variable points to existing directory
3. Check directory permissions

### LLM API Failures

**Symptoms**: Logs show "OpenRouterError" or "ComplianceLLMClient unavailable"

**Causes**:
- Missing or invalid `OPENROUTER_API_KEY`
- API rate limits
- Network connectivity issues

**Resolution**:
1. Verify `OPENROUTER_API_KEY` is set and valid
2. Check API rate limits
3. System falls back to echo client (placeholder analysis)
4. Check network connectivity

### Chunk Processing Failures

**Symptoms**: Audit status "failed", logs show chunk processing errors

**Causes**:
- Missing chunks in database
- ChromaDB connection issues
- Context builder failures

**Resolution**:
1. Verify chunks exist for the document
2. Check ChromaDB is accessible
3. Review context builder logs for token budget issues
4. Re-run embedding pipeline if needed

### Score Recording Failures

**Symptoms**: Warning logs: "Failed to record compliance score"

**Causes**:
- Database write failures
- Missing flags for audit

**Resolution**:
1. Check database connectivity
2. Verify flags exist for the audit
3. Manually record score if needed (via ScoreTracker)

## Monitoring Recommendations

### Log Aggregation

Use a log aggregation service (e.g., ELK, Loki, CloudWatch) to:
- Correlate logs by `request_id`
- Track audit processing by `audit_id`
- Monitor error rates and patterns

### Alerting

Set up alerts for:
- Health check failures (503 status)
- High error rates in logs
- Slow processing (low `chunks_per_minute`)
- High retry counts

### Dashboards

Create dashboards showing:
- Audit processing rate
- Average chunks per minute
- Error rates by component
- Token usage trends
- Queue depth (pending audits/embeddings)

## Request ID Propagation

Request IDs are:
1. Generated for each HTTP request (or read from `X-Request-ID` header)
2. Added to response headers as `X-Request-ID`
3. Propagated through all log entries for that request
4. Used for end-to-end request correlation

To trace a request:
```bash
# Find all logs for a request ID
grep "request_id.*abc-123" logs/app.log

# Or in JSON logs
jq 'select(.request_id == "abc-123")' logs/app.log
```

## Performance Tuning

### Log Level

Set `LOG_LEVEL=WARNING` in production to reduce log volume.

### Metrics Interval

Adjust metrics emission interval in `backend/app/services/metrics.py`:
```python
emission_interval: float = 60.0  # seconds
```

### Database Connection Pooling

For production, configure SQLAlchemy connection pooling:
```python
DATABASE_URL=postgresql://user:pass@host/db?pool_size=10
```

