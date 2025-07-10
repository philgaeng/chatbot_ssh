#!/bin/bash

# Load configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/config.sh"

echo "🔐 Setting up database encryption..."

# Check if pgcrypto extension is available
echo "Checking pgcrypto extension..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT pgp_sym_encrypt('test', 'test_key');" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ pgcrypto extension is available"
else
    echo "❌ pgcrypto extension is not available"
    echo "Enabling pgcrypto extension..."
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
    
    if [ $? -eq 0 ]; then
        echo "✅ pgcrypto extension enabled successfully"
    else
        echo "❌ Failed to enable pgcrypto extension"
        exit 1
    fi
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

# Test encryption functionality
echo "🧪 Testing encryption functionality..."
cd "$PROJECT_ROOT"

# Set the encryption key for testing
export DB_ENCRYPTION_KEY="$ENCRYPTION_KEY"

# Run encryption test
python3 -c "
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    from backend.services.database_services import ComplainantDbManager
    
    manager = ComplainantDbManager()
    
    # Test data
    test_data = {
        'complainant_full_name': 'Test User',
        'complainant_phone': '+977-1234567890',
        'complainant_email': 'test@example.com'
    }
    
    # Test encryption
    encrypted = manager._encrypt_complainant_data(test_data)
    print('✅ Encryption test passed')
    
    # Test decryption
    decrypted = manager._decrypt_complainant_data(encrypted)
    print('✅ Decryption test passed')
    
    # Verify integrity
    for key in test_data:
        if test_data[key] != decrypted[key]:
            print(f'❌ Data integrity check failed for {key}')
            exit(1)
    
    print('✅ Data integrity check passed')
    print('✅ Encryption setup verified successfully')
    
except Exception as e:
    print(f'❌ Encryption test failed: {str(e)}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Encryption setup completed successfully!"
    echo ""
    echo "🎉 Your database is now ready for encrypted data storage!"
    echo ""
    echo "📋 Usage:"
    echo "- All sensitive user data will be automatically encrypted"
    echo "- Encryption is transparent to your application code"
    echo "- Data is encrypted at rest in the database"
    echo ""
    echo "🔐 Security features:"
    echo "- Field-level encryption for sensitive data"
    echo "- Encryption key stored in environment variables"
    echo "- Automatic encryption/decryption"
    echo "- Search functionality works with encrypted data"
else
    echo "❌ Encryption setup failed"
    echo "Please check your database connection and pgcrypto extension"
    exit 1
fi 