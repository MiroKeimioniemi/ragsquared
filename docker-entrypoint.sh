#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting AI Auditing System...${NC}"

# Ensure data directories exist
mkdir -p /app/data/{uploads,processed,logs,chroma,cache/embeddings,reports}
chmod -R 755 /app/data

# Function to run database migrations
run_migrations() {
    echo -e "${YELLOW}Running database migrations...${NC}"
    cd /app
    
    # Check if database file exists and has tables but no alembic version
    if [ -f "/app/data/app.db" ]; then
        # Check if alembic_version table exists and if documents table exists
        DB_STATE=$(python -c "
import sqlite3
try:
    conn = sqlite3.connect('/app/data/app.db')
    cursor = conn.cursor()
    # Check for alembic_version
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'\")
    alembic_exists = cursor.fetchone() is not None
    # Check for documents table (first migration creates this)
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='documents'\")
    documents_exists = cursor.fetchone() is not None
    conn.close()
    print('stamped' if alembic_exists else ('has_tables' if documents_exists else 'empty'))
except Exception as e:
    print('error')
" 2>/dev/null || echo "error")
        
        if [ "$DB_STATE" = "has_tables" ]; then
            # Database has tables but no alembic tracking - stamp it with head
            echo -e "${YELLOW}Database has tables but no migration tracking. Stamping database to head...${NC}"
            set +e
            python -m alembic -c alembic.ini stamp head 2>&1 | grep -v "INFO\|WARN" || true
            STAMP_STATUS=$?
            set -e
            if [ $STAMP_STATUS -eq 0 ]; then
                echo -e "${GREEN}Database stamped successfully${NC}"
            else
                echo -e "${YELLOW}Stamping had issues, but continuing with migration attempt...${NC}"
            fi
        fi
    fi
    
    set +e  # Temporarily disable exit on error
    MIGRATION_OUTPUT=$(python -m alembic -c alembic.ini upgrade head 2>&1)
    MIGRATION_STATUS=$?
    set -e  # Re-enable exit on error
    
    if [ $MIGRATION_STATUS -eq 0 ]; then
        echo -e "${GREEN}Migrations complete${NC}"
    else
        # Check if error is just "table already exists" - this is OK
        if echo "$MIGRATION_OUTPUT" | grep -qi "already exists"; then
            echo -e "${GREEN}Migrations complete (tables already exist, database is up to date)${NC}"
        else
            echo -e "${YELLOW}Migration had issues, but continuing...${NC}"
            echo "$MIGRATION_OUTPUT" | tail -5
        fi
    fi
}

# Function to start Flask backend
start_backend() {
    echo -e "${GREEN}Starting Flask backend on port 5000...${NC}"
    cd /app
    gunicorn \
        --bind 0.0.0.0:5000 \
        --workers 2 \
        --threads 2 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile - \
        --log-level info \
        "backend.app:app" &
    BACKEND_PID=$!
    echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"
}

# Function to start Next.js frontend
start_frontend() {
    echo -e "${GREEN}Starting Next.js frontend on port 3000...${NC}"
    cd /app/frontend
    # Use npm start which runs next start
    npm start &
    FRONTEND_PID=$!
    echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"
}

# Function to wait for services
wait_for_services() {
    echo -e "${YELLOW}Waiting for services to be ready...${NC}"
    
    # Wait for backend
    for i in {1..30}; do
        if curl -f http://localhost:5000/healthz > /dev/null 2>&1; then
            echo -e "${GREEN}Backend is ready!${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}Backend failed to start${NC}"
            exit 1
        fi
        sleep 1
    done
    
    # Wait for frontend
    for i in {1..30}; do
        if curl -f http://localhost:3000 > /dev/null 2>&1; then
            echo -e "${GREEN}Frontend is ready!${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${YELLOW}Frontend may still be starting...${NC}"
        fi
        sleep 1
    done
}

# Function to handle shutdown
cleanup() {
    echo -e "${YELLOW}Shutting down services...${NC}"
    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait
    exit 0
}

trap cleanup SIGTERM SIGINT

# Main execution
case "${1:-start}" in
    start)
        run_migrations
        start_backend
        sleep 2
        start_frontend
        wait_for_services
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}AI Auditing System is running!${NC}"
        echo -e "${GREEN}Backend:  http://localhost:5000${NC}"
        echo -e "${GREEN}Frontend: http://localhost:3000${NC}"
        echo -e "${GREEN}========================================${NC}"
        # Keep container running
        wait
        ;;
    migrate)
        run_migrations
        ;;
    backend)
        start_backend
        wait
        ;;
    frontend)
        start_frontend
        wait
        ;;
    *)
        exec "$@"
        ;;
esac

