# services/media_stream_handler.py
import asyncio
import websockets
import json
import base64
import audioop
import logging
from typing import Dict, Optional
from collections import deque
import numpy as np

class MediaStreamHandler:
    """Handle real-time audio streaming via Twilio Media Streams"""
    
    def __init__(self, voice_bot, speech_processor):
        self.voice_bot = voice_bot
        self.speech_processor = speech_processor
        self.active_streams = {}
        self.audio_buffers = {}
        self.processing_queues = {}
        
        # Audio processing settings
        self.sample_rate = 8000  # Twilio uses 8kHz
        self.chunk_duration_ms = 20  # Process every 20ms of audio
        self.silence_threshold_ms = 500  # Detect end of speech
        
    async def handle_media_stream(self, websocket, path):
        """WebSocket handler for Twilio Media Streams"""
        stream_sid = None
        call_sid = None
        
        try:
            async for message in websocket:
                data = json.loads(message)
                
                if data['event'] == 'start':
                    stream_sid = data['start']['streamSid']
                    call_sid = data['start']['callSid']
                    
                    # Initialize stream
                    await self._initialize_stream(stream_sid, call_sid, data['start'])
                    
                elif data['event'] == 'media':
                    # Process audio chunk in real-time
                    await self._process_audio_chunk(
                        stream_sid,
                        data['media']['payload'],
                        data['media']['timestamp']
                    )
                    
                elif data['event'] == 'stop':
                    await self._cleanup_stream(stream_sid)
                    
        except Exception as e:
            logging.error(f"Media stream error: {e}")
        finally:
            if stream_sid:
                await self._cleanup_stream(stream_sid)
    
    async def _initialize_stream(self, stream_sid: str, call_sid: str, start_data: Dict):
        """Initialize a new media stream"""
        self.active_streams[stream_sid] = {
            'call_sid': call_sid,
            'start_time': asyncio.get_event_loop().time(),
            'audio_buffer': deque(maxlen=500),  # ~10 seconds of audio
            'processing_task': None,
            'vad_state': {'speaking': False, 'silence_start': None}
        }
        
        # Start continuous processing task
        self.active_streams[stream_sid]['processing_task'] = asyncio.create_task(
            self._continuous_audio_processing(stream_sid)
        )
        
        logging.info(f"Initialized media stream: {stream_sid} for call: {call_sid}")
    
    async def _process_audio_chunk(self, stream_sid: str, payload: str, timestamp: str):
        """Process incoming audio chunk"""
        if stream_sid not in self.active_streams:
            return
        
        # Decode base64 audio (μ-law format from Twilio)
        audio_bytes = base64.b64decode(payload)
        
        # Convert μ-law to linear PCM for processing
        pcm_audio = audioop.ulaw2lin(audio_bytes, 2)
        
        # Add to buffer for processing
        self.active_streams[stream_sid]['audio_buffer'].append({
            'data': pcm_audio,
            'timestamp': timestamp
        })
    
    async def _continuous_audio_processing(self, stream_sid: str):
        """Continuously process audio with VAD and real-time transcription"""
        stream = self.active_streams[stream_sid]
        accumulated_audio = b''
        
        while stream_sid in self.active_streams:
            try:
                # Check for speech/silence
                if stream['audio_buffer']:
                    chunk = stream['audio_buffer'].popleft()
                    audio_data = chunk['data']
                    
                    # Simple VAD using energy threshold
                    is_speech = self._detect_speech(audio_data)
                    
                    if is_speech:
                        accumulated_audio += audio_data
                        stream['vad_state']['speaking'] = True
                        stream['vad_state']['silence_start'] = None
                    else:
                        if stream['vad_state']['speaking']:
                            # Started silence after speech
                            if not stream['vad_state']['silence_start']:
                                stream['vad_state']['silence_start'] = asyncio.get_event_loop().time()
                            elif (asyncio.get_event_loop().time() - stream['vad_state']['silence_start']) > 0.5:
                                # End of utterance detected
                                if accumulated_audio:
                                    await self._process_utterance(stream_sid, accumulated_audio)
                                    accumulated_audio = b''
                                stream['vad_state']['speaking'] = False
                
                await asyncio.sleep(0.01)  # Process every 10ms
                
            except Exception as e:
                logging.error(f"Audio processing error: {e}")
                await asyncio.sleep(0.1)
    
    def _detect_speech(self, audio_data: bytes, threshold: int = 500) -> bool:
        """Simple VAD using energy detection"""
        if not audio_data:
            return False
        
        # Calculate RMS energy
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        energy = np.sqrt(np.mean(audio_array**2))
        
        return energy > threshold
    
    async def _process_utterance(self, stream_sid: str, audio_data: bytes):
        """Process complete utterance in real-time"""
        stream = self.active_streams.get(stream_sid)
        if not stream:
            return
        
        call_sid = stream['call_sid']
        
        # Get call state
        call_state = self.voice_bot.active_calls.get(call_sid)
        if not call_state:
            return
        
        # Real-time transcription
        transcription = await self._transcribe_audio_streaming(audio_data)
        
        if transcription:
            # Process immediately with playbook
            response = await self._get_playbook_response(transcription, call_state)
            
            # Stream response back immediately
            await self._stream_response(stream_sid, response)
    
    async def _transcribe_audio_streaming(self, audio_data: bytes) -> Optional[str]:
        """Fast streaming transcription"""
        try:
            # Convert to format expected by Azure
            audio_stream = self._create_audio_stream(audio_data)
            
            result = await self.speech_processor.speech_to_text_from_stream(audio_stream)
            
            if result['success']:
                return result['text']
            
        except Exception as e:
            logging.error(f"Transcription error: {e}")
        
        return None
    
    async def _stream_response(self, stream_sid: str, response_text: str):
        """Stream TTS response back through media stream"""
        try:
            # Generate TTS
            tts_result = await self.speech_processor.text_to_speech_stream(response_text)
            
            if tts_result['success']:
                # Convert to μ-law for Twilio
                audio_data = tts_result['audio_data']
                ulaw_audio = audioop.lin2ulaw(audio_data, 2)
                
                # Send back through WebSocket
                await self._send_audio_to_stream(stream_sid, ulaw_audio)
                
        except Exception as e:
            logging.error(f"Response streaming error: {e}")
    
    async def _cleanup_stream(self, stream_sid: str):
        """Clean up stream resources"""
        if stream_sid in self.active_streams:
            if self.active_streams[stream_sid]['processing_task']:
                self.active_streams[stream_sid]['processing_task'].cancel()
            del self.active_streams[stream_sid]