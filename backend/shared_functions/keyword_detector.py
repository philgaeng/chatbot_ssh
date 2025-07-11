import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import os
from backend.config.constants import DEFAULT_VALUES
logger = logging.getLogger(__name__)
DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES['DEFAULT_LANGUAGE_CODE']

class DetectionLevel(Enum):
    """Detection levels for sensitive content"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class KeywordMatch:
    """Represents a keyword match with context"""
    keyword: str
    category: str
    level: DetectionLevel
    confidence: float
    context: str
    start_pos: int
    end_pos: int

@dataclass
class DetectionResult:
    """Result of keyword detection"""
    detected: bool
    level: DetectionLevel
    category: str
    confidence: float
    matches: List[KeywordMatch]
    message: str
    action_required: bool

class KeywordDetector:
    """
    Keyword-based detector for sensitive content with multiple thresholds.
    Designed for offline use in rural Nepal with limited connectivity.
    """
    
    def __init__(self, language_code: str = DEFAULT_LANGUAGE_CODE):
        self.language_code = language_code
        self.keyword_patterns = self._load_keyword_patterns()
        self.thresholds = self._load_thresholds()
    
    def _initialize_constants(self, language_code: str = DEFAULT_LANGUAGE_CODE):
        self.language_code = language_code
        
    def _load_keyword_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load keyword patterns for different categories"""
        return {
            "sexual_assault": {
                "en": {
                    "critical": [
                        r"\b(rape|raped|raping)\b",
                        r"\b(sexual assault|sexually assaulted)\b",
                        r"\b(molest|molested|molesting)\b",
                        r"\b(touch(ed|ing)?\s+(my|her|his)\s+(private|body|breast|vagina|penis))\b",
                        r"\b(kiss(ed|ing)?\s+(me|her|him)\s+(force|against|without))\b",
                        r"\b(unwanted\s+sexual\s+(contact|advance|behavior))\b"
                    ],
                    "high": [
                        r"\b(touch(ed|ing)?\s+(my|her|his)\s+(leg|arm|hand|face))\b",
                        r"\b(kiss(ed|ing)?\s+(me|her|him))\b",
                        r"\b(hug(ged|ging)?\s+(me|her|him)\s+(force|against))\b",
                        r"\b(stare(ed|ing)?\s+(at|me|her|him)\s+(inappropriately|lewdly))\b",
                        r"\b(sexual\s+(harassment|harassed|harassing))\b"
                    ],
                    "medium": [
                        r"\b(uncomfortable\s+(touch|kiss|hug|behavior))\b",
                        r"\b(inappropriate\s+(touch|kiss|hug|behavior))\b",
                        r"\b(unwanted\s+(touch|kiss|hug|attention))\b",
                        r"\b(sexual\s+(comment|remark|joke|gesture))\b"
                    ],
                    "low": [
                        r"\b(touch(ed|ing)?\s+(me|her|him))\b",
                        r"\b(kiss(ed|ing)?)\b",
                        r"\b(hug(ged|ging)?)\b",
                        r"\b(stare(ed|ing)?)\b"
                    ]
                },
                "ne": {
                    "critical": [
                        r"\b(बलात्कार|बलात्कार गरे|बलात्कार गर्दै)\b",
                        r"\b(यौन हिंसा|यौन दुर्व्यवहार)\b",
                        r"\b(छुनु|छोएको|छोएर)\b",
                        r"\b(चुम्बन|चुम्बन गरे|चुम्बन गर्दै)\b"
                    ],
                    "high": [
                        r"\b(अश्लील|अश्लील व्यवहार)\b",
                        r"\b(यौन उत्पीडन|यौन उत्पीडन गरे)\b",
                        r"\b(अनुचित|अनुचित व्यवहार)\b"
                    ],
                    "medium": [
                        r"\b(असहज|असहज महसुस)\b",
                        r"\b(अनचाहे|अनचाहे व्यवहार)\b"
                    ],
                    "low": [
                        r"\b(छुनु|चुम्बन|अलिंगन)\b"
                    ]
                }
            },
            "harassment": {
                "en": {
                    "critical": [
                        r"\b(threaten(ed|ing)?\s+(to\s+)?(kill|hurt|harm|rape))\b",
                        r"\b(stalk(ed|ing)?\s+(me|her|him))\b",
                        r"\b(blackmail(ed|ing)?)\b"
                    ],
                    "high": [
                        r"\b(harass(ed|ing)?\s+(me|her|him))\b",
                        r"\b(bully(ing|ied)?\s+(me|her|him))\b",
                        r"\b(intimidat(e|ed|ing)?)\b"
                    ],
                    "medium": [
                        r"\b(unwanted\s+(attention|calls|messages))\b",
                        r"\b(follow(ed|ing)?\s+(me|her|him))\b"
                    ],
                    "low": [
                        r"\b(call(ed|ing)?\s+(me|her|him))\b",
                        r"\b(message(ed|ing)?\s+(me|her|him))\b"
                    ]
                },
                "ne": {
                    "critical": [
                        r"\b(धम्की|धम्की दिए|धम्की दिँदै)\b",
                        r"\b(पछ्याउनु|पछ्याएको|पछ्याउँदै)\b"
                    ],
                    "high": [
                        r"\b(उत्पीडन|उत्पीडन गरे)\b",
                        r"\b(धम्काउनु|धम्काएको)\b"
                    ],
                    "medium": [
                        r"\b(अनचाहे|अनचाहे ध्यान)\b"
                    ],
                    "low": [
                        r"\b(कल|मेसेज|फोन)\b"
                    ]
                }
            },
            "land_issues": {
                "en": {
                    "critical": [
                        r"\b(force(ed|ing)?\s+(to\s+)?(leave|evict|move))\b",
                        r"\b(destroy(ed|ing)?\s+(my|our)\s+(house|home|property))\b",
                        r"\b(burn(ed|ing)?\s+(my|our)\s+(house|home))\b"
                    ],
                    "high": [
                        r"\b(land\s+(grab|grabbed|grabbing))\b",
                        r"\b(property\s+(seizure|seized|seizing))\b",
                        r"\b(compensation\s+(not\s+)?(given|received|paid))\b"
                    ],
                    "medium": [
                        r"\b(land\s+(issue|problem|dispute))\b",
                        r"\b(property\s+(issue|problem|dispute))\b",
                        r"\b(relocation\s+(issue|problem))\b"
                    ],
                    "low": [
                        r"\b(land|property|house|home)\b"
                    ]
                },
                "ne": {
                    "critical": [
                        r"\b(जबर्जस्ती|जबर्जस्ती बसाइ|जबर्जस्ती निकाल्नु)\b",
                        r"\b(घर|मकान|जग्गा|जमिन)\s+(जलाउनु|जलाएको|जलाउँदै)\b"
                    ],
                    "high": [
                        r"\b(जग्गा|जमिन)\s+(कब्जा|कब्जा गरे)\b",
                        r"\b(मुआबजा|मुआबजा नदिएको)\b"
                    ],
                    "medium": [
                        r"\b(जग्गा|जमिन)\s+(समस्या|मुद्दा)\b",
                        r"\b(बसाइ|बसाइ सरुवा)\s+(समस्या|मुद्दा)\b"
                    ],
                    "low": [
                        r"\b(जग्गा|जमिन|घर|मकान)\b"
                    ]
                }
            },
            "violence": {
                "en": {
                    "critical": [
                        r"\b(kill(ed|ing)?\s+(me|her|him|someone))\b",
                        r"\b(beat(ing|en)?\s+(me|her|him|someone))\b",
                        r"\b(hit(ting)?\s+(me|her|him|someone))\b",
                        r"\b(punch(ed|ing)?\s+(me|her|him|someone))\b"
                    ],
                    "high": [
                        r"\b(fight(ing|en)?\s+(with|against))\b",
                        r"\b(attack(ed|ing)?\s+(me|her|him|someone))\b",
                        r"\b(assault(ed|ing)?)\b"
                    ],
                    "medium": [
                        r"\b(violence|violent)\b",
                        r"\b(abuse(d|ing)?)\b"
                    ],
                    "low": [
                        r"\b(hurt|pain|injury)\b"
                    ]
                },
                "ne": {
                    "critical": [
                        r"\b(मार्नु|मारेको|मार्दै)\b",
                        r"\b(कुट्नु|कुटेको|कुट्दै)\b",
                        r"\b(घोप्टो|घोप्टो लगाएको)\b"
                    ],
                    "high": [
                        r"\b(झगडा|झगडा गरे)\b",
                        r"\b(आक्रमण|आक्रमण गरे)\b"
                    ],
                    "medium": [
                        r"\b(हिंसा|हिंसात्मक)\b",
                        r"\b(दुर्व्यवहार|दुर्व्यवहार गरे)\b"
                    ],
                    "low": [
                        r"\b(चोट|दुखाइ|पीडा)\b"
                    ]
                }
            }
        }
    
    def _load_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Load confidence thresholds for different detection levels"""
        return {
            "sexual_assault": {
                "critical": 0.9,
                "high": 0.7,
                "medium": 0.5,
                "low": 0.3
            },
            "harassment": {
                "critical": 0.9,
                "high": 0.7,
                "medium": 0.5,
                "low": 0.3
            },
            "land_issues": {
                "critical": 0.8,
                "high": 0.6,
                "medium": 0.4,
                "low": 0.2
            },
            "violence": {
                "critical": 0.9,
                "high": 0.7,
                "medium": 0.5,
                "low": 0.3
            }
        }
    
    def detect_sensitive_content(self, text: str) -> DetectionResult:
        """
        Detect sensitive content in the given text.
        
        Args:
            text: The text to analyze
            
        Returns:
            DetectionResult with detection information
        """
        if not text:
            return DetectionResult(
                detected=False,
                level=DetectionLevel.LOW,
                category="",
                confidence=0.0,
                matches=[],
                message="",
                action_required=False
            )
        
        text_lower = text.lower()
        all_matches = []
        
        # Check each category
        for category, patterns in self.keyword_patterns.items():
            lang_patterns = patterns.get(self.language_code, patterns.get("en", {}))
            
            for level_name, pattern_list in lang_patterns.items():
                level = DetectionLevel(level_name)
                
                for pattern in pattern_list:
                    matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                    
                    for match in matches:
                        confidence = self._calculate_confidence(match, text_lower, level)
                        
                        if confidence >= self.thresholds[category][level_name]:
                            keyword_match = KeywordMatch(
                                keyword=match.group(),
                                category=category,
                                level=level,
                                confidence=confidence,
                                context=text[max(0, match.start()-20):match.end()+20],
                                start_pos=match.start(),
                                end_pos=match.end()
                            )
                            all_matches.append(keyword_match)
        
        if not all_matches:
            return DetectionResult(
                detected=False,
                level=DetectionLevel.LOW,
                category="",
                confidence=0.0,
                matches=[],
                message="",
                action_required=False
            )
        
        # Find the highest level match
        highest_match = max(all_matches, key=lambda x: (x.level.value, x.confidence))
        
        # Determine if action is required
        action_required = highest_match.level in [DetectionLevel.CRITICAL, DetectionLevel.HIGH]
        
        # Generate appropriate message
        message = self._generate_detection_message(highest_match, all_matches)
        
        return DetectionResult(
            detected=True,
            level=highest_match.level,
            category=highest_match.category,
            confidence=highest_match.confidence,
            matches=all_matches,
            message=message,
            action_required=action_required
        )
    
    def _calculate_confidence(self, match, text: str, level: DetectionLevel) -> float:
        """Calculate confidence score for a keyword match"""
        base_confidence = {
            DetectionLevel.CRITICAL: 0.9,
            DetectionLevel.HIGH: 0.7,
            DetectionLevel.MEDIUM: 0.5,
            DetectionLevel.LOW: 0.3
        }
        
        # Adjust based on context
        context_bonus = 0.0
        
        # Check if surrounding words provide additional context
        start = max(0, match.start() - 10)
        end = min(len(text), match.end() + 10)
        context = text[start:end]
        
        # Add bonus for additional context words
        context_words = ["force", "unwanted", "inappropriate", "against", "without", "consent"]
        for word in context_words:
            if word in context:
                context_bonus += 0.1
        
        return min(1.0, base_confidence[level] + context_bonus)
    
    def _generate_detection_message(self, highest_match: KeywordMatch, all_matches: List[KeywordMatch]) -> str:
        """Generate appropriate message based on detection level"""
        
        if self.language_code == "ne":
            messages = {
                DetectionLevel.CRITICAL: {
                    "sexual_assault": "यो यौन हिंसा जस्तो देखिन्छ। के तपाईं यौन हिंसाको रिपोर्ट दिन चाहनुहुन्छ?",
                    "harassment": "यो धम्की वा उत्पीडन जस्तो देखिन्छ। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?",
                    "land_issues": "यो जबर्जस्ती बसाइ सरुवा जस्तो देखिन्छ। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?",
                    "violence": "यो हिंसा जस्तो देखिन्छ। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?"
                },
                DetectionLevel.HIGH: {
                    "sexual_assault": "यसमा यौन सम्बन्धित समस्या देखिन्छ। के तपाईं यौन उत्पीडनको रिपोर्ट दिन चाहनुहुन्छ?",
                    "harassment": "यसमा उत्पीडन जस्तो देखिन्छ। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?",
                    "land_issues": "यसमा जग्गा सम्बन्धित समस्या देखिन्छ। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?",
                    "violence": "यसमा हिंसा जस्तो देखिन्छ। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?"
                },
                DetectionLevel.MEDIUM: {
                    "sexual_assault": "यसमा केही यौन सम्बन्धित शब्दहरू देखिन्छन्। के तपाईं यौन उत्पीडनको रिपोर्ट दिन चाहनुहुन्छ?",
                    "harassment": "यसमा केही उत्पीडन सम्बन्धित शब्दहरू देखिन्छन्। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?",
                    "land_issues": "यसमा केही जग्गा सम्बन्धित शब्दहरू देखिन्छन्। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?",
                    "violence": "यसमा केही हिंसा सम्बन्धित शब्दहरू देखिन्छन्। के तपाईं यसको रिपोर्ट दिन चाहनुहुन्छ?"
                }
            }
        else:
            messages = {
                DetectionLevel.CRITICAL: {
                    "sexual_assault": "This appears to be sexual assault. Would you like to report sexual assault?",
                    "harassment": "This appears to be threats or harassment. Would you like to report this?",
                    "land_issues": "This appears to be forced eviction. Would you like to report this?",
                    "violence": "This appears to be violence. Would you like to report this?"
                },
                DetectionLevel.HIGH: {
                    "sexual_assault": "This contains sexual harassment content. Would you like to report sexual harassment?",
                    "harassment": "This contains harassment content. Would you like to report this?",
                    "land_issues": "This contains land-related issues. Would you like to report this?",
                    "violence": "This contains violence. Would you like to report this?"
                },
                DetectionLevel.MEDIUM: {
                    "sexual_assault": "This contains some sexual-related words. Would you like to report sexual harassment?",
                    "harassment": "This contains some harassment-related words. Would you like to report this?",
                    "land_issues": "This contains some land-related words. Would you like to report this?",
                    "violence": "This contains some violence-related words. Would you like to report this?"
                }
            }
        
        return messages.get(highest_match.level, {}).get(highest_match.category, "")
    
    def get_detection_buttons(self, result: DetectionResult) -> List[Dict[str, str]]:
        """Generate appropriate buttons based on detection result"""
        if not result.action_required:
            return []
        
        if self.language_code == "ne":
            return [
                {"title": "हो, रिपोर्ट गर्नुहोस्", "payload": "/affirm_sensitive_content"},
                {"title": "होइन, मैले गलत बुझेको हुन सक्छु", "payload": "/deny_sensitive_content"},
                {"title": "छोड्नुहोस्", "payload": "/skip"}
            ]
        else:
            return [
                {"title": "Yes, report this", "payload": "/affirm_sensitive_content"},
                {"title": "No, I may have misunderstood", "payload": "/deny_sensitive_content"},
                {"title": "Skip", "payload": "/skip"}
            ]

# Example usage and testing
if __name__ == "__main__":
    detector = KeywordDetector(language_code="en")
    
    test_cases = [
        "Someone kissed me without my consent",
        "They touched my leg inappropriately",
        "I have a land dispute with my neighbor",
        "Someone threatened to kill me",
        "I lost my harvest due to rain"
    ]
    
    for test_case in test_cases:
        result = detector.detect_sensitive_content(test_case)
        print(f"Text: {test_case}")
        print(f"Detected: {result.detected}")
        print(f"Level: {result.level}")
        print(f"Category: {result.category}")
        print(f"Message: {result.message}")
        print(f"Action Required: {result.action_required}")
        print("---") 