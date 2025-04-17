#!/bin/bash

# Configuration
TRAIN_INSTANCE_ID="i-05eb666c1e981d45c"  # Replace with your rasa-train instance ID
GREEN='\033[0;32m'
NC='\033[0m'
KEY_FILE="/home/ubuntu/.ssh/pg_rasa_train.pem"

echo -e "${GREEN}Starting training instance...${NC}"

# Start the training instance
aws ec2 start-instances --instance-ids $TRAIN_INSTANCE_ID
aws ec2 wait instance-running --instance-ids $TRAIN_INSTANCE_ID

# Get private IP instead of public IP
PRIVATE_IP=$(aws ec2 describe-instances \
    --instance-ids $TRAIN_INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PrivateIpAddress' \
    --output text)

echo -e "${GREEN}Instance private IP: $PRIVATE_IP${NC}"

# Wait for SSH to be available
while ! nc -z $PRIVATE_IP 22; do
    echo "Waiting for SSH to be available..."
    sleep 5
done

echo -e "${GREEN}SSH is available${NC}"

# Sync only the necessary training files
echo -e "${GREEN}Syncing training files...${NC}"
rsync -av -e "ssh -i $KEY_FILE" --progress \
    --include="domain.yml" \
    --include="config.yml" \
    --include="data/***" \
    --exclude="*" \
    ../nepal_chatbot/ ubuntu@$PRIVATE_IP:~/nepal_chatbot/

# Run training
echo -e "${GREEN}Starting Rasa training...${NC}"
ssh -i $KEY_FILE ubuntu@$PRIVATE_IP << 'EOF'
    cd nepal_chatbot
    source /home/ubuntu/rasa-env-21/bin/activate
    rasa train
    echo "Training complete!"
EOF

# Copy only the new model back
echo -e "${GREEN}Copying trained model back...${NC}"
scp -i $KEY_FILE ubuntu@$PRIVATE_IP:~/nepal_chatbot/models/* ../nepal_chatbot/models/

# Stop the instance
echo -e "${GREEN}Stopping training instance...${NC}"
aws ec2 stop-instances --instance-ids $TRAIN_INSTANCE_ID

echo -e "${GREEN}Training process complete! New model has been copied to your models directory.${NC}" 