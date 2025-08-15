"""
This module provides functions for analyzing text content to inform Text-to-Speech (TTS)
voice selection and speech parameters. It leverages Google Cloud Natural Language API
for language detection, sentiment analysis, content categorization, and syntax complexity,
as well as Google Cloud Text-to-Speech API for voice management and synthesis.
Additionally, it includes functionality for detecting regional English variations
and dynamic voice parameter adjustment based on text characteristics.
"""
import random
import time
import re
import os
import logging
from typing import Protocol, List, Optional, Dict, Set, Any, Tuple
from abc import ABC, abstractmethod
import nltk
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from google.cloud import language_v1
from google.cloud import texttospeech
from google.api_core.exceptions import ResourceExhausted, InternalServerError, ServiceUnavailable

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not installed. Low memory warnings will be disabled.")

# --- Custom Exception ---

class ChunkingError(Exception):
    """Custom exception raised for fatal errors during text chunking."""
    pass

# --- Interface Definitions ---

class LanguageAnalyzer(Protocol):
    """
    Protocol for classes that perform various linguistic analyses on text.
    """
    def analyze_language(self, text: str) -> str:
        """
        Detects the language of a given text.

        Args:
            text (str): The text content to analyze.

        Returns:
            str: The language code (e.g., 'en-US', 'es-ES').
        """
        ...
    def analyze_sentiment(self, text: str) -> Tuple[float, float]:
        """
        Determines the sentiment of the text.

        Args:
            text (str): The text content to analyze.

        Returns:
            Tuple[float, float]: A tuple containing the sentiment score and magnitude.
        """
        ...
    def analyze_category(self, text: str) -> List[str]:
        """
        Classifies the text into one or more content categories.

        Args:
            text (str): The text content to analyze.

        Returns:
            List[str]: A list of categories the text belongs to.
        """
        ...
    def analyze_syntax_complexity(self, text: str) -> Dict[str, Any]:
        """
        Analyzes the syntactic structure and complexity of the text.

        Args:
            text (str): The text content to analyze.

        Returns:
            Dict[str, Any]: A dictionary containing information about syntax (e.g., sentence structure).
        """
        ...
    def analyze_regional_context(self, text: str, detected_code: str) -> Optional[str]:
        """
        Analyzes the text for regional variations (e.g., regionalisms).

        Args:
            text (str): The text content to analyze.
            detected_code (str): The language code of the text.

        Returns:
            Optional[str]: A regional code (e.g., 'US', 'UK') if detected, otherwise None.
        """
        ...

class TTSVoiceSelector(Protocol):
    """
    Protocol for classes that select and configure a voice for Text-to-Speech (TTS).
    """
    def get_available_voices(self, language_code: Optional[str] = None) -> List[Any]:
        """
        Retrieves a list of available TTS voices.

        Args:
            language_code (Optional[str], optional): A specific language code to filter the voices.
                                                    Defaults to None.

        Returns:
            List[Any]: A list of available voice objects.
        """
        ...
    def get_contextual_voice_parameters(
        self,
        detected_language_code: str,
        sentiment_score: float,
        categories: Optional[List[str]] = None,
        syntax_info: Optional[Dict[str, Any]] = None,
        user_gender_preference: Optional[texttospeech.SsmlVoiceGender] = None,
        regional_code_from_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Selects suitable Google Cloud Text-to-Speech voice parameters based on contextual factors.

        Args:
            detected_language_code (str): The primary language code detected by Natural Language API.
            sentiment_score (float): The sentiment score of the text (from -1.0 to 1.0).
            categories (Optional[List[str]], optional): A list of category names for the text. Defaults to None.
            syntax_info (Optional[Dict[str, Any]], optional): A dictionary containing syntax complexity metrics. Defaults to None.
            user_gender_preference (Optional[texttospeech.SsmlVoiceGender], optional): User's preferred
                                                                                        gender for the narrator. Defaults to None.
            regional_code_from_text (Optional[str], optional): A more specific regional language code
                                                                derived from text analysis. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary containing the selected voice parameters.
        """
        ...

class TTSSynthesizer(Protocol):
    """Protocol for classes that synthesize audio from text."""
    def synthesize(
            self,
            text: str,
            voice_params: Dict[str, Any],
            output_filename: str,
            pitch: float = 0.0,
            speaking_rate: float = 1.0
            ) -> bool:
        """
        Synthesizes a text string into an audio file.

        Args:
            text (str): The text content to synthesize.
            voice_params (Dict[str, Any]): A dictionary of voice parameters.
            output_filename (str): The name of the output audio file.
            pitch (float, optional): The speaking pitch of the synthesized voice. Defaults to 0.0.
            speaking_rate (float, optional): The speaking rate relative to the normal
                                            speed (0.25 to 4.0). Defaults to 1.0.

        Returns:
            bool: True if the synthesis was successful, False otherwise.
        """
        ...

class UserPreferenceProvider(Protocol):
    """Protocol for classes that retrieve user-defined preferences for TTS."""
    def get_gender_preference(self) -> Optional[texttospeech.SsmlVoiceGender]:
        """
        Retrieves the user's preferred gender for the TTS voice.

        Returns:
            Optional[texttospeech.SsmlVoiceGender]: The preferred gender enum
                                                    (MALE, FEMALE, NEUTRAL), or None
                                                    if no preference.
        """
        ...


# --- Abstractions ---

class TextChunker(ABC):
    """
    Abstract base class for chunking large text content into smaller, manageable pieces.

    This is useful for preparing text for APIs that have character limits.
    """
    @abstractmethod
    def chunk(self, text: str) -> List[str]:
        """
        Breaks down a single string of text into a list of smaller text chunks.

        The chunking logic should prioritize maintaining sentence integrity.

        Args:
            text (str): The large text string to be chunked.

        Returns:
            List[str]: A list of text chunks.
        """
        ...


# --- Implementation Classes ---

class EnglishRegionalisms:
    """
    A repository of words and phrases that are specific to different English regions.

    The words are stored in sets for fast lookup, categorized by their regional code.
    """
    REGIONAL_WORDS: Dict[str, Set[str]] = {
        # These words and phrases are typically associated with US English.
        "US": {
            "color", "honor", "flavor", "labor", "neighbor", "humor", "favor", "splendor", "tumor", "rumor", "valour",
            "center", "meter", "liter", "theater", "fiber",
            "organize", "realize", "recognize", "apologize", "airplane", "truck", "elevator", "sidewalk", "trunk", "fall",
            "gasoline", "subway", "restroom", "bathroom", "french fries", "cookie", "candy", "garbage", "trash",
            "faucet", "schedule", "vacation", "movie", "soccer", "period", "parentheses", "brackets", "dash",
            "mail", "mailbox", "drugstore", "vest", "pants", "diaper", "flashlight", "college", "grades",
            "gotten", "jelly", "suspenders", "zucchini", "check" # banking
            # ... add more as you find them ...
        },
        # These words and phrases are typically associated with British English.
        "GB": {
            "colour", "honour", "flavour", "labour", "neighbour", "humour", "favour", "splendour", "tumour", "rumour", "valour",
            "centre", "metre", "litre", "theatre", "fibre",
            "organise", "realise", "recognise", "apologise", "analyse", "paralyse", "aeroplane", "lorry", "lift", "pavement", "boot", "autumn",
            "petrol", "underground", "tube", "loo", "toilet", "chips", "crisps", "biscuit", "sweets", "rubbish", "dustbin",
            "tap", "timetable", "holiday", "film", "football", "full stop", "brackets", "square brackets", "hyphen",
            "post", "postbox", "chemist's", "waistcoat", "trousers", "nappy", "torch", "university", "marks",
            "got", "jam", "braces", "courgette", "cheque" # banking
            # ... add more as you find them ...
        }
    }

class GoogleLanguageAnalyzer(LanguageAnalyzer):
    """
    A concrete implementation of the LanguageAnalyzer protocol using the Google Cloud
    Natural Language API for various linguistic analyses.

    This class handles text preprocessing, API calls, and returns structured data
    on language, sentiment, categories, syntax, and regional context.
    """
    MIN_LENGTH = 50
    PROACTIVE_DELAY = 0.1
    DEFAULT_SYNTAX_METRICS = {
        "num_sentences": 0,
        "num_tokens": 0,
        "avg_tokens_per_sentence": 0,
        "num_complex_clauses": 0
    }

    def __init__(self):
        """
        Initializes the language analyzer and ensures necessary NLTK data is downloaded.
        """
        ensure_nltk_resource('tokenizers/punkt')
        ensure_nltk_resource('tokenizers/punkt_tab')

    def analyze_language(self, text: str) -> str:
        """
        Detects the dominant language of the input text using Google Natural Language API.
        """
        if not text or len(text) < self.MIN_LENGTH:
            logging.info("Skipping language analysis due to short text length (< %d chars). Defaulting to 'en'.", self.MIN_LENGTH)
            return "en"

        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
        try:
            time.sleep(self.PROACTIVE_DELAY)
            response = client.analyze_sentiment(request={'document': document})
            return response.language if response.language and response.language != 'und' else "en"
        except Exception as e:
            logging.warning("Could not detect language. Error: %s. Defaulting to 'en'.", e)
            return "en"
        
    def analyze_sentiment(self, text: str) -> Tuple[float, float]:
        """
        Analyzes the sentiment (emotional tone) of the input text using Google Natural Language API.
        """
        if not text or len(text) < self.MIN_LENGTH:
            logging.info("Skipping sentiment analysis due to short text length (< %d chars). Defaulting to neutral (0.0, 0.0).", self.MIN_LENGTH)
            return 0.0, 0.0
            
        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
        try:
            time.sleep(self.PROACTIVE_DELAY)
            sentiment = client.analyze_sentiment(request={'document': document}).document_sentiment
            return sentiment.score, sentiment.magnitude
        except Exception as e:
            logging.warning("Could not analyze sentiment. Error: %s. Defaulting to neutral (0.0, 0.0).", e)
            return 0.0, 0.0
  
    def analyze_category(self, text: str) -> List[str]:
        """
        Classifies the content into predefined categories using Google Natural Language API.
        """
        if not text or len(text) < self.MIN_LENGTH:
            logging.info("Skipping category analysis due to short text length (< %d chars). Returning empty list.", self.MIN_LENGTH)
            return []
            
        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
        try:
            time.sleep(self.PROACTIVE_DELAY)
            response = client.classify_text(request={'document': document})
            return [category.name for category in response.categories]
        except Exception as e:
            logging.warning("Could not classify text content. Error: %s. Returning empty list.", e)
            return []
    
    def analyze_syntax_complexity(self, text: str) -> Dict[str, Any]:
        """
        Analyzes sentence structure complexity using Google Natural Language API's syntax analysis.
        
        Args:
            text (str): The text content to analyze.

        Returns:
            Dict[str, Any]: A dictionary containing syntax complexity metrics.
                Returns default zero values if analysis is skipped or fails.
        """
        if not text or len(text) < self.MIN_LENGTH:
            logging.info("Skipping syntax analysis due to short text length (< %d chars). Returning default metrics.", self.MIN_LENGTH)
            return self.DEFAULT_SYNTAX_METRICS
            
        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(
            content=text, type_=language_v1.Document.Type.PLAIN_TEXT
        )
        try:
            time.sleep(self.PROACTIVE_DELAY)
            response = client.analyze_syntax(request={'document': document})
            num_sentences = len(response.sentences)
            num_tokens = len(response.tokens)
            avg_tokens_per_sentence = num_tokens / num_sentences if num_sentences > 0 else 0

            clause_labels = ['acl', 'advcl', 'ccomp', 'csubj', 'xcomp', 'csubjpass', 'auxpass']
            num_complex_clauses = sum(
                1 for token in response.tokens
                if token.dependency_edge.label.name.lower() in clause_labels
            )
            return {
                "num_sentences": num_sentences,
                "num_tokens": num_tokens,
                "avg_tokens_per_sentence": avg_tokens_per_sentence,
                "num_complex_clauses": num_complex_clauses
            }
        except Exception as e:
            logging.warning("Could not analyze syntax complexity. Error: %s. Returning default metrics.", e)
            return self.DEFAULT_SYNTAX_METRICS

    def analyze_regional_context(self, text: str, detected_code: str) -> Optional[str]:
        """
        Analyzes the text for regional English variations (e.g., US vs. GB).

        Args:
            text (str): The text content to analyze.
            detected_code (str): The language code of the text.

        Returns:
            Optional[str]: The regional code (e.g., 'en-US', 'en-GB') if a strong bias
                           is detected, otherwise None.
        """
        if not text or detected_code != "en" or len(text) < self.MIN_LENGTH:
            if detected_code != "en":
                logging.info("Skipping regional analysis: Not English (detected: %s).", detected_code)
            elif len(text) < self.MIN_LENGTH:
                logging.info("Skipping regional analysis due to short text length (< %d chars).", self.MIN_LENGTH)
            return None
            
        text_lower = text.lower()
        
        us_words = EnglishRegionalisms.REGIONAL_WORDS.get("US", set())
        gb_words = EnglishRegionalisms.REGIONAL_WORDS.get("GB", set())
        
        # Count occurrences of regional-specific words and multi-word phrases
        us_score = sum(text_lower.count(us_word) for us_word in us_words)
        gb_score = sum(text_lower.count(gb_word) for gb_word in gb_words)
        
        logging.info("Regional Analysis (English): US score = %d, GB score = %d", us_score, gb_score)

        # Determine regional bias based on the scores.
        # A threshold of 1.5 times more common is used to indicate a "strong" bias.
        if us_score > 0 and us_score >= gb_score * 1.5:
            logging.info("Strong regional bias detected: en-US.")
            return "en-US"
        elif gb_score > 0 and gb_score >= us_score * 1.5:
            logging.info("Strong regional bias detected: en-GB.")
            return "en-GB"
        else:
            logging.info("No strong regional bias detected, or scores are too close.")
            return None
  
class GoogleTTSVoiceSelector(TTSVoiceSelector):
    """
    A TTSVoiceSelector implementation that fetches, caches, and selects a
    Google Cloud TTS voice based on contextual factors.
    """
    GENERIC_TO_REGIONAL_MAP = {
        "en": ["en-US", "en-GB", "en-AU", "en-IN"],
        "fr": ["fr-FR", "fr-CA"],
        "de": ["de-DE"],
        "es": ["es-ES", "es-US", "es-MX"],
        "zh": ["zh-CN", "zh-TW", "zh-HK"],
    }
    # Stores the list of available Text-to-Speech voices to avoid repeated API calls.
    available_voices: List[Any] = []

    def get_available_voices(self, language_code: Optional[str] = None) -> List[Any]:
        """
        Fetches and caches the list of available Text-to-Speech voices from Google Cloud.

        Args:
            language_code (str, optional): A specific language code (e.g., "en-US", "fr")
                                        to filter the voices. If None, all available voices
                                        are returned. Defaults to None.

        Returns:
            List[Any]: A list of `texttospeech.Voice` objects matching the criteria.
        """
        # Fetch voices only if the cache is empty
        if not self.available_voices:
            try:
                client = texttospeech.TextToSpeechClient()
                response = client.list_voices()
                self.available_voices = response.voices
                logging.info("Fetched and cached %d available voices.", len(self.available_voices))
            except Exception as e:
                logging.error("Failed to fetch voices from Google Cloud: %s", e, exc_info=True)
                return []
        
        if not language_code:
            return self.available_voices
        
        codes_to_check = [language_code]
        # Logic for expanding language codes
        if len(language_code) == 2 and language_code in self.GENERIC_TO_REGIONAL_MAP:
            codes_to_check.extend(self.GENERIC_TO_REGIONAL_MAP[language_code])
        elif len(language_code) == 5 and language_code[:2] in self.GENERIC_TO_REGIONAL_MAP:
            if language_code[:2] not in codes_to_check:
                codes_to_check.append(language_code[:2])
        codes_to_check = list(set(codes_to_check))
        
        return [
            v for v in self.available_voices
            for voice_lang_code in v.language_codes
            if voice_lang_code in codes_to_check
        ]

    def get_contextual_voice_parameters(self, detected_language_code: str, sentiment_score: float, 
                                        categories: Optional[List[str]] = None, syntax_info: Optional[Dict[str, Any]] = None,
                                        user_gender_preference: Optional[texttospeech.SsmlVoiceGender] = None, regional_code_from_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Selects suitable Google Cloud Text-to-Speech voice parameters based on contextual factors.

        Args:
            detected_language_code (str): The primary language code detected.
            sentiment_score (float): The sentiment score of the text (-1.0 to 1.0).
            categories (Optional[List[str]], optional): A list of category names for the text. Defaults to None.
            syntax_info (Optional[Dict[str, Any]], optional): A dictionary of syntax complexity metrics. Defaults to None.
            user_gender_preference (Optional[texttospeech.SsmlVoiceGender], optional): User's preferred gender. Defaults to None.
            regional_code_from_text (Optional[str], optional): A more specific regional language code. Defaults to None.

        Returns:
            Dict[str, Any]: A dictionary of selected voice parameters.
        """
        categories = categories or []

        try:
            effective_language_search_code = regional_code_from_text if regional_code_from_text else detected_language_code
            voices_for_lang = self.get_available_voices(effective_language_search_code)

            if not voices_for_lang:
                if regional_code_from_text and regional_code_from_text != detected_language_code:
                    logging.info("No voices found for '%s'. Trying generic code '%s'.", regional_code_from_text, detected_language_code)
                    voices_for_lang = self.get_available_voices(detected_language_code)

                if not voices_for_lang:
                    logging.warning("Still no suitable voices found for '%s'. Falling back to hardcoded default.", detected_language_code)
                    return {
                        "name": "en-US-Wavenet-B",
                        "pitch": 0.0,
                        "speaking_rate": 1.0,
                        "language_code": "en-US",
                        "voice_gender": texttospeech.SsmlVoiceGender.NEUTRAL
                    }

            # Prioritize voices by quality
            voice_quality_order = ["Chirp", "Studio", "Neural2", "Wavenet", "Standard"]
            preferred_voices_list_order = []
            for voice_type in voice_quality_order:
                voice_list = [v for v in voices_for_lang if voice_type in v.name]
                if voice_list:
                    preferred_voices_list_order.append(voice_list)
            
            if not preferred_voices_list_order:
                preferred_voices_list_order.append(voices_for_lang)

            selected_voice = None
            pitch = 0.0
            speaking_rate = 1.0
            
            target_gender = user_gender_preference or texttospeech.SsmlVoiceGender.NEUTRAL
            
            # If no explicit user preference, infer gender based on sentiment and categories.
            if user_gender_preference is None:
                if sentiment_score > 0.5:
                    target_gender = texttospeech.SsmlVoiceGender.FEMALE
                elif sentiment_score < -0.5:
                    target_gender = texttospeech.SsmlVoiceGender.MALE
                
                if any("Romance" in c for c in categories):
                    target_gender = texttospeech.SsmlVoiceGender.FEMALE
                elif any(c in ["News", "Business & Industrial", "Science"] for c in categories):
                    target_gender = texttospeech.SsmlVoiceGender.NEUTRAL

            # Find a voice matching the target gender, with fallbacks
            for voice_type_list in preferred_voices_list_order:
                candidates_by_gender = [v for v in voice_type_list if v.ssml_gender == target_gender]
                if candidates_by_gender:
                    selected_voice = random.choice(candidates_by_gender)
                    break
            
            if selected_voice is None:
                for voice_type_list in preferred_voices_list_order:
                    neutral_candidates = [v for v in voice_type_list if v.ssml_gender == texttospeech.SsmlVoiceGender.NEUTRAL]
                    if neutral_candidates:
                        selected_voice = random.choice(neutral_candidates)
                        logging.info("Could not find a voice for preferred gender %s. Falling back to Neutral.", target_gender.name)
                        break
            
            if selected_voice is None:
                selected_voice = random.choice(preferred_voices_list_order[0])
                logging.info("Could not find a voice for preferred gender %s or Neutral. Falling back to any available voice (%s).", target_gender.name, selected_voice.name)

            # Adjust pitch and speaking rate based on context
            PITCH_SENSITIVITY = 4.0
            RATE_SENSITIVITY = 0.1

            if sentiment_score != 0.0:
                pitch += sentiment_score * PITCH_SENSITIVITY
                speaking_rate += sentiment_score * (RATE_SENSITIVITY / 2)

            for cat in categories:
                if "Science Fiction" in cat or "Fantasy" in cat:
                    pitch -= 1.0
                    speaking_rate *= 0.95
                elif "Romance" in cat:
                    pitch += 1.5
                    speaking_rate *= 1.03
                elif any(c in ["News", "Business & Industrial", "Education"] for c in [cat]):
                    pitch = 0.0
                    speaking_rate = 1.0
                elif "Poetry" in cat or "Literature" in cat:
                    pitch -= 0.5
                    speaking_rate *= 0.90
                elif "Mystery" in cat or "Thriller" in cat:
                    pitch -= 0.8
                    speaking_rate *= 0.97

            if syntax_info and syntax_info["num_sentences"] > 0:
                avg_tokens = syntax_info["avg_tokens_per_sentence"]
                num_complex_clauses = syntax_info["num_complex_clauses"]
                if avg_tokens > 20 or (syntax_info["num_sentences"] > 0 and num_complex_clauses / syntax_info["num_sentences"] > 0.3):
                    speaking_rate *= 0.90
                    pitch -= 0.5
                elif avg_tokens < 10:
                    speaking_rate *= 1.05

            pitch = max(-20.0, min(20.0, pitch))
            speaking_rate = max(0.25, min(4.0, speaking_rate))

            if "Chirp" in selected_voice.name or "Studio" in selected_voice.name:
                if pitch != 0.0 or speaking_rate != 1.0:
                    logging.info("Selected voice '%s' (Chirp/Studio) does not fully support pitch/speaking_rate adjustments. Setting to defaults.", selected_voice.name)
                    pitch = 0.0
                    speaking_rate = 1.0

            final_voice_language_code = selected_voice.language_codes[0]
            final_voice_gender = selected_voice.ssml_gender

            return {
                "name": selected_voice.name,
                "pitch": pitch,
                "speaking_rate": speaking_rate,
                "language_code": final_voice_language_code,
                "voice_gender": final_voice_gender
            }
        except Exception as e:
            logging.error("An error occurred during voice selection: %s", e, exc_info=True)
            # Hardcoded fallback on unexpected error
            return {
                "name": "en-US-Wavenet-B",
                "pitch": 0.0,
                "speaking_rate": 1.0,
                "language_code": "en-US",
                "voice_gender": texttospeech.SsmlVoiceGender.NEUTRAL
            }

class GoogleTTSSynthesizer(TTSSynthesizer):
    """
    An implementation of the TTSSynthesizer protocol that uses the Google Cloud
    Text-to-Speech API.

    This class includes robust retry logic with exponential backoff for handling
    transient API errors like rate limits and server unavailability.
    """
    # Proactive delay added before each API call to help prevent hitting rate limits.
    PROACTIVE_DELAY = 0.1

    def __init__(self, max_retries: int = 5, initial_delay: float = 1.0):
        """
        Initializes the synthesizer with configurable retry parameters.

        Args:
            max_retries (int, optional): Maximum number of times to retry an API call.
                                         Defaults to 5.
            initial_delay (float, optional): Initial delay in seconds before the first retry.
                                             Defaults to 1.0.
        """
        self.MAX_API_RETRIES = max_retries
        self.INITIAL_RETRY_DELAY = initial_delay


    def synthesize(self, text: str, voice_params: Dict[str, Any], output_filename: str, pitch: float = 0.0, speaking_rate: float = 1.0) -> bool:
        """
        Synthesizes speech from the input text using a specified Google Cloud TTS voice.

        Args:
            text (str): The text content to convert to speech.
            voice_params (Dict[str, Any]): A dictionary containing voice parameters
                                            (language_code, name, ssml_gender).
            output_filename (str): The path to save the generated audio file (MP3).
            pitch (float, optional): The speaking pitch of the voice, in semitones
                                    (from -20.0 to 20.0). Defaults to 0.0.
            speaking_rate (float, optional): The speaking rate relative to the normal
                                            speed (0.25 to 4.0). Defaults to 1.0.

        Returns:
            bool: True if speech synthesis was successful and the file was saved, False otherwise.
        """
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice_selection_params = texttospeech.VoiceSelectionParams(
            language_code=voice_params["language_code"],
            name=voice_params["name"],
            ssml_gender=voice_params["voice_gender"]
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            pitch=pitch,
            speaking_rate=speaking_rate
        )

        for attempt in range(self.MAX_API_RETRIES + 1):
            try:
                time.sleep(self.PROACTIVE_DELAY)
                response = client.synthesize_speech(
                    input=synthesis_input, voice=voice_selection_params, audio_config=audio_config
                )

                with open(output_filename, "wb") as out:
                    out.write(response.audio_content)
                logging.info("Audio chunk saved successfully to '%s'.", output_filename)
                return True

            except (ResourceExhausted, InternalServerError, ServiceUnavailable) as e:
                if attempt < self.MAX_API_RETRIES:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    logging.warning(
                        "Rate limit or server error for chunk. Retrying in %ss (Attempt %d/%d). Error: %s",
                        f"{delay:.2f}", attempt + 1, self.MAX_API_RETRIES, e
                    )
                    time.sleep(delay)
                else:
                    logging.error(
                        "Max retries reached for rate limit/server error on chunk. Failed to synthesize: '%s'. Error: %s",
                        output_filename, e
                    )
                    return False
            except Exception as e:
                logging.error(
                    "An unexpected error occurred during TTS synthesis for chunk '%s': %s",
                    output_filename, e, exc_info=True
                )
                return False
        return False

class UserPreference(UserPreferenceProvider):
    """
    An implementation of the UserPreferenceProvider protocol for retrieving
    user-defined TTS preferences via command-line input.
    """
    def get_gender_preference(self) -> Optional[texttospeech.SsmlVoiceGender]:
        """
        Prompts the user to select a preferred narrator gender for the synthesized speech.

        Returns:
            Optional[texttospeech.SsmlVoiceGender]: The selected SSML voice gender enum
                                                    (MALE, FEMALE, NEUTRAL) or None if the
                                                    user chooses automatic selection.
        """
        while True:
            gender_input = input(
                "Choose narrator gender (Male, Female, Neutral, or press Enter for automatic): "
            ).strip().lower()

            if gender_input == "male":
                return texttospeech.SsmlVoiceGender.MALE
            elif gender_input == "female":
                return texttospeech.SsmlVoiceGender.FEMALE
            elif gender_input == "neutral":
                return texttospeech.SsmlVoiceGender.NEUTRAL
            elif gender_input == "":
                return None
            else:
                logging.warning("Invalid input. Please type 'Male', 'Female', 'Neutral', or press Enter.")

class DefaultTextChunker(TextChunker):
    """
    An implementation of TextChunker that breaks text into chunks,
    prioritizing paragraph and then sentence integrity.
    """
    MAX_BYTES_PER_CHUNK = 5000
    MAX_BYTES_PER_SENTENCE = 900
    
    def _split_long_sentence(self, sentence: str) -> List[str]:
        """
        Splits a single sentence that is longer than the byte limit.
        First attempts to split at punctuation, then falls back to a brute-force split.
        """
        sentence_bytes = len(sentence.encode('utf-8'))
        if sentence_bytes <= self.MAX_BYTES_PER_SENTENCE:
            return [sentence]
        
        logging.warning(
            "Sentence is too long (%d bytes > %d). Attempting to split.",
            sentence_bytes, self.MAX_BYTES_PER_SENTENCE
        )
        
        parts = re.split(r'([,.?!])', sentence)
        sentence_parts = [''.join(parts[i:i+2]) for i in range(0, len(parts), 2)]
        
        if all(len(p.encode('utf-8')) <= self.MAX_BYTES_PER_SENTENCE for p in sentence_parts):
            return sentence_parts
            
        logging.warning("Punctuation splitting failed. Falling back to byte-level split.")
        
        chunks = []
        current_chunk = ""
        for word in sentence.split():
            if len((current_chunk + " " + word).encode('utf-8')) <= self.MAX_BYTES_PER_SENTENCE:
                current_chunk += " " + word
            else:
                chunks.append(current_chunk.strip())
                current_chunk = word
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

    def chunk(self, text: str) -> List[str]:
        """Breaks down a single string of text into a list of smaller text chunks."""
        ensure_nltk_resource('tokenizers/punkt')
        
        chunks = []
        paragraphs = text.split('\n\n')
        
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # Use NLTK to split the paragraph into sentences
            sentences = nltk.sent_tokenize(para)
            
            for sentence in sentences:
                sentence_parts = self._split_long_sentence(sentence)
                
                for s_part in sentence_parts:
                    # Check if the sentence part fits in the current chunk
                    # The `+ 1` accounts for the space between sentence parts
                    if len((current_chunk + " " + s_part).encode('utf-8')) > self.MAX_BYTES_PER_CHUNK:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = s_part
                        else:
                            # This should not be reachable with the current logic, but is a fail-safe
                            current_chunk = s_part
                    else:
                        if current_chunk:
                            current_chunk += " " + s_part
                        else:
                            current_chunk = s_part
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Final sanity check
        for i, chunk in enumerate(chunks):
            chunk_bytes = len(chunk.encode('utf-8'))
            if chunk_bytes > self.MAX_BYTES_PER_CHUNK:
                logging.error("Chunk %d exceeds max byte limit (%d bytes). This indicates a chunking error.", i, chunk_bytes)
                raise ChunkingError(f"Chunk {i} has exceeded the maximum byte limit.")
        
        return chunks


# --- NLTK resource helper ---

def ensure_nltk_resource(resource: str,
    download_if_missing: bool = True,
    quiet: bool = True
    ) -> bool:
    """
    Checks if the given NLTK resource is available and downloads it if missing.

    Args:
        resource (str): The resource path, e.g., 'tokenizers/punkt'.
        download_if_missing (bool, optional): Whether to download the resource if it is not found.
                                             Defaults to True.
        quiet (bool, optional): Whether to suppress download output. Defaults to True.

    Returns:
        bool: True if the resource is available (either found or successfully downloaded),
              False otherwise.
    """
    try:
        nltk.data.find(resource)
        logging.info("NLTK resource '%s' is available.", resource)
        return True
    except LookupError:
        if download_if_missing:
            try:
                logging.info("NLTK resource '%s' not found. Downloading...", resource)
                nltk.download(resource.split('/')[-1], quiet=quiet)
                logging.info("NLTK resource '%s' downloaded successfully.", resource)
                return True
            except Exception as e:
                logging.error("Failed to download NLTK resource '%s': %s", resource, e)
                return False
        else:
            logging.warning("NLTK resource '%s' not found, and download was not requested.", resource)
            return False
    except Exception as e:
        logging.error("An unexpected error occurred while checking for NLTK resource '%s': %s", resource, e)
        return False

# --- Utility Function for Memory Check ---
def warn_on_low_memory(threshold_percent: int = 10):
    """
    Checks the available system memory and logs a warning if it falls below a given threshold.

    Args:
        threshold_percent (int, optional): The low memory threshold as a percentage of total RAM.
                                           Defaults to 10.
    """
    if not PSUTIL_AVAILABLE:
        return
        
    try:
        virtual_memory = psutil.virtual_memory()
        available_percent = virtual_memory.available / virtual_memory.total * 100
        
        if available_percent < threshold_percent:
            logging.warning(
                "Low memory detected: Only %.2f%% of RAM is available. "
                "The script may crash with an out-of-memory error.", available_percent
            )
    except Exception as e:
        logging.debug("Could not check system memory. Error: %s", e)

# -- High-level Service ---

class AudioSynthesisService:
    """
    High-level service for analyzing text, selecting contextual voice parameters,
    chunking for TTS API, and synthesizing audio.
    """

    def __init__(
        self,
        language_analyzer: LanguageAnalyzer,
        voice_selector: TTSVoiceSelector,
        tts_synthesizer: TTSSynthesizer,
        user_pref_provider: UserPreferenceProvider,
        chunker: Optional[TextChunker] = None
    ) -> None:
        """
        Initializes the service with all its dependencies.
        
        Args:
            language_analyzer: An object that performs linguistic analysis.
            voice_selector: An object that selects voice parameters.
            tts_synthesizer: An object that synthesizes audio from text.
            user_pref_provider: An object that provides user preferences.
            chunker: An object to chunk the text. Defaults to a DefaultTextChunker.
        """
        self.language_analyzer = language_analyzer
        self.voice_selector = voice_selector
        self.tts_synthesizer = tts_synthesizer
        self.user_pref_provider = user_pref_provider
        self.chunker = chunker if chunker else DefaultTextChunker()

    def synthesize_audio(
        self,
        text: str,
        output_audio_path: str,
        temp_audio_dir: Optional[str] = None,
        user_gender_preference: Optional[texttospeech.SsmlVoiceGender] = None
    ) -> Optional[str]:
        """
        Chunk text, analyze, select TTS parameters, synthesize, and combine audio.

        Args:
            text (str): Text content to analyze and synthesize.
            output_audio_path (str): Path where the output audio file will be saved.
            temp_audio_dir (str, optional): Directory for intermediate audio chunks.
                                            Defaults to a sub-directory of the output path.
            user_gender_preference (Optional[texttospeech.SsmlVoiceGender], optional):
                                            User's preferred gender for the voice.
                                            Defaults to None for automatic selection.

        Returns:
            Optional[str]: Path to final audiobook MP3 if successful, else None.
        """
        logging.info("Starting audio synthesis pipeline.")

        try:
            chunks = self.chunker.chunk(text)
            if not chunks:
                logging.error("No text chunks generated for audiobook.")
                return None
            
            logging.info("Performing linguistic analysis on the full text...")
            lang_code = self.language_analyzer.analyze_language(text)
            sentiment_score, _ = self.language_analyzer.analyze_sentiment(text)
            categories = self.language_analyzer.analyze_category(text)
            syntax_info = self.language_analyzer.analyze_syntax_complexity(text)
            regional_code = self.language_analyzer.analyze_regional_context(text, lang_code)

            if user_gender_preference is None:
                user_gender_preference = self.user_pref_provider.get_gender_preference()

            logging.info("Selecting contextual voice parameters...")
            voice_params = self.voice_selector.get_contextual_voice_parameters(
                detected_language_code=lang_code,
                sentiment_score=sentiment_score,
                categories=categories,
                syntax_info=syntax_info,
                user_gender_preference=user_gender_preference,
                regional_code_from_text=regional_code,
            )

            if not temp_audio_dir:
                temp_audio_dir = os.path.join(os.path.dirname(output_audio_path), "temp_audio_chunks")
            os.makedirs(temp_audio_dir, exist_ok=True)
            logging.info("Temporary audio directory created at '%s'.", temp_audio_dir)

            combined_audio = AudioSegment.empty()
            
            for i, chunk in enumerate(chunks):
                warn_on_low_memory()

                if not chunk.strip():
                    continue
                temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
                
                logging.info("Synthesizing chunk %d of %d...", i + 1, len(chunks))
                success = self.tts_synthesizer.synthesize(
                    text=chunk,
                    voice_params=voice_params,
                    output_filename=temp_audio_file,
                    pitch=voice_params["pitch"],
                    speaking_rate=voice_params["speaking_rate"]
                )
                
                if success:
                    try:
                        segment = AudioSegment.from_mp3(temp_audio_file)
                        combined_audio += segment
                        logging.debug("Appended chunk %d to the combined audio.", i + 1)
                    except (CouldntDecodeError, FileNotFoundError) as e:
                        logging.error("Error loading chunk %d from '%s': %s", i, temp_audio_file, e)
                else:
                    logging.warning("Failed to synthesize chunk %d. Saving failed chunk to a text file for review.", i)
                    with open(os.path.join(temp_audio_dir, f"failed_chunk_{i:04d}.txt"), "w", encoding="utf-8") as err_f:
                        err_f.write(chunk)

            if combined_audio.duration_seconds == 0:
                logging.error("No audio segments were successfully generated for the audiobook. Exiting.")
                return None

            logging.info("Combining all audio segments into a single file...")
            combined_audio.export(output_audio_path, format="mp3")
            
            logging.info("Audiobook created successfully: '%s'", output_audio_path)
            
            logging.info("Cleaning up temporary audio files in '%s'.", temp_audio_dir)
            for file_name in os.listdir(temp_audio_dir):
                os.remove(os.path.join(temp_audio_dir, file_name))
            os.rmdir(temp_audio_dir)
            
            return output_audio_path
        
        except Exception as e:
            logging.error("An unexpected error occurred during audio synthesis: %s", e, exc_info=True)
            return None
        