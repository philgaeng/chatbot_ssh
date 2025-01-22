# Use the Rasa base image with Python 3.8
FROM rasa/rasa:3.6.20-full

# Switch to root user for setup
USER root

# Set environment variables
ENV APP_DIR=/app

# Install necessary tools, upgrade pip, and clean up
RUN apt-get update && apt-get install -y curl vim && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install "SQLAlchemy<2.0" && \
    rm -rf /var/lib/apt/lists/*

# Create application directory and logs
RUN mkdir -p $APP_DIR/logs && chmod -R 755 $APP_DIR

# Copy project files
COPY domain $APP_DIR/domain
COPY merge_domain.py $APP_DIR/merge_domain.py
COPY actions $APP_DIR/actions
COPY models $APP_DIR/models
COPY config.yml $APP_DIR/config.yml
COPY data $APP_DIR/data
COPY requirements.txt $APP_DIR/requirements.txt

# Install dependencies
RUN python3 -m pip install --no-cache-dir -r $APP_DIR/requirements.txt

# Set permissions for all files in /app
RUN chmod -R 755 $APP_DIR && chown -R 1000:1000 $APP_DIR

# Clean up temporary files
RUN rm -rf /tmp/* /var/tmp/*

# Set the working directory
WORKDIR $APP_DIR

# Copy and set permissions for scripts
COPY start.sh $APP_DIR/start.sh
COPY start_train.sh $APP_DIR/start_train.sh
RUN chmod +x $APP_DIR/start.sh $APP_DIR/start_train.sh

# Expose necessary ports
EXPOSE 5000 5005 5432

# Add a health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5005/ || exit 1

# Default command
CMD ["bash", "/app/start.sh"]
