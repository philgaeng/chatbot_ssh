#!/bin/bash

# Load configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/config.sh"

echo "Setting up local PostgreSQL database with encryption support..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed. Installing..."
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
fi

# Start PostgreSQL if not running
if ! sudo systemctl is-active --quiet postgresql; then
    echo "Starting PostgreSQL..."
    sudo systemctl start postgresql
fi

# Create user and database
echo "Creating database user and database..."

# Connect as postgres user to create the new user and database
sudo -u postgres psql << EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
GRANT CREATE ON DATABASE $DB_NAME TO $DB_USER;

-- Connect to the database and grant schema privileges
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT CREATE ON SCHEMA public TO $DB_USER;
GRANT USAGE ON SCHEMA public TO $DB_USER;

-- Grant sequence privileges
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO $DB_USER;

-- Grant table privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;

-- Enable pgcrypto extension for encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;
EOF

if [ $? -eq 0 ]; then
    echo "✅ Database setup completed successfully"
    echo "Database: $DB_NAME"
    echo "User: $DB_USER"
    echo "Host: $DB_HOST:$DB_PORT"
    echo "✅ pgcrypto extension enabled for encryption"
else
    echo "❌ Database setup failed"
    exit 1
fi

# Test connection
echo "Testing database connection..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Database connection test successful"
else
    echo "❌ Database connection test failed"
    exit 1
fi

# Test pgcrypto extension
echo "Testing pgcrypto extension..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT pgp_sym_encrypt('test', 'test_key');" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ pgcrypto extension test successful"
else
    echo "❌ pgcrypto extension test failed"
    exit 1
fi

# Generate encryption key if not set
if [ -z "$ENCRYPTION_KEY" ]; then
    echo "🔑 Generating encryption key..."
    ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "Generated encryption key: $ENCRYPTION_KEY"
    echo ""
    echo "📝 Add this to your environment variables:"
    echo "export DB_ENCRYPTION_KEY='$ENCRYPTION_KEY'"
    echo ""
    echo "Or add to your .env file:"
    echo "DB_ENCRYPTION_KEY=$ENCRYPTION_KEY"
    echo ""
else
    echo "✅ Encryption key already set"
fi

echo ""
echo "🎉 Local database setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Add the encryption key to your environment variables"
echo "2. Run database initialization: python scripts/database/init.py --enable-encryption"
echo "3. Test encryption: python scripts/database/init.py --test-encryption"
echo ""
echo "🔐 Encryption is now ready to use!" 