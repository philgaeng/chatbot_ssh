#!/usr/bin/env python3

# Debug script to test inheritance
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.database_services.base_manager import BaseDatabaseManager
from backend.services.database_services.grievance_manager import TranscriptionDbManager, TranslationDbManager

def test_inheritance():
    print("Testing inheritance...")
    
    # Test BaseDatabaseManager
    print("1. Testing BaseDatabaseManager...")
    base = BaseDatabaseManager()
    print(f"   Base has select_query_data: {hasattr(base, 'select_query_data')}")
    print(f"   Base dir: {[attr for attr in dir(base) if 'select' in attr.lower()]}")
    
    # Check if the method exists in the class
    print(f"   Base class has select_query_data: {hasattr(BaseDatabaseManager, 'select_query_data')}")
    
    # Test TranscriptionDbManager
    print("2. Testing TranscriptionDbManager...")
    transcription = TranscriptionDbManager()
    print(f"   Transcription has select_query_data: {hasattr(transcription, 'select_query_data')}")
    print(f"   Transcription dir: {[attr for attr in dir(transcription) if 'select' in attr.lower()]}")
    
    # Check if the method exists in the class
    print(f"   Transcription class has select_query_data: {hasattr(TranscriptionDbManager, 'select_query_data')}")
    
    # Test TranslationDbManager
    print("3. Testing TranslationDbManager...")
    translation = TranslationDbManager()
    print(f"   Translation has select_query_data: {hasattr(translation, 'select_query_data')}")
    print(f"   Translation dir: {[attr for attr in dir(translation) if 'select' in attr.lower()]}")
    
    # Check if the method exists in the class
    print(f"   Translation class has select_query_data: {hasattr(TranslationDbManager, 'select_query_data')}")
    
    # Check method resolution order
    print("4. Method Resolution Order:")
    print(f"   Base MRO: {BaseDatabaseManager.__mro__}")
    print(f"   Transcription MRO: {TranscriptionDbManager.__mro__}")
    print(f"   Translation MRO: {TranslationDbManager.__mro__}")

if __name__ == "__main__":
    test_inheritance() 