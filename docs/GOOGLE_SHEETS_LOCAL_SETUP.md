# Google Sheets Local Development Setup

This guide will help you set up Google Sheets monitoring for your Nepal Chatbot project in your local WSL environment.

## Overview

The setup involves:

1. Configuring your local environment with the Google Sheets bearer token
2. Exposing your local Flask API via ngrok tunnel
3. Setting up a Google Sheet with a custom script to fetch data from your local API

## Prerequisites

- WSL2 with your Nepal Chatbot project running locally
- Flask backend running on port 5001
- Google account with access to Google Sheets
- ngrok account (free tier works fine)

## Step-by-Step Setup

### 1. Configure Local Environment

First, set up your bearer token in the local environment:

```bash
# Edit your env.local file
nano /home/philg/projects/nepal_chatbot/env.local
```

The `GSHEET_BEARER_TOKEN` has already been added. Replace `your_local_gsheet_token_here` with a secure token of your choice:

```
GSHEET_BEARER_TOKEN=your_secure_token_here
```

**Example:**

```
GSHEET_BEARER_TOKEN=dev_gsheet_2024_abc123xyz
```

### 2. Install and Configure ngrok

#### Install ngrok:

```bash
# Download and install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

#### Set up ngrok authentication:

1. Visit [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)
2. Copy your authtoken
3. Run: `ngrok config add-authtoken YOUR_AUTH_TOKEN`

### 3. Start Your Local Services

Make sure your local Flask server is running:

```bash
# Start all local services
./scripts/local/launch_servers.sh
```

Verify the Flask server is running on port 5001:

```bash
curl http://localhost:5001/health
# Should return: OK
```

### 4. Start ngrok Tunnel

```bash
# Make scripts executable (if not already)
chmod +x /home/philg/projects/nepal_chatbot/scripts/local/setup_ngrok.sh
chmod +x /home/philg/projects/nepal_chatbot/scripts/local/check_ngrok.sh
chmod +x /home/philg/projects/nepal_chatbot/scripts/local/stop_ngrok.sh

# Start ngrok tunnel
./scripts/local/setup_ngrok.sh
```

This will output something like:

```
🌍 Public URL: https://abc123.ngrok.io
📝 Use this URL in your Google Sheets configuration
```

**Important:** Copy this URL - you'll need it for the Google Sheets setup!

### 5. Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Name it "Nepal Chatbot - Local Monitoring"

### 6. Set Up Google Apps Script

1. In your Google Sheet, go to **Extensions** → **Apps Script**
2. Delete the default code and paste the contents of `/home/philg/projects/nepal_chatbot/scripts/local/google_sheets_local.js`
3. Save the script (Ctrl+S) and give it a name like "Nepal Chatbot Local"

### 7. Configure the Google Sheet

1. Go back to your Google Sheet
2. You should see a new menu: **Nepal Chatbot - Local Dev**
3. Click **Nepal Chatbot - Local Dev** → **Setup Configuration**
4. Enter your API token (same as `GSHEET_BEARER_TOKEN` from env.local)
5. Enter your ngrok URL (from step 4)

### 8. Test the Setup

1. Click **Nepal Chatbot - Local Dev** → **Test Connection**
2. If successful, click **Nepal Chatbot - Local Dev** → **Refresh Data**

The sheet should populate with grievance data from your local database!

## Managing the Setup

### Check ngrok Status

```bash
./scripts/local/check_ngrok.sh
```

### Stop ngrok Tunnel

```bash
./scripts/local/stop_ngrok.sh
```

### Restart ngrok Tunnel

```bash
./scripts/local/setup_ngrok.sh restart
```

## Troubleshooting

### Common Issues

#### 1. "Connection failed" in Google Sheets

- Check if your Flask server is running: `curl http://localhost:5001/health`
- Verify ngrok is running: `./scripts/local/check_ngrok.sh`
- Make sure you're using the correct ngrok URL

#### 2. "Invalid token" error

- Verify the `GSHEET_BEARER_TOKEN` in env.local matches the token in Google Sheets
- Restart your Flask server after changing env.local

#### 3. No data showing in sheet

- Check if you have grievances in your local database
- Look at the Google Apps Script logs: **View** → **Logs** in Apps Script editor
- Test the API endpoint directly: `curl -H "Authorization: Bearer YOUR_TOKEN" https://your-ngrok-url.ngrok.io/gsheet-get-grievances`

#### 4. ngrok URL keeps changing

- Free ngrok accounts get new URLs each restart
- Consider upgrading to a paid plan for static URLs
- Or update the Google Sheets configuration each time you restart ngrok

### Debugging Steps

1. **Check Flask logs:**

   ```bash
   tail -f /home/philg/projects/nepal_chatbot/logs/flask_server.log
   ```

2. **Check ngrok logs:**

   ```bash
   tail -f /tmp/ngrok.log
   ```

3. **Test API endpoint directly:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        -H "Content-Type: application/json" \
        https://your-ngrok-url.ngrok.io/gsheet-get-grievances
   ```

## Field Mapping

The Google Sheet will display these fields:

| Column | Database Field           | Description       |
| ------ | ------------------------ | ----------------- |
| A      | complainant_id           | User ID           |
| B      | grievance_id             | Grievance ID      |
| C      | complainant_full_name    | Full Name         |
| D      | complainant_phone        | Contact Phone     |
| E      | complainant_municipality | Municipality      |
| F      | complainant_village      | Village           |
| G      | complainant_address      | Address           |
| H      | grievance_description    | Grievance Details |
| I      | grievance_summary        | Summary           |
| J      | grievance_categories     | Categories        |
| K      | grievance_creation_date  | Creation Date     |
| L      | status                   | Status            |

## Security Notes

- The bearer token provides basic authentication - keep it secure
- ngrok exposes your local API to the internet - only use for development
- Consider using ngrok's authentication features for additional security
- Don't commit your actual bearer token to version control

## Next Steps

Once everything is working locally:

1. **Test data filtering:** Try adding query parameters to the API call
2. **Set up automatic refresh:** Use Google Apps Script triggers for periodic updates
3. **Customize the sheet:** Add formatting, charts, or additional functionality
4. **Prepare for production:** Set up the same configuration on your production server

## Support

If you encounter issues:

1. Check the logs mentioned in the troubleshooting section
2. Verify all URLs and tokens are correct
3. Ensure all services are running and accessible
4. Test each component individually before combining them
