FROM opensearchproject/opensearch:2.11.1

# Set default environment variables
ENV OPENSEARCH_JAVA_OPTS="-Xms512m -Xmx512m"
ENV discovery.type=single-node
ENV DISABLE_SECURITY_PLUGIN=false
ENV DISABLE_INSTALL_DEMO_CONFIG=false

# Configure cluster name
ENV cluster.name=opensearch-cluster

# Disable performance analyzer if not needed
ENV DISABLE_PERFORMANCE_ANALYZER_AGENT_CLI=true

# Configure memory settings
ENV bootstrap.memory_lock=true

# Expose ports
# 9200: REST API
# 9600: Performance Analyzer
EXPOSE 9200 9600

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD curl -f -k -u admin:admin https://localhost:9200/_cluster/health || exit 1
