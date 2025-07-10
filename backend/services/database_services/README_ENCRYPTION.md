# Database Encryption Setup

This document explains how to set up and use field-level encryption for sensitive personal data in the Nepal Chatbot database.

## 🔐 Overview

The `ComplainantDbManager` now supports field-level encryption using PostgreSQL's `pgcrypto` extension. Sensitive fields are automatically encrypted before storage and decrypted when retrieved.

## 📋 Encrypted Fields

The following fields are automatically encrypted:

- `complainant_full_name`
- `complainant_phone`
- `complainant_email`
- `complainant_address`

## 🚀 Setup Instructions

### 1. Enable pgcrypto Extension

Run this SQL command in your PostgreSQL database:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

### 2. Generate Encryption Key

Generate a secure encryption key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Set Environment Variable

Add the encryption key to your environment variables:

```bash
export DB_ENCRYPTION_KEY='your_generated_key_here'
```

Or add to your `.env` file:

```
DB_ENCRYPTION_KEY=your_generated_key_here
```

### 4. Run Setup Script (Optional)

You can also use the provided setup script:

```bash
python -m backend.services.database_services.setup_encryption
```

## 🔧 Usage

### Creating Users with Encryption

```python
from backend.services.database_services import db_manager

# Create a new user - sensitive fields will be automatically encrypted
user_data = {
    'complainant_full_name': 'John Doe',
    'complainant_phone': '+977-1234567890',
    'complainant_email': 'john.doe@example.com',
    'complainant_address': '123 Main Street, Kathmandu'
}

user_id = db_manager.create_complainant(user_data)
```

### Retrieving Users with Decryption

```python
# Retrieve user - sensitive fields will be automatically decrypted
user = db_manager.get_complainant_by_id(user_id)
print(user['complainant_phone'])  # Shows decrypted phone number
```

### Updating Users with Encryption

```python
# Update user - sensitive fields will be automatically encrypted
update_data = {
    'complainant_phone': '+977-9876543210',
    'complainant_email': 'john.updated@example.com'
}

success = db_manager.update_complainant(user_id, update_data)
```

## 🔍 How It Works

### Encryption Process

1. When creating/updating users, sensitive fields are encrypted using `pgp_sym_encrypt()`
2. Encrypted data is stored as binary data in the database
3. Non-sensitive fields remain unencrypted for querying

### Decryption Process

1. When retrieving users, encrypted fields are decrypted using `pgp_sym_decrypt()`
2. Decrypted data is returned to the application
3. The encryption/decryption is transparent to the application code

### Search Functionality

- Phone number searches work by encrypting the search term and comparing with encrypted stored values
- Other queries work normally on non-encrypted fields

## 🛡️ Security Features

### Key Management

- Encryption key is stored in environment variables (not in code)
- Key is never logged or stored in the database
- Different keys can be used for different environments

### Data Protection

- Sensitive data is encrypted at rest in the database
- Database administrators cannot read encrypted data without the key
- Encryption is transparent to application code

### Fallback Behavior

- If no encryption key is set, data is stored unencrypted (with warning)
- If encryption fails, data is stored unencrypted (with error logging)
- Application continues to work even if encryption is disabled

## 🔧 Configuration

### Environment Variables

| Variable            | Description                       | Required             |
| ------------------- | --------------------------------- | -------------------- |
| `DB_ENCRYPTION_KEY` | Encryption key for sensitive data | Yes (for encryption) |

### Customization

You can modify the encrypted fields by updating the `ENCRYPTED_FIELDS` set in `ComplainantDbManager`:

```python
ENCRYPTED_FIELDS = {
    'complainant_phone',
    'complainant_email',
    'complainant_address',
    'complainant_full_name',
    'complainant_province',  # Add more fields as needed
    'complainant_district'
}
```

## 🚨 Important Notes

### Migration from Unencrypted Data

- Existing unencrypted data will remain unencrypted
- New data will be encrypted automatically
- Consider migrating existing data if needed

### Backup and Recovery

- Ensure encryption key is backed up securely
- Without the key, encrypted data cannot be recovered
- Test backup and recovery procedures

### Performance

- Encryption/decryption adds minimal overhead
- Search operations on encrypted fields may be slower
- Consider indexing strategies for performance

## 🧪 Testing

Test encryption functionality:

```python
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
print("Encrypted:", encrypted)

# Test decryption
decrypted = manager._decrypt_complainant_data(encrypted)
print("Decrypted:", decrypted)

# Verify integrity
assert test_data == decrypted
print("✅ Encryption test passed!")
```

## 🔗 Related Files

- `complainant_manager.py` - Main encryption implementation
- `setup_encryption.py` - Setup and testing utilities
- `base_manager.py` - Base database functionality
- `__init__.py` - Manager imports and instances

## 📞 Support

For issues with encryption setup or usage, check:

1. PostgreSQL logs for pgcrypto errors
2. Application logs for encryption warnings/errors
3. Environment variable configuration
4. Database connection and permissions
