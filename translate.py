import os
import openai
from typing import Optional

def translate_to_english(nepali_text: str) -> Optional[str]:
    """
    Translate Nepali text to English using OpenAI's API.
    
    Args:
        nepali_text (str): The Nepali text to translate
        
    Returns:
        Optional[str]: The translated English text, or None if translation fails
    """
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Create the prompt for translation
        prompt = f"""Translate the following Nepali text to English. 
        Only provide the translation without any additional text or explanations.
        
        Nepali text: {nepali_text}
        
        English translation:"""
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional Nepali to English translator. Provide only the translation without any additional text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        # Extract and return the translation
        translation = response.choices[0].message.content.strip()
        return translation
        
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return None

def main():
    # Example usage
    nepali_text = "नमस्कार, म कसरी मद्दत गर्न सक्छु?"
    translation = translate_to_english(nepali_text)
    
    if translation:
        print(f"Nepali: {nepali_text}")
        print(f"English: {translation}")
    else:
        print("Translation failed")

if __name__ == "__main__":
    main() 