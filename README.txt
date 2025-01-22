### Prerequisites

- Python 3.9
- Rasa 3.1.0

Install dependencies using:

```bash
pip install -r requirements.txt


## Steps to Launch the Project

### 1. Update the Server Public IP in Nginx Configuration
1. Open the Nginx configuration file:
   ```bash
   sudo nano /etc/nginx/sites-available/default
   ```
2. Replace the existing server IP with the current public IP address in the `server_name` directive.
3. Save and exit the file (`Ctrl+O`, then `Enter`, followed by `Ctrl+X`).
4. Restart the Nginx service:
   ```bash
   sudo systemctl restart nginx
   ```

### 2. Update the Server Public IP in `config.js`
1. Navigate to the project directory:
   ```bash
   cd /home/ubuntu/nepal_chatbot/test_webchat
   ```
2. Open the `config.js` file:
   ```bash
   nano config.js
   ```
3. Replace the old public IP with the current one in the `RASA_SERVER_URL` field:
   ```javascript
   const PUBLIC_IP = "<new-public-ip>";
   ```
4. Save and exit the file.

### 3. Update the Local Private IP in `credentials.yml`
1. Open the `credentials.yml` file:
   ```bash
   nano /home/ubuntu/nepal_chatbot/credentials.yml
   ```
2. Locate the line where the private IP is defined (e.g., `url:`) and replace it with the current private IP address.
3. Save and exit the file.

### 4. Start the Servers
1. Activate the Rasa virtual environment:
   ```bash
   source /home/ubuntu/nepal_chatbot/rasa-env/bin/activate
   ```
2. Start the Rasa server:
   ```bash
   rasa run --enable-api --cors "*"
   ```
3. Start the Nginx service if not already running:
   ```bash
   sudo systemctl start nginx
   ```
4. (Optional) Start any other required services or background jobs.

---

## Basic Commands

### Common Commands:
1. **Restart Nginx**:
   ```bash
   sudo systemctl restart nginx
   ```
2. **Check Nginx Status**:
   ```bash
   sudo systemctl status nginx
   ```
3. **Activate Virtual Environment**:
   ```bash
   source /home/ubuntu/nepal_chatbot/rasa-env/bin/activate
   ```
4. **Start Rasa Server**:
   ```bash
   rasa run --enable-api --cors "*" --debug

   rasa run --enable-api --cors "*"
   ```
5. **View Nginx Logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```
6. **View Rasa Logs**:
   ```bash
   tail -f /path/to/rasa/logs
   ```

---

## Notes
- Ensure all required ports (e.g., 5005 for Rasa, 80/443 for Nginx) are open in the server's security group.
- After any IP changes, ensure DNS records are updated if applicable.
- Use `sudo` wherever permissions are required.## Steps to Launch the Project

### 1. Update the Server Public IP in Nginx Configuration
1. Open the Nginx configuration file:
   ```bash
   sudo nano /etc/nginx/sites-available/default
   ```
2. Replace the existing server IP with the current public IP address in the `server_name` directive.
3. Save and exit the file (`Ctrl+O`, then `Enter`, followed by `Ctrl+X`).
4. Restart the Nginx service:
   ```bash
   sudo systemctl restart nginx
   ```

### 2. Update the Server Public IP in `config.js`
1. Navigate to the project directory:
   ```bash
   cd /home/ubuntu/nepal_chatbot/test_webchat
   ```
2. Open the `config.js` file:
   ```bash
   nano config.js
   ```
3. Replace the old public IP with the current one in the `RASA_SERVER_URL` field:
   ```javascript
   const PUBLIC_IP = "<new-public-ip>";
   ```
4. Save and exit the file.

### 3. Update the Local Private IP in `credentials.yml`
1. Open the `credentials.yml` file:
   ```bash
   nano /home/ubuntu/nepal_chatbot/credentials.yml
   ```
2. Locate the line where the private IP is defined (e.g., `url:`) and replace it with the current private IP address.
3. Save and exit the file.

### 4. Start the Servers
1. Activate the Rasa virtual environment:
   ```bash
   source /home/ubuntu/nepal_chatbot/rasa-env/bin/activate
   ```
2. Start the Rasa server:
   ```bash
   rasa run --enable-api --cors "*"
   ```
3. Start the Nginx service if not already running:
   ```bash
   sudo systemctl start nginx
   ```
4. (Optional) Start any other required services or background jobs.

---

## Basic Commands

### Common Commands:
1. **Restart Nginx**:
   ```bash
   sudo systemctl restart nginx
   ```
2. **Check Nginx Status**:
   ```bash
   sudo systemctl status nginx
   ```
3. **Activate Virtual Environment**:
   ```bash
   source /home/ubuntu/nepal_chatbot/rasa-env/bin/activate
   ```
4. **Start Rasa Server**:
   ```bash
   rasa run --enable-api --cors "*" --debug

   rasa run --enable-api --cors "*"
   ```
5. **View Nginx Logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```
6. **View Rasa Logs**:
   ```bash
   tail -f /path/to/rasa/logs
   ```

---

## Notes
- Ensure all required ports (e.g., 5005 for Rasa, 80/443 for Nginx) are open in the server's security group.
- After any IP changes, ensure DNS records are updated if applicable.
- Use `sudo` wherever permissions are required.