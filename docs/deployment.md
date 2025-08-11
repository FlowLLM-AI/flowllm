# Deployment Guide

This guide covers how to deploy flowllm applications in various environments, from development to production, including containerization, scaling, and monitoring.

## Table of Contents

- [Deployment Overview](#deployment-overview)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Containerization](#containerization)
- [Cloud Deployment](#cloud-deployment)
- [Scaling and Load Balancing](#scaling-and-load-balancing)
- [Monitoring and Logging](#monitoring-and-logging)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Deployment Overview

flowllm supports multiple deployment scenarios:

- **Local Development**: Quick setup for development and testing
- **Single Server**: Simple production deployment on a single machine
- **Containerized**: Docker-based deployment for consistency
- **Cloud Native**: Kubernetes deployment for scalability
- **Serverless**: Function-based deployment for event-driven workloads

### Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer                            │
└─────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│   flowllm Instance  │ │   flowllm Instance  │ │   flowllm Instance  │
│   (HTTP + MCP)      │ │   (HTTP + MCP)      │ │   (HTTP + MCP)      │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
                │               │               │
                └───────────────┼───────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                  Shared Services                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │Vector Store │ │    LLM      │ │   Metrics   │           │
│  │(ES/Chroma)  │ │  Provider   │ │  Storage    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## Development Deployment

### Quick Start

```bash
# Clone repository
git clone https://github.com/your-org/flowllm.git
cd flowllm

# Install dependencies
pip install -e .

# Set up environment
cp example.env .env
# Edit .env with your API keys

# Start development server
flowllm \
  http_service.port=8001 \
  llm.default.model_name=gpt-4 \
  vector_store.default.backend=local_file
```

### Development Configuration

Create `config/dev.yaml`:

```yaml
http_service:
  host: "127.0.0.1"
  port: 8001
  timeout_keep_alive: 300
  limit_concurrency: 32

thread_pool:
  max_workers: 5

llm:
  default:
    backend: openai_compatible
    model_name: "gpt-3.5-turbo"
    params:
      temperature: 0.7

vector_store:
  default:
    backend: local_file
    embedding_model: default
    params:
      store_dir: "./dev_vector_store"

# Enable debug logging
logging:
  level: DEBUG
```

### Hot Reload for Development

```bash
# Install development dependencies
pip install watchdog

# Start with auto-reload
uvicorn flowllm.app:app --reload --host 127.0.0.1 --port 8001
```

## Production Deployment

### Single Server Deployment

#### 1. System Requirements

**Minimum Requirements:**
- CPU: 4 cores
- RAM: 8GB
- Storage: 50GB SSD
- OS: Ubuntu 20.04+ / CentOS 8+ / RHEL 8+

**Recommended Requirements:**
- CPU: 8+ cores
- RAM: 16GB+
- Storage: 100GB+ SSD
- OS: Ubuntu 22.04 LTS

#### 2. System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.12+
sudo apt install python3.12 python3.12-pip python3.12-venv

# Create application user
sudo useradd -m -s /bin/bash flowllm
sudo usermod -aG sudo flowllm

# Create application directory
sudo mkdir -p /opt/flowllm
sudo chown flowllm:flowllm /opt/flowllm
```

#### 3. Application Installation

```bash
# Switch to application user
sudo -u flowllm -i

# Navigate to application directory
cd /opt/flowllm

# Clone and install application
git clone https://github.com/your-org/flowllm.git .
python3.12 -m venv venv
source venv/bin/activate
pip install -e .

# Create configuration
cp example.env .env
# Edit .env with production values
```

#### 4. Production Configuration

Create `config/prod.yaml`:

```yaml
http_service:
  host: "0.0.0.0"
  port: 8080
  timeout_keep_alive: 600
  limit_concurrency: 128

thread_pool:
  max_workers: 20

llm:
  default:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.3
      max_retries: 5

embedding_model:
  default:
    backend: openai_compatible
    model_name: "text-embedding-3-large"
    params:
      dimensions: 1536

vector_store:
  default:
    backend: elasticsearch
    embedding_model: default
    params:
      hosts: ["http://localhost:9200"]
      batch_size: 1000

# Production logging
logging:
  level: INFO
  file: "/var/log/flowllm/app.log"
```

#### 5. Process Management with systemd

Create `/etc/systemd/system/flowllm.service`:

```ini
[Unit]
Description=flowllm HTTP Service
After=network.target

[Service]
Type=simple
User=flowllm
Group=flowllm
WorkingDirectory=/opt/flowllm
Environment=PATH=/opt/flowllm/venv/bin
ExecStart=/opt/flowllm/venv/bin/flowllm --config-file=config/prod.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/flowllm /var/log/flowllm

[Install]
WantedBy=multi-user.target
```

Create MCP service `/etc/systemd/system/flowllm-mcp.service`:

```ini
[Unit]
Description=flowllm MCP Service
After=network.target

[Service]
Type=simple
User=flowllm
Group=flowllm
WorkingDirectory=/opt/flowllm
Environment=PATH=/opt/flowllm/venv/bin
ExecStart=/opt/flowllm/venv/bin/flowllm_mcp --config-file=config/prod.yaml mcp_transport=stdio
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable flowllm flowllm-mcp
sudo systemctl start flowllm flowllm-mcp
```

#### 6. Reverse Proxy with Nginx

Install and configure Nginx:

```bash
sudo apt install nginx

# Create configuration
sudo tee /etc/nginx/sites-available/flowllm << EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/flowllm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 7. SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Containerization

### Docker Setup

#### 1. Create Dockerfile

```dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 flowllm && chown -R flowllm:flowllm /app
USER flowllm

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["flowllm", "http_service.host=0.0.0.0", "http_service.port=8080"]
```

#### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  flowllm:
    build: .
    ports:
      - "8080:8080"
    environment:
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
      - EMBEDDING_BASE_URL=${EMBEDDING_BASE_URL}
      - ES_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - vector_data:/app/vector_store
    restart: unless-stopped
    networks:
      - flowllm-net

  flowllm-mcp:
    build: .
    command: ["flowllm_mcp", "mcp_transport=stdio"]
    environment:
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
      - EMBEDDING_BASE_URL=${EMBEDDING_BASE_URL}
      - ES_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    volumes:
      - ./config:/app/config
      - vector_data:/app/vector_store
    restart: unless-stopped
    networks:
      - flowllm-net

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    restart: unless-stopped
    networks:
      - flowllm-net

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - flowllm
    restart: unless-stopped
    networks:
      - flowllm-net

volumes:
  es_data:
  vector_data:

networks:
  flowllm-net:
    driver: bridge
```

#### 3. Build and Deploy

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f flowllm

# Scale services
docker-compose up -d --scale flowllm=3
```

### Multi-Stage Build for Production

```dockerfile
# Build stage
FROM python:3.12-slim as builder

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir build && python -m build

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install wheel
COPY --from=builder /app/dist/*.whl ./
RUN pip install --no-cache-dir *.whl && rm *.whl

# Create non-root user
RUN useradd -m -u 1000 flowllm
USER flowllm

# Copy configuration
COPY --chown=flowllm:flowllm config/ ./config/

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["flowllm", "--config-file=config/prod.yaml"]
```

## Cloud Deployment

### AWS Deployment

#### 1. ECS with Fargate

Create `ecs-task-definition.json`:

```json
{
  "family": "flowllm",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "flowllm",
      "image": "your-account.dkr.ecr.region.amazonaws.com/flowllm:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LLM_API_KEY",
          "value": "${LLM_API_KEY}"
        }
      ],
      "secrets": [
        {
          "name": "LLM_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:flowllm/api-keys"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/flowllm",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

Deploy with Terraform:

```hcl
resource "aws_ecs_cluster" "flowllm" {
  name = "flowllm"
}

resource "aws_ecs_service" "flowllm" {
  name            = "flowllm"
  cluster         = aws_ecs_cluster.flowllm.id
  task_definition = aws_ecs_task_definition.flowllm.arn
  desired_count   = 3
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnets
    security_groups  = [aws_security_group.flowllm.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.flowllm.arn
    container_name   = "flowllm"
    container_port   = 8080
  }
}
```

#### 2. Lambda Deployment

Create `lambda_handler.py`:

```python
import json
from mangum import Mangum
from flowllm.app import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")


def lambda_handler(event, context):
    """AWS Lambda handler"""
    return handler(event, context)
```

Create `serverless.yml`:

```yaml
service: flowllm

provider:
  name: aws
  runtime: python3.12
  region: us-west-2
  timeout: 300
  memorySize: 1024
  environment:
    LLM_API_KEY: ${ssm:/flowllm/llm-api-key}
    EMBEDDING_API_KEY: ${ssm:/flowllm/embedding-api-key}

functions:
  api:
    handler: lambda_handler.lambda_handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
      - http:
          path: /
          method: ANY

plugins:
  - serverless-python-requirements

custom:
  pythonRequirements:
    dockerizePip: true
```

### Kubernetes Deployment

#### 1. Create Kubernetes Manifests

**namespace.yaml:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: flowllm
```

**configmap.yaml:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flowllm-config
  namespace: flowllm
data:
  config.yaml: |
    http_service:
      host: "0.0.0.0"
      port: 8080
    llm:
      default:
        backend: openai_compatible
        model_name: "gpt-4"
    vector_store:
      default:
        backend: elasticsearch
        params:
          hosts: ["http://elasticsearch:9200"]
```

**secret.yaml:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: flowllm-secrets
  namespace: flowllm
type: Opaque
data:
  llm-api-key: <base64-encoded-key>
  embedding-api-key: <base64-encoded-key>
```

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flowllm
  namespace: flowllm
spec:
  replicas: 3
  selector:
    matchLabels:
      app: flowllm
  template:
    metadata:
      labels:
        app: flowllm
    spec:
      containers:
      - name: flowllm
        image: your-registry/flowllm:latest
        ports:
        - containerPort: 8080
        env:
        - name: LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: flowllm-secrets
              key: llm-api-key
        - name: EMBEDDING_API_KEY
          valueFrom:
            secretKeyRef:
              name: flowllm-secrets
              key: embedding-api-key
        volumeMounts:
        - name: config
          mountPath: /app/config
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
      volumes:
      - name: config
        configMap:
          name: flowllm-config
```

**service.yaml:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: flowllm-service
  namespace: flowllm
spec:
  selector:
    app: flowllm
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

**ingress.yaml:**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: flowllm-ingress
  namespace: flowllm
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - flowllm.yourdomain.com
    secretName: flowllm-tls
  rules:
  - host: flowllm.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: flowllm-service
            port:
              number: 80
```

#### 2. Deploy to Kubernetes

```bash
# Apply manifests
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# Check status
kubectl get pods -n flowllm
kubectl logs -f deployment/flowllm -n flowllm
```

## Scaling and Load Balancing

### Horizontal Scaling

#### Docker Compose Scaling

```bash
# Scale HTTP service
docker-compose up -d --scale flowllm=5

# Update load balancer configuration
# nginx.conf upstream block:
upstream flowllm_backend {
    server flowllm_1:8080;
    server flowllm_2:8080;
    server flowllm_3:8080;
    server flowllm_4:8080;
    server flowllm_5:8080;
}
```

#### Kubernetes Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: flowllm-hpa
  namespace: flowllm
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: flowllm
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Load Balancer Configuration

#### Nginx Load Balancing

```nginx
upstream flowllm_backend {
    least_conn;
    server 10.0.1.10:8080 weight=1 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8080 weight=1 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8080 weight=1 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name flowllm.yourdomain.com;

    location / {
        proxy_pass http://flowllm_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Health check
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /health {
        access_log off;
        proxy_pass http://flowllm_backend;
    }
}
```

#### HAProxy Configuration

```
global
    daemon
    maxconn 4096

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    option httplog

frontend flowllm_frontend
    bind *:80
    default_backend flowllm_backend

backend flowllm_backend
    balance roundrobin
    option httpchk GET /health
    server flowllm1 10.0.1.10:8080 check
    server flowllm2 10.0.1.11:8080 check
    server flowllm3 10.0.1.12:8080 check
```

## Monitoring and Logging

### Application Monitoring

#### Health Check Endpoints

Add to your application:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/ready")
def readiness_check():
    """Readiness check with dependencies"""
    try:
        # Check database connection
        # Check LLM API
        # Check vector store
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not ready", "error": str(e)}, 503

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    # Return application metrics
    pass
```

#### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'flowllm'
    static_configs:
      - targets: ['flowllm:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

#### Grafana Dashboard

Create dashboard with key metrics:
- Request rate and latency
- Error rate
- CPU and memory usage
- LLM API call metrics
- Vector store performance

### Logging Configuration

#### Structured Logging

```python
import structlog
from pythonjsonlogger import jsonlogger

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info("Request processed", 
           user_id="123", 
           request_id="req_456", 
           duration=0.25)
```

#### Log Aggregation with ELK Stack

**docker-compose.yml addition:**
```yaml
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    ports:
      - "5044:5044"
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

## Security Considerations

### API Security

#### API Key Management

```python
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != os.getenv("API_SECRET_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

@app.post("/agent")
def agent_endpoint(request: AgentRequest, api_key: str = Depends(verify_api_key)):
    # Protected endpoint
    pass
```

#### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/agent")
@limiter.limit("10/minute")
def agent_endpoint(request: Request, agent_request: AgentRequest):
    # Rate limited endpoint
    pass
```

### Infrastructure Security

#### Container Security

```dockerfile
# Use minimal base image
FROM python:3.12-alpine

# Don't run as root
RUN adduser -D -s /bin/sh flowllm
USER flowllm

# Remove unnecessary packages
RUN apk del build-dependencies

# Set security headers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
```

#### Network Security

```yaml
# docker-compose.yml with network isolation
version: '3.8'

services:
  flowllm:
    networks:
      - frontend
      - backend
    
  elasticsearch:
    networks:
      - backend

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access
```

#### Secrets Management

```yaml
# Kubernetes secrets
apiVersion: v1
kind: Secret
metadata:
  name: flowllm-secrets
type: Opaque
data:
  llm-api-key: <base64-encoded>
  database-password: <base64-encoded>

# Use external secret management
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "flowllm"
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Symptoms:** Service fails to start or crashes immediately

**Diagnosis:**
```bash
# Check service status
systemctl status flowllm

# Check logs
journalctl -u flowllm -f

# Check configuration
flowllm --validate-config
```

**Solutions:**
- Verify API keys are set correctly
- Check configuration file syntax
- Ensure all dependencies are installed
- Verify network connectivity to external services

#### 2. High Memory Usage

**Symptoms:** Service consumes excessive memory

**Diagnosis:**
```bash
# Monitor memory usage
htop
ps aux | grep flowllm

# Check for memory leaks
valgrind --tool=memcheck python -m flowllm.app
```

**Solutions:**
- Reduce thread pool size
- Enable garbage collection tuning
- Limit vector store cache size
- Monitor for memory leaks in custom operations

#### 3. Slow Response Times

**Symptoms:** API responses are slow

**Diagnosis:**
```bash
# Check response times
curl -w "@curl-format.txt" -s -o /dev/null http://localhost:8080/health

# Monitor system resources
iostat -x 1
sar -u 1
```

**Solutions:**
- Optimize LLM parameters
- Enable caching
- Scale horizontally
- Optimize vector store queries

#### 4. Connection Errors

**Symptoms:** Cannot connect to external services

**Diagnosis:**
```bash
# Test connectivity
curl -v https://api.openai.com/v1/models
telnet elasticsearch-host 9200

# Check DNS resolution
nslookup api.openai.com
```

**Solutions:**
- Verify network configuration
- Check firewall rules
- Validate API endpoints
- Update certificates

### Performance Tuning

#### Application Level

```yaml
# Optimize configuration
http_service:
  timeout_keep_alive: 300
  limit_concurrency: 64

thread_pool:
  max_workers: 20  # CPU cores * 2

llm:
  default:
    params:
      max_retries: 3
      timeout: 30

vector_store:
  default:
    params:
      batch_size: 1000
      cache_size: 10000
```

#### System Level

```bash
# Increase file descriptor limits
echo "flowllm soft nofile 65536" >> /etc/security/limits.conf
echo "flowllm hard nofile 65536" >> /etc/security/limits.conf

# Optimize TCP settings
echo 'net.core.somaxconn = 1024' >> /etc/sysctl.conf
echo 'net.core.netdev_max_backlog = 5000' >> /etc/sysctl.conf
sysctl -p
```

### Debugging Tools

#### Application Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Profile performance
import cProfile
cProfile.run('your_function()')

# Memory profiling
from memory_profiler import profile

@profile
def your_function():
    pass
```

#### Container Debugging

```bash
# Debug running container
docker exec -it flowllm_container /bin/bash

# Check container logs
docker logs -f flowllm_container

# Monitor container resources
docker stats flowllm_container
```

For more detailed troubleshooting, see the [Configuration Guide](configuration.md) and [Operations Development](operations.md) documentation.
