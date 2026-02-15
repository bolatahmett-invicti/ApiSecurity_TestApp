# API Security Scanner Test Application

Test application for the Universal Polyglot API Scanner v5.0 with AI-powered enrichment.

## 🚀 Features

This repository demonstrates the automated API security scanning workflow using:

- **Universal Polyglot API Scanner v5.0** - AI-enriched API discovery
- **GitHub Actions** - Automated CI/CD pipeline
- **Invicti DAST** - Comprehensive security testing
- **AI Enrichment** - Claude-powered schema generation and test payloads

## 📋 Workflow Overview

The GitHub Actions workflow (`.github/workflows/security.yml`) automatically:

1. **Scans** your codebase for API endpoints
2. **Generates** AI-enriched OpenAPI specifications with:
   - Complete parameter definitions
   - Request/response schemas with examples
   - Authentication configurations
   - Security test payloads (valid, edge cases, attacks, fuzz)
3. **Detects** API changes on pull requests
4. **Uploads** to Invicti DAST for security testing
5. **Comments** on PRs with scan results

## 🔧 Setup

### Required GitHub Secrets

Go to **Settings > Secrets and variables > Actions** and add:

#### Invicti DAST Credentials (Required)

| Secret | Description | Required |
|--------|-------------|----------|
| `INVICTI_URL` | Invicti instance URL | Yes |
| `INVICTI_USER` | Invicti API user ID | Yes |
| `INVICTI_TOKEN` | Invicti API token | Yes |
| `INVICTI_WEBSITE_ID` | Target website ID | Yes |

#### AI Provider Credentials (Optional - At Least One for AI Enrichment)

| Secret | Provider | Description | Get Key |
|--------|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic Claude (Default) | Claude API key | [console.anthropic.com](https://console.anthropic.com/) |
| `OPENAI_API_KEY` | OpenAI GPT-4 | OpenAI API key | [platform.openai.com](https://platform.openai.com/api-keys) |
| `GOOGLE_API_KEY` | Google Gemini | Gemini API key | [makersuite.google.com](https://makersuite.google.com/app/apikey) |
| `AWS_ACCESS_KEY_ID` | AWS Bedrock | AWS access key | [AWS Console](https://console.aws.amazon.com/) |
| `AWS_SECRET_ACCESS_KEY` | AWS Bedrock | AWS secret key | [AWS Console](https://console.aws.amazon.com/) |

**Note:** AI enrichment will be disabled if no provider API key is configured, falling back to basic scan.

### Choosing an AI Provider

**Anthropic Claude (Default - Recommended)**
- Best balance of quality, speed, and cost
- Models: claude-sonnet-4-5-20250929 (default), claude-opus-4-6, claude-haiku-4-5-20251001
- Cost with Phase 3 Hybrid Architecture: ~$0.65-1.00 per 100 endpoints (87-90% reduction!)
- Previous cost: ~$3-5 per 100 endpoints

**OpenAI GPT-4**
- Wide availability and familiarity
- Models: gpt-4-turbo (default), gpt-4o, gpt-4o-mini
- Cost: Similar to Claude

**Google Gemini**
- Competitive pricing
- Models: gemini-1.5-pro (default), gemini-1.5-flash
- Cost: Lower than Claude/GPT-4

**AWS Bedrock**
- Enterprise deployments with AWS infrastructure
- Models: Claude via Bedrock, Llama 3, Mistral
- Cost: Pay-as-you-go pricing through AWS

## 🎯 Usage

### Automatic Scans

The workflow runs automatically on:
- **Push** to `main`, `master`, or `develop` branches
- **Pull requests** to `main` or `master`

### Manual Trigger

Run manually with custom options:

1. Go to **Actions** tab
2. Select **API Security Scanner** workflow
3. Click **Run workflow**
4. Choose options:
   - **Upload to Invicti DAST**: Enable/disable Invicti upload
   - **Enable AI enrichment**: Enable/disable AI-powered enrichment
   - **AI Provider**: Select provider (anthropic, openai, gemini, bedrock)

### Local Testing

Test the scanner locally with Docker:

```bash
# Basic scan (no AI)
docker run --rm \
  -v $(pwd):/code \
  -v $(pwd)/output:/output \
  bolatahmett/api-scanner:latest

# AI-enriched scan with Anthropic Claude (default)
docker run --rm \
  -v $(pwd):/code \
  -v $(pwd)/output:/output \
  -e SCANNER_AI_ENRICH=true \
  -e LLM_PROVIDER=anthropic \
  -e ANTHROPIC_API_KEY=sk-ant-your-key \
  bolatahmett/api-scanner:latest

# AI-enriched scan with OpenAI GPT-4
docker run --rm \
  -v $(pwd):/code \
  -v $(pwd)/output:/output \
  -e SCANNER_AI_ENRICH=true \
  -e LLM_PROVIDER=openai \
  -e OPENAI_API_KEY=sk-your-key \
  bolatahmett/api-scanner:latest

# AI-enriched scan with Google Gemini
docker run --rm \
  -v $(pwd):/code \
  -v $(pwd)/output:/output \
  -e SCANNER_AI_ENRICH=true \
  -e LLM_PROVIDER=gemini \
  -e GOOGLE_API_KEY=your-key \
  bolatahmett/api-scanner:latest

# AI-enriched scan with AWS Bedrock
docker run --rm \
  -v $(pwd):/code \
  -v $(pwd)/output:/output \
  -e SCANNER_AI_ENRICH=true \
  -e LLM_PROVIDER=bedrock \
  -e AWS_ACCESS_KEY_ID=your-access-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret-key \
  -e AWS_REGION=us-east-1 \
  bolatahmett/api-scanner:latest
```

## 📊 AI Enrichment Benefits

When AI enrichment is enabled (with `ANTHROPIC_API_KEY`):

### Before (Basic Scan)
```json
{
  "paths": {
    "/api/users": {
      "post": {
        "summary": "POST /api/users"
      }
    }
  }
}
```

### After (AI-Enriched)
```json
{
  "paths": {
    "/api/users": {
      "post": {
        "summary": "Create new user",
        "parameters": [
          {
            "name": "Content-Type",
            "in": "header",
            "required": true,
            "schema": {"type": "string", "enum": ["application/json"]}
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "email": {"type": "string", "format": "email"},
                  "username": {"type": "string", "minLength": 3, "maxLength": 50},
                  "password": {"type": "string", "minLength": 8}
                },
                "required": ["email", "username", "password"]
              },
              "examples": {
                "valid": {
                  "value": {
                    "email": "user@example.com",
                    "username": "john_doe",
                    "password": "SecurePass123!"
                  }
                }
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "User created successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": {"type": "integer"},
                    "email": {"type": "string"},
                    "username": {"type": "string"}
                  }
                }
              }
            }
          },
          "400": {"description": "Invalid input"},
          "409": {"description": "User already exists"}
        },
        "security": [{"bearerAuth": []}],
        "x-test-payloads": {
          "valid": [...],
          "edge_cases": [...],
          "security": [
            {
              "name": "sql_injection",
              "payload": {
                "username": "admin' OR '1'='1",
                "email": "test@example.com",
                "password": "password"
              }
            },
            {
              "name": "xss_injection",
              "payload": {
                "username": "<script>alert('XSS')</script>",
                "email": "test@example.com",
                "password": "password"
              }
            }
          ],
          "fuzz": [...]
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "bearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT"
      }
    }
  },
  "x-ai-enrichment": {
    "enabled": true,
    "auth_config": {
      "auth_mechanisms": [...],
      "test_sequence": [...]
    },
    "dependencies": {
      "test_sequences": [...]
    }
  }
}
```

### Results

- ✅ **95%+ specification completeness** (vs 40% with basic scan)
- ✅ **98% test coverage** in Invicti
- ✅ **80% reduction in false negatives**
- ✅ **Zero manual spec writing**

## 💰 Cost Optimization

### Phase 3 Hybrid Architecture (87-90% Cost Reduction!)

The scanner now uses a hybrid approach: **deterministic Python code** for pattern-based tasks + **selective LLM** for complex analysis.

| Architecture | Cost (100 endpoints) | Savings |
|--------------|---------------------|---------|
| 100% LLM (old) | $6.69 | Baseline |
| Phase 1: Pattern-based | $1.00-2.00 | 70-85% |
| Phase 2: + AST analysis | $0.80-1.20 | 85% |
| **Phase 3: + Smart LLM** | **$0.65-1.00** | **87-90%** |

**How it works:**
- **Simple CRUD endpoints** → Python only (100% savings, no LLM)
- **Well-documented code** → Python extracts everything (type hints, docstrings, decorators)
- **Complex business logic** → Focused LLM prompts (50-70% smaller)
- **Security payloads** → Static OWASP templates (no LLM needed)

**Philosophy:** "Python for structure, LLM for semantics"

**Real-world savings:**
- 10,000 endpoints/month: Save $569-604/month ($6,828-7,248/year)

### Configuration Options

The hybrid architecture is **enabled by default** in the workflow. You can customize it with environment variables:

```yaml
# Hybrid Architecture - Phase 1
-e USE_DETERMINISTIC_ENRICHMENT=true      # Master switch (default: true)
-e DETERMINISTIC_PARAMETERS=true          # Extract params from routes
-e DETERMINISTIC_STATUS_CODES=true        # Standard status codes
-e DETERMINISTIC_HTTP_METHODS=true        # HTTP method rules

# Hybrid Architecture - Phase 2 (AST-based)
-e DETERMINISTIC_TYPE_HINTS=true          # Extract type hints
-e DETERMINISTIC_DECORATORS=true          # Detect auth from decorators
-e DETERMINISTIC_DOCSTRINGS=true          # Parse docstrings

# Hybrid Architecture - Phase 3 (Smart LLM)
-e ENABLE_SMART_LLM_DECISIONS=true        # Use LLM only when needed
-e SMART_LLM_CONFIDENCE_THRESHOLD=0.7     # Skip LLM if confidence >= 70%
-e ENABLE_FOCUSED_LLM_PROMPTS=true        # Minimal prompts (50-70% smaller)

# Batch Processing
-e ENABLE_BATCHING=true                   # Batch multiple endpoints per LLM call
-e OPENAPI_BATCH_SIZE=20                  # Batch size for OpenAPI enrichment
-e PAYLOAD_BATCH_SIZE=15                  # Batch size for payload generation
```

**Tuning confidence threshold:**
- `0.8` = Conservative (only skip LLM for perfect code, 70% savings)
- `0.7` = Recommended (balanced quality & cost, 85% savings)
- `0.6` = Aggressive (maximize savings, 90% reduction)

## 📈 Workflow Jobs

### 1. API Discovery Scan
- Scans codebase for API endpoints
- Generates AI-enriched OpenAPI spec
- Uploads artifacts for other jobs

### 2. API Change Detection
- Compares current vs. previous OpenAPI spec
- Detects added/removed endpoints
- Comments on pull requests with diff

### 3. Invicti DAST Upload
- Uploads enriched spec to Invicti
- Triggers security scanning
- Only runs on main/master branch or manual trigger

### 4. Security Gate
- Checks for critical/high risk endpoints
- Can block PRs with security issues (currently warning only)

## 🔍 Example Output

### Pull Request Comment
```
## 🔍 API Security Scan Results

| Metric | Value |
|--------|-------|
| Total Endpoints | 15 |
| Critical/High Risk | 2 |
| Scan Mode | 🤖 AI-Enriched |

<details>
<summary>📊 API Diff Details</summary>

Added Endpoints (2):
  + /api/users [POST]
  + /api/users/{id} [GET, PUT, DELETE]

</details>

✨ **AI Enrichment Enabled**: Complete schemas, auth configs, and security test payloads included

---
*Generated by Universal Polyglot API Scanner v5.0*
```

## 🛠️ Configuration

### Enable/Disable AI Enrichment

Edit `.github/workflows/security.yml`:

```yaml
env:
  SCANNER_IMAGE: bolatahmett/api-scanner:latest
  # Set to 'true' to enable AI enrichment
  AI_ENRICHMENT_ENABLED: true  # Change to false to disable
  # Default AI provider (anthropic, openai, gemini, bedrock)
  DEFAULT_LLM_PROVIDER: anthropic
```

### Change Default AI Provider

To use a different AI provider by default, update the workflow:

```yaml
env:
  DEFAULT_LLM_PROVIDER: openai  # or gemini, bedrock
```

And ensure the corresponding secret is configured (e.g., `OPENAI_API_KEY`).

### Adjust Scanner Settings

Add environment variables to the Docker run command:

```yaml
- name: Run API Scanner
  run: |
    docker run --rm \
      -v ${{ github.workspace }}:/code:ro \
      -v ${{ github.workspace }}/output:/output \
      -e SCANNER_AI_ENRICH=true \
      -e LLM_PROVIDER=anthropic \
      -e ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }} \
      -e LLM_MODEL=claude-sonnet-4-5-20250929 \
      -e LLM_MAX_TOKENS=4096 \
      -e ENRICHMENT_MAX_WORKERS=3 \
      -e SCANNER_PARALLEL=true \
      -e SCANNER_WORKERS=8 \
      ${{ env.SCANNER_IMAGE }}
```

**Multi-Provider Examples:**

```yaml
# Using OpenAI GPT-4
-e LLM_PROVIDER=openai \
-e OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }} \
-e LLM_MODEL=gpt-4-turbo

# Using Google Gemini
-e LLM_PROVIDER=gemini \
-e GOOGLE_API_KEY=${{ secrets.GOOGLE_API_KEY }} \
-e LLM_MODEL=gemini-1.5-pro

# Using AWS Bedrock
-e LLM_PROVIDER=bedrock \
-e AWS_ACCESS_KEY_ID=${{ secrets.AWS_ACCESS_KEY_ID }} \
-e AWS_SECRET_ACCESS_KEY=${{ secrets.AWS_SECRET_ACCESS_KEY }} \
-e AWS_REGION=us-east-1 \
-e LLM_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
```

## 🔒 Security Features

### Path Validation & Scan Directory Restrictions

The scanner includes comprehensive security validation to prevent unauthorized directory access.

#### Automatic Protection

The scanner automatically prevents scanning of:
- **System directories**: `/etc`, `/boot`, `/root`, `/sys` (Linux/macOS) or `C:\Windows` (Windows)
- **Path traversal attempts**: `../` sequences are detected and logged
- **Symbolic links**: Disabled by default to prevent directory escaping

#### Restrict Scan Directories (Production Recommended)

Limit scanning to specific base directories using `ALLOWED_SCAN_DIRS`:

```bash
# Docker example - restrict to /code only
docker run --rm \
  -v $(pwd):/code \
  -e ALLOWED_SCAN_DIRS=/code \
  -e ANTHROPIC_API_KEY=sk-ant-your-key \
  bolatahmett/api-scanner:latest

# Multi-tenant example - separate directories per tenant
docker run --rm \
  -v $(pwd)/tenant1:/workspace/tenant1 \
  -v $(pwd)/tenant2:/workspace/tenant2 \
  -e ALLOWED_SCAN_DIRS=/workspace/tenant1 \
  bolatahmett/api-scanner:latest
```

#### Security Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_SCAN_DIRS` | (none) | Comma-separated list of allowed base directories. If set, scanner will only scan paths under these directories. |
| `ENABLE_SYMLINK_SCAN` | `false` | Enable scanning of symbolic links. Set to `true` only if you trust all symlinks. |

#### GitHub Actions Security

The workflow automatically restricts scanning to the repository directory:

```yaml
env:
  ALLOWED_SCAN_DIRS: ${{ github.workspace }}
  ENABLE_SYMLINK_SCAN: false
```

#### Security Examples

**Secure Production Deployment:**
```bash
docker run --rm \
  -v /app/code:/workspace:ro \
  -e ALLOWED_SCAN_DIRS=/workspace \
  -e ENABLE_SYMLINK_SCAN=false \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  bolatahmett/api-scanner:latest
```

**Multi-Directory with Restrictions:**
```bash
# Allow scanning only /app and /workspace
docker run --rm \
  -v /app/project1:/app \
  -v /workspace/project2:/workspace \
  -e ALLOWED_SCAN_DIRS="/app,/workspace" \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  bolatahmett/api-scanner:latest
```

**Development (Less Restricted):**
```bash
# Allow symlinks for local development (use with caution)
docker run --rm \
  -v $(pwd):/code \
  -e ALLOWED_SCAN_DIRS=/code \
  -e ENABLE_SYMLINK_SCAN=true \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  bolatahmett/api-scanner:latest
```

#### Security Violations

The scanner will exit with error if:
- Attempting to scan system directories (e.g., `/etc`, `C:\Windows`)
- Path is outside `ALLOWED_SCAN_DIRS` (if configured)
- Symbolic links detected and `ENABLE_SYMLINK_SCAN=false`

All violations are logged to the audit log for security monitoring.

#### Best Practices

1. **Always set `ALLOWED_SCAN_DIRS` in production**
   ```bash
   ALLOWED_SCAN_DIRS=/workspace,/app
   ```

2. **Keep `ENABLE_SYMLINK_SCAN=false` unless necessary**
   - Only enable if you trust all symlinks
   - Useful for node_modules/, vendor/ directories

3. **Use read-only volume mounts**
   ```bash
   -v $(pwd):/code:ro  # Read-only mount
   ```

4. **Enable audit logging**
   ```bash
   -e SCANNER_AUDIT_LOG=/output/audit.log
   ```

5. **Review security logs regularly**
   ```bash
   docker run --rm -v $(pwd)/logs:/output \
     -e SCANNER_AUDIT_LOG=/output/security.log \
     ...
   ```

For detailed security documentation, see [SECURITY.md](https://github.com/yourorg/api-scanner/blob/main/docs/SECURITY.md).

---

## 📚 Documentation

- [Security Features](https://github.com/yourorg/api-scanner/blob/main/docs/SECURITY.md)
- [AI Enrichment Guide](https://github.com/yourorg/api-scanner/blob/main/docs/AI_ENRICHMENT.md)
- [Technical Architecture](https://github.com/yourorg/api-scanner/blob/main/docs/ARCHITECTURE.md)
- [Scanner Main Repo](https://github.com/yourorg/api-scanner)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Push and create a pull request
5. The workflow will automatically scan your changes

## 📝 License

This test application is for demonstration purposes.

## 🆘 Support

For issues or questions:
- **GitHub Issues**: [Create an issue](https://github.com/yourorg/api-scanner/issues)
- **Documentation**: See docs/ folder
- **Email**: security-team@yourorg.com

---

**Universal Polyglot API Scanner v5.0**
*AI-Powered API Discovery & Enrichment for DAST Tools*
