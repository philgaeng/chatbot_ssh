#!/bin/bash

# Load configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/config.sh"

echo "🔐 Setting up database encryption key..."

# Generate encryption key
echo "Generating encryption key..."
ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

echo "Generated encryption key: $ENCRYPTION_KEY"
echo ""

# Check if .env file exists
ENV_FILE="$PROJECT_ROOT/.env"
ENV_LOCAL="$PROJECT_ROOT/env.local"

if [ -f "$ENV_LOCAL" ]; then
    ENV_FILE="$ENV_LOCAL"
    echo "Found environment file: $ENV_FILE"
elif [ -f "$ENV_FILE" ]; then
    echo "Found environment file: $ENV_FILE"
else
    echo "No environment file found. Creating .env file..."
    ENV_FILE="$PROJECT_ROOT/.env"
fi

# Add encryption key to environment file
if [ -f "$ENV_FILE" ]; then
    # Check if DB_ENCRYPTION_KEY already exists
    if grep -q "DB_ENCRYPTION_KEY" "$ENV_FILE"; then
        echo "Updating existing DB_ENCRYPTION_KEY in $ENV_FILE"
        # Update existing key
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/DB_ENCRYPTION_KEY=.*/DB_ENCRYPTION_KEY=$ENCRYPTION_KEY/" "$ENV_FILE"
        else
            # Linux
            sed -i "s/DB_ENCRYPTION_KEY=.*/DB_ENCRYPTION_KEY=$ENCRYPTION_KEY/" "$ENV_FILE"
        fi
    else
        echo "Adding DB_ENCRYPTION_KEY to $ENV_FILE"
        echo "" >> "$ENV_FILE"
        echo "# Database Encryption" >> "$ENV_FILE"
        echo "DB_ENCRYPTION_KEY=$ENCRYPTION_KEY" >> "$ENV_FILE"
    fi
else
    echo "Creating new environment file: $ENV_FILE"
    cat > "$ENV_FILE" << EOF
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=grievance_db
POSTGRES_USER=nepal_grievance_admin
POSTGRES_PASSWORD=K9!mP2\$vL5nX8&qR4jW7

# Database Encryption
DB_ENCRYPTION_KEY=$ENCRYPTION_KEY
EOF
fi

# Set environment variable for current session
export DB_ENCRYPTION_KEY="$ENCRYPTION_KEY"

echo ""
echo "✅ Encryption key setup completed!"
echo ""
echo "📋 Summary:"
echo "- Encryption key generated and saved to $ENV_FILE"
echo "- Environment variable set for current session"
echo ""
echo "🔐 Next steps:"
echo "1. Restart your application to load the new environment variable"
echo "2. Test encryption: python scripts/database/init.py --test-encryption"
echo "3. All new sensitive data will be automatically encrypted"
echo ""
echo "⚠️  Important: Keep your encryption key secure!"
echo "- The key is stored in $ENV_FILE"
echo "- Without this key, encrypted data cannot be decrypted"
echo "- Consider backing up the key securely" 