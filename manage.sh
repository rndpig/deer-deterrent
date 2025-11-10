#!/bin/bash
# =============================================================================
# Deer Deterrent Management Script - Dell Deployment
# Quick commands for managing the Docker-based deer deterrent system
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.dell.yml"
ENV_FILE=".env.dell"
PROJECT_DIR="$HOME/deer-deterrent"

# Helper functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Change to project directory
cd "$PROJECT_DIR" || {
    print_error "Project directory not found: $PROJECT_DIR"
    exit 1
}

# Commands
cmd_start() {
    print_header "Starting Deer Deterrent System"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    print_success "All services started"
    echo ""
    cmd_status
}

cmd_stop() {
    print_header "Stopping Deer Deterrent System"
    docker compose -f "$COMPOSE_FILE" stop
    print_success "All services stopped"
}

cmd_restart() {
    print_header "Restarting Deer Deterrent System"
    docker compose -f "$COMPOSE_FILE" restart
    print_success "All services restarted"
}

cmd_down() {
    print_header "Shutting Down Deer Deterrent System"
    print_warning "This will stop and remove all containers"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose -f "$COMPOSE_FILE" down
        print_success "All services shut down"
    else
        print_info "Cancelled"
    fi
}

cmd_status() {
    print_header "Service Status"
    docker compose -f "$COMPOSE_FILE" ps
}

cmd_logs() {
    SERVICE=${1:-}
    if [ -z "$SERVICE" ]; then
        print_header "Logs - All Services (Ctrl+C to exit)"
        docker compose -f "$COMPOSE_FILE" logs -f --tail=100
    else
        print_header "Logs - $SERVICE (Ctrl+C to exit)"
        docker compose -f "$COMPOSE_FILE" logs -f --tail=100 "$SERVICE"
    fi
}

cmd_health() {
    print_header "Health Check - All Services"
    
    echo -e "\n${BLUE}Frontend:${NC}"
    curl -s http://localhost:3000 > /dev/null && print_success "Running" || print_error "Not responding"
    
    echo -e "\n${BLUE}Backend:${NC}"
    curl -s http://localhost:8000/health | jq . || print_error "Not responding"
    
    echo -e "\n${BLUE}ML Detector:${NC}"
    curl -s http://localhost:8001/health | jq . || print_error "Not responding"
    
    echo -e "\n${BLUE}Coordinator:${NC}"
    curl -s http://localhost:5000/health | jq . || print_error "Not responding"
    
    echo -e "\n${BLUE}Database:${NC}"
    docker compose -f "$COMPOSE_FILE" exec -T database pg_isready -U deeruser && print_success "Running" || print_error "Not responding"
    
    echo -e "\n${BLUE}MQTT Broker:${NC}"
    docker compose -f "$COMPOSE_FILE" exec -T mosquitto mosquitto_sub -t test -C 1 -W 1 > /dev/null 2>&1 && print_success "Running" || print_error "Not responding"
}

cmd_stats() {
    print_header "Resource Usage"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
}

cmd_update() {
    print_header "Updating Deer Deterrent System"
    
    print_info "Pulling latest code from GitHub..."
    git pull origin main
    
    print_info "Rebuilding containers..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    
    print_success "Update complete"
    cmd_status
}

cmd_backup() {
    print_header "Backing Up Deer Deterrent Data"
    
    BACKUP_DIR="$HOME/backups"
    DATE=$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_DIR"
    
    print_info "Backing up database..."
    docker compose -f "$COMPOSE_FILE" exec -T database pg_dump -U deeruser deer_deterrent > "$BACKUP_DIR/db_$DATE.sql"
    print_success "Database backed up: $BACKUP_DIR/db_$DATE.sql"
    
    print_info "Backing up configuration..."
    cp "$ENV_FILE" "$BACKUP_DIR/env_$DATE.backup"
    print_success "Config backed up: $BACKUP_DIR/env_$DATE.backup"
    
    print_info "Backing up snapshots and logs..."
    tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" dell-deployment/data dell-deployment/logs 2>/dev/null || true
    print_success "Data backed up: $BACKUP_DIR/data_$DATE.tar.gz"
    
    print_info "Cleaning old backups (keeping last 7 days)..."
    find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
    find "$BACKUP_DIR" -name "*.backup" -mtime +7 -delete
    
    print_success "Backup complete!"
}

cmd_clean() {
    print_header "Cleaning Up Docker Resources"
    
    print_warning "This will remove:"
    echo "  - Stopped containers"
    echo "  - Unused networks"
    echo "  - Dangling images"
    echo "  - Build cache"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker system prune -f
        print_success "Cleanup complete"
        
        echo ""
        print_info "Disk usage after cleanup:"
        df -h /
    else
        print_info "Cancelled"
    fi
}

cmd_shell() {
    SERVICE=${1:-backend}
    print_header "Opening Shell in $SERVICE Container"
    docker compose -f "$COMPOSE_FILE" exec "$SERVICE" bash || \
    docker compose -f "$COMPOSE_FILE" exec "$SERVICE" sh
}

cmd_test() {
    print_header "Testing System Components"
    
    echo -e "\n${BLUE}Testing ML Detector with sample image...${NC}"
    
    # Create a test image URL (Wikipedia deer image)
    TEST_URL="https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/White-tailed_deer.jpg/640px-White-tailed_deer.jpg"
    
    # Download test image
    curl -s "$TEST_URL" -o /tmp/test_deer.jpg
    
    # Test detection
    curl -s -X POST http://localhost:8001/detect \
        -F "file=@/tmp/test_deer.jpg" | jq .
    
    rm -f /tmp/test_deer.jpg
    
    echo -e "\n${BLUE}Testing coordinator webhook...${NC}"
    curl -s -X POST http://localhost:5000/webhook/test \
        -H "Content-Type: application/json" \
        -d "{
            \"camera_id\": \"test-camera\",
            \"snapshot_url\": \"$TEST_URL\",
            \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
        }" | jq .
    
    print_success "Test complete - check coordinator logs for results"
}

cmd_monitor() {
    print_header "System Monitoring (Ctrl+C to exit)"
    
    while true; do
        clear
        echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║       Deer Deterrent System - Live Monitor                ║${NC}"
        echo -e "${BLUE}║       $(date +'%Y-%m-%d %H:%M:%S')                                      ║${NC}"
        echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
        
        echo -e "\n${YELLOW}Container Status:${NC}"
        docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
        
        echo -e "\n${YELLOW}Resource Usage:${NC}"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
        
        echo -e "\n${YELLOW}Recent Coordinator Activity:${NC}"
        docker compose -f "$COMPOSE_FILE" logs --tail=5 coordinator | tail -5
        
        echo -e "\n${YELLOW}Disk Usage:${NC}"
        df -h / | grep -E '(Filesystem|/$)'
        
        echo -e "\n${BLUE}Refreshing in 5 seconds... (Ctrl+C to exit)${NC}"
        sleep 5
    done
}

cmd_help() {
    cat << EOF
${BLUE}╔════════════════════════════════════════════════════════════╗${NC}
${BLUE}║     Deer Deterrent Management Script - Dell Deployment     ║${NC}
${BLUE}╚════════════════════════════════════════════════════════════╝${NC}

${YELLOW}Usage:${NC}
  ./manage.sh [command] [options]

${YELLOW}Service Management:${NC}
  start            Start all services
  stop             Stop all services (keep containers)
  restart          Restart all services
  down             Stop and remove all containers
  status           Show service status

${YELLOW}Monitoring:${NC}
  logs [service]   Show logs (all services or specific one)
  health           Check health of all services
  stats            Show resource usage statistics
  monitor          Live monitoring dashboard (refreshes every 5s)

${YELLOW}Maintenance:${NC}
  update           Pull latest code and rebuild
  backup           Backup database, config, and data
  clean            Clean up Docker resources
  test             Run system tests

${YELLOW}Debugging:${NC}
  shell [service]  Open shell in container (default: backend)

${YELLOW}Service Names:${NC}
  - frontend       React dashboard
  - backend        FastAPI server
  - ml-detector    YOLOv8 inference service
  - coordinator    Ring webhook handler
  - database       PostgreSQL
  - mosquitto      MQTT broker
  - ring-mqtt      Ring camera integration

${YELLOW}Examples:${NC}
  ./manage.sh start              # Start all services
  ./manage.sh logs coordinator   # View coordinator logs
  ./manage.sh health             # Check all services
  ./manage.sh backup             # Create backup
  ./manage.sh shell ml-detector  # Debug ML detector

${YELLOW}Quick Links:${NC}
  Dashboard:  http://localhost:3000
  API Docs:   http://localhost:8000/docs
  ML Docs:    http://localhost:8001/docs
  Ring UI:    http://localhost:55123

${BLUE}For more help, see: DELL_DEPLOYMENT.md${NC}
EOF
}

# Main command dispatcher
COMMAND=${1:-help}
shift || true

case "$COMMAND" in
    start)      cmd_start ;;
    stop)       cmd_stop ;;
    restart)    cmd_restart ;;
    down)       cmd_down ;;
    status)     cmd_status ;;
    logs)       cmd_logs "$@" ;;
    health)     cmd_health ;;
    stats)      cmd_stats ;;
    update)     cmd_update ;;
    backup)     cmd_backup ;;
    clean)      cmd_clean ;;
    shell)      cmd_shell "$@" ;;
    test)       cmd_test ;;
    monitor)    cmd_monitor ;;
    help|--help|-h) cmd_help ;;
    *)
        print_error "Unknown command: $COMMAND"
        echo ""
        cmd_help
        exit 1
        ;;
esac
