# Multilingual NLU Training for Nepal Chatbot

## Overview

This directory contains the NLU training data for the Nepal Chatbot, which supports both English and Nepali languages. To ensure optimal training performance and avoid language-specific tokenization issues, we use separate NLU files for each language.

## File Structure

```
data/nlu/
├── nlu.yml          # Main NLU file (English only)
├── nlu_en.yml       # English-only intents
├── nlu_ne.yml       # Nepali-only intents
└── README.md        # This file
```

## Why Separate Language Files?

### Problems with Mixed Language Training

1. **Tokenization Issues**: Rasa uses language-specific tokenizers (e.g., `SpacyTokenizer` with `en_core_web_md`). Mixing Devanagari (Nepali) and Latin (English) scripts confuses the tokenizer.

2. **Embedding Confusion**: The DIET classifier learns embeddings based on training data. Mixed language examples create conflicting patterns.

3. **Training Performance**: The model struggles to learn clear decision boundaries when examples from different languages are mixed.

4. **Maintenance Issues**: It becomes harder to maintain and debug intent recognition.

### Benefits of Separate Files

1. **Clean Training**: Each language gets its own dedicated training data
2. **Better Performance**: Language-specific tokenization and embeddings
3. **Easier Maintenance**: Clear separation of concerns
4. **Flexible Deployment**: Can train separate models for each language if needed

## Current Approach

### Primary Training (English)
- **Main file**: `nlu.yml` (English only)
- **Used for**: Primary model training
- **Language detection**: Handled by the `LanguageHelper` class in actions

### Multilingual Support
- **Response generation**: Uses `utterance_mapping_rasa.py` for language-specific responses
- **Language switching**: Users can switch languages using `/ne` or `/en` commands
- **Dynamic responses**: All bot responses are generated in the user's preferred language

## Training Strategy

### Option 1: Single Model (Current)
- Train on `nlu.yml` (English only)
- Use language detection to route responses
- Pros: Simpler deployment, single model
- Cons: Limited Nepali intent recognition

### Option 2: Separate Models (Future)
- Train separate models on `nlu_en.yml` and `nlu_ne.yml`
- Use language detection to route to appropriate model
- Pros: Better intent recognition for both languages
- Cons: More complex deployment, two models to maintain

### Option 3: Combined Training (Not Recommended)
- Combine both language files into one
- Pros: Single model handles both languages
- Cons: Poor performance due to tokenization conflicts

## Usage

### For Training
```bash
# Train on English only (current approach)
rasa train --data data/nlu/nlu.yml

# Train on Nepali only (if using separate models)
rasa train --data data/nlu/nlu_ne.yml

# Train on both (not recommended)
rasa train --data data/nlu/
```

### For Development
- Use `nlu_en.yml` for English intent testing
- Use `nlu_ne.yml` for Nepali intent testing
- Keep `nlu.yml` as the main training file

## Language Detection

The chatbot uses the `LanguageHelper` class in `actions/base_classes.py` to:
- Detect user language based on script (Devanagari vs Latin)
- Provide language-specific skip words and patterns
- Support fuzzy matching for different languages

## Response Generation

All bot responses are generated using the multilingual utterance mapping system in `actions/utterance_mapping_rasa.py`, which provides:
- Language-specific responses for all actions
- Localized buttons and options
- Context-aware language switching

## Best Practices

1. **Keep intents language-specific**: Don't mix languages in the same intent
2. **Use language detection**: Let the system detect user language automatically
3. **Maintain separate files**: Keep English and Nepali examples separate
4. **Test both languages**: Ensure both language paths work correctly
5. **Document changes**: Update this README when adding new intents

## Future Improvements

1. **Separate model training**: Train dedicated models for each language
2. **Enhanced language detection**: Improve accuracy of language detection
3. **More Nepali examples**: Add more natural Nepali expressions
4. **Dialect support**: Support for different Nepali dialects
5. **Voice support**: Add voice input/output for both languages 