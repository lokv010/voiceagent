import azure.cognitiveservices.speech as speechsdk
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
import asyncio
import logging
from typing import Dict, Optional

class AzureSpeechProcessor:
    def __init__(self, speech_key: str, speech_region: str, text_analytics_key: str = None, text_analytics_endpoint: str = None):
        """Initialize Azure Speech Services"""
        self.speech_key = speech_key
        self.speech_region = speech_region
        
        # Speech-to-Text configuration
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, 
            region=speech_region
        )
        self.speech_config.speech_recognition_language = "en-US"
        self.speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, 
            "3000"
        )
        # Enable detailed recognition results
        self.speech_config.output_format = speechsdk.OutputFormat.Detailed
        
        # Text-to-Speech configuration
        self.tts_config = speechsdk.SpeechConfig(
            subscription=speech_key, 
            region=speech_region
        )
        # Use high-quality neural voice
        self.tts_config.speech_synthesis_voice_name = "en-US-AriaNeural"
        
        # Text Analytics client (if credentials provided)
        self.text_analytics_client = None
        if text_analytics_key and text_analytics_endpoint:
            self.text_analytics_client = TextAnalyticsClient(
                endpoint=text_analytics_endpoint,
                credential=AzureKeyCredential(text_analytics_key)
            )
        
        logging.info("Azure Speech Services initialized successfully")
    
    async def speech_to_text_from_stream(self, audio_stream) -> Dict:
        """Convert speech to text from audio stream"""
        try:
            # Create audio configuration from stream
            audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)
            
            # Create speech recognizer
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )
            
            # Set up event handlers for better control
            recognition_result = None
            recognition_done = asyncio.Event()
            
            def handle_result(evt):
                nonlocal recognition_result
                recognition_result = evt.result
                recognition_done.set()
            
            speech_recognizer.recognized.connect(handle_result)
            speech_recognizer.canceled.connect(handle_result)
            
            # Start recognition
            speech_recognizer.start_continuous_recognition()
            
            # Wait for result or timeout
            try:
                await asyncio.wait_for(recognition_done.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                speech_recognizer.stop_continuous_recognition()
                return {
                    'success': False,
                    'error': 'Recognition timeout',
                    'text': '',
                    'confidence': 0.0
                }
            
            speech_recognizer.stop_continuous_recognition()
            
            if recognition_result and recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # Extract confidence from detailed results
                confidence = 0.9  # Default confidence
                if hasattr(recognition_result, 'best'):
                    confidence = recognition_result.best[0].confidence if recognition_result.best else 0.9
                
                return {
                    'success': True,
                    'text': recognition_result.text,
                    'confidence': confidence
                }
            elif recognition_result and recognition_result.reason == speechsdk.ResultReason.NoMatch:
                return {
                    'success': False,
                    'error': 'No speech could be recognized',
                    'text': '',
                    'confidence': 0.0
                }
            else:
                error_details = recognition_result.cancellation_details.error_details if recognition_result else "Unknown error"
                return {
                    'success': False,
                    'error': f'Speech recognition failed: {error_details}',
                    'text': '',
                    'confidence': 0.0
                }
                
        except Exception as e:
            logging.error(f"Speech-to-text error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0.0
            }
    
    async def text_to_speech_stream(self, text: str) -> Dict:
        """Convert text to speech and return audio stream"""
        try:
            # Create speech synthesizer
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.tts_config,
                audio_config=None  # Get audio data directly
            )
            
            # Use SSML for better control
            ssml_text = f"""
            <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
                <voice name='en-US-AriaNeural'>
                    <prosody rate='0.9' pitch='medium'>
                        {text}
                    </prosody>
                </voice>
            </speak>
            """
            
            # Synthesize speech
            result = speech_synthesizer.speak_ssml_async(ssml_text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return {
                    'success': True,
                    'audio_data': result.audio_data,
                    'audio_length': len(result.audio_data),
                    'audio_format': 'wav'
                }
            else:
                cancellation_details = result.cancellation_details
                return {
                    'success': False,
                    'error': f'Speech synthesis failed: {cancellation_details.reason}',
                    'audio_data': None
                }
                
        except Exception as e:
            logging.error(f"Text-to-speech error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'audio_data': None
            }
    
    async def analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment using Azure Text Analytics"""
        try:
            if not self.text_analytics_client:
                # Fallback sentiment analysis
                return self._simple_sentiment_analysis(text)
            
            documents = [text]
            response = self.text_analytics_client.analyze_sentiment(
                documents=documents,
                language="en"
            )
            
            result = response[0]
            
            return {
                'sentiment': result.sentiment,
                'confidence_scores': {
                    'positive': result.confidence_scores.positive,
                    'neutral': result.confidence_scores.neutral,
                    'negative': result.confidence_scores.negative
                },
                'overall_score': result.confidence_scores.positive - result.confidence_scores.negative,
                'mixed': result.sentiment == 'mixed'
            }
            
        except Exception as e:
            logging.error(f"Sentiment analysis error: {str(e)}")
            return self._simple_sentiment_analysis(text)
    
    def _simple_sentiment_analysis(self, text: str) -> Dict:
        """Simple fallback sentiment analysis"""
        positive_words = ['good', 'great', 'excellent', 'interested', 'yes', 'perfect', 'amazing']
        negative_words = ['bad', 'terrible', 'no', 'not interested', 'busy', 'stop']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = 'positive'
            confidence = 0.7
        elif negative_count > positive_count:
            sentiment = 'negative'
            confidence = 0.7
        else:
            sentiment = 'neutral'
            confidence = 0.5
        
        return {
            'sentiment': sentiment,
            'confidence_scores': {
                'positive': confidence if sentiment == 'positive' else 0.3,
                'neutral': 0.5,
                'negative': confidence if sentiment == 'negative' else 0.3
            },
            'overall_score': confidence if sentiment == 'positive' else -confidence if sentiment == 'negative' else 0.0,
            'mixed': False
        }
    
    async def detect_language(self, text: str) -> Dict:
        """Detect language of the text"""
        try:
            if not self.text_analytics_client:
                return {'language': 'en', 'confidence': 0.9}
            
            documents = [text]
            response = self.text_analytics_client.detect_language(documents=documents)
            
            result = response[0]
            primary_language = result.primary_language
            
            return {
                'language': primary_language.iso6391_name,
                'confidence': primary_language.confidence_score,
                'name': primary_language.name
            }
            
        except Exception as e:
            logging.error(f"Language detection error: {str(e)}")
            return {'language': 'en', 'confidence': 0.9}
        
    
    def synthesize_to_file(self, text, filename):
        audio_config = speechsdk.AudioConfig(filename=filename)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.tts_config, audio_config=audio_config)

        result = synthesizer.speak_text_async(text).get()
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            raise Exception(f"Synthesis failed: {result.reason}")
        return filename