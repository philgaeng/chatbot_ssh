# Nepal Chatbot Server Documentation

This document explains how to set up and run the Nepal Chatbot server components.

## Server Components

The Nepal Chatbot consists of several components:

1. **Rasa Action Server**: Handles actions for the Rasa chatbot
2. **File Server**: Handles file uploads and downloads
3. **Accessibility App**: Provides an accessible interface for users
4. **Database**: PostgreSQL database used by all components

## Project Structure

The code is organized into three main modules:

1. **actions/** - Contains Rasa-specific action code
2. **actions_server/** - Shared functionality used by both Rasa actions and the accessible interface
3. **accessible_server/** - Specific code for the accessible interface

## Running the Servers

### All-in-one Server Script

The easiest way to run all components is using the `run_servers.py` script:

```bash
python run_servers.py --all
```

This will:
1. Initialize the database
2. Start the file server on port 5001
3. Start the accessibility app on port 5006
4. Start the Rasa Action Server on port 5055

### Command Line Options

You can customize server behavior with these options:

```bash
# Skip database initialization
python run_servers.py --all --skip-db-init

# Run only the file server
python run_servers.py --file-server-only

# Run only the accessibility app
python run_servers.py --accessibility-only

# Run only the Rasa action server
python run_servers.py --rasa-only

# Change ports
python run_servers.py --all \
  --file-server-port 5002 \
  --accessibility-port 5007 \
  --rasa-action-port 5055
```

### Running Components Separately

You can also run each component separately:

1. **Initialize Database**:
   ```bash
   python init_database.py
   ```

2. **Run Rasa Action Server** (using Rasa's standard action server):
   ```bash
   rasa run actions
   ```

3. **Run File Server Only**:
   ```bash
   python run_servers.py --file-server-only
   ```

4. **Run Accessibility App Only**:
   ```bash
   python run_servers.py --accessibility-only
   ```

## Configuration

Make sure your `.env` file is properly set up with:

- Database connection parameters
- AWS credentials (if using AWS services)
- OpenAI API key (for voice transcription)

## Development Workflow

When developing the Nepal Chatbot:

1. **Rasa Actions**: Make changes in the `actions/` directory
2. **Shared Functionality**: Make changes in the `actions_server/` directory
3. **Accessible Interface**: Make changes in the `accessible_server/` directory

The separation ensures that the Rasa action server only loads what it needs and the Flask servers can run independently.

## Troubleshooting

If you encounter issues:

1. Check the logs for any error messages
2. Ensure the database is properly configured 
3. Make sure all dependencies are installed
4. Check that port numbers are not already in use

## Server Communication

- **Rasa Action Server**: Handles requests from the Rasa core
- **File Server**: Handles file uploads and downloads
- **Accessible App**: Serves the web interface for the accessible version of the chatbot

All servers access the shared database managed by `actions_server/db_manager.py`. 