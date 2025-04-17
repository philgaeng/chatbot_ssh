#!/bin/bash
# Setup script for Rasa 3.6.21 on Python 3.10

# Create and activate a new Python 3.10 virtual environment
python3.10 -m venv ~/rasa-env-21
source ~/rasa-env-21/bin/activate

# Check initial pip version
echo "Current pip version:"
pip --version

# Upgrade pip thoroughly
python3.10 -m pip install --upgrade pip setuptools wheel
echo "Pip version after upgrade:"
pip --version

# Install Rasa with spacy extras first to establish core dependencies
pip install "rasa[spacy]==3.6.21"

# Install rasa-sdk
pip install rasa-sdk==3.6.2

# Install spacy and download the English model
python -m spacy download en_core_web_md

# Only install additional dependencies if needed and not conflicting
# with what Rasa has already installed
pip install tensorflow==2.12.0
pip install scikit-learn==1.1.3
pip install python-crfsuite==0.9.11

# Print version info
echo "Installation complete! Checking versions:"
python --version
pip --version
rasa --version
spacy --version

echo "You can now copy your project files from GitHub and start developing!" 