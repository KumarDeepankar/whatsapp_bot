# OpenSearch Docker Setup

This directory contains the Docker configuration for running OpenSearch.

## Quick Start

```bash
./run.sh
```

## What's Included

- **Dockerfile**: OpenSearch 2.11.1 with optimized settings
- **run.sh**: Build and run script

## Configuration

### Default Settings
- **Admin Credentials**: `admin:admin` (demo configuration)
- **Cluster Mode**: Single-node
- **Memory**: 512MB heap (initial and max)
- **Security**: Enabled with demo certificates

### Ports
- `9200`: REST API (HTTPS)
- `9600`: Performance Analyzer

## Access

### REST API
```bash
curl -k -u admin:admin https://localhost:9200
```

### Check Cluster Health
```bash
curl -k -u admin:admin https://localhost:9200/_cluster/health
```

## Container Management

### Start Container
```bash
./run.sh
```

### Stop Container
```bash
docker stop opensearch-instance
```

### Remove Container
```bash
docker rm opensearch-instance
```

### View Logs
```bash
docker logs opensearch-instance
```

## Notes

- Uses demo security configuration with hardcoded `admin:admin` credentials
- Self-signed demo certificates included (hence `-k` flag in curl)
- Single-node cluster for development
- For production, disable demo config and provide custom certificates/credentials
