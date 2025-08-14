# services/webrtc_handler.py
import asyncio
import json
from typing import Dict, Optional
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
import logging

class WebRTCAudioHandler:
    """Handle WebRTC connections for browser-based calls"""
    
    def __init__(self, voice_bot):
        self.voice_bot = voice_bot
        self.connections = {}
        self.audio_processors = {}
        
    async def create_offer(self, call_id: str) -> Dict:
        """Create WebRTC offer for browser"""
        pc = RTCPeerConnection()
        self.connections[call_id] = pc
        
        # Add audio track
        audio_track = AudioTransformTrack(self.voice_bot)
        pc.addTrack(audio_track)
        self.audio_processors[call_id] = audio_track
        
        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
            "call_id": call_id
        }
    
    async def handle_answer(self, call_id: str, answer: Dict):
        """Handle WebRTC answer from browser"""
        pc = self.connections.get(call_id)
        if not pc:
            return {"error": "Connection not found"}
        
        answer_sdp = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
        await pc.setRemoteDescription(answer_sdp)
        
        return {"status": "connected"}
    
    async def process_audio_frame(self, call_id: str, frame):
        """Process audio frame in real-time"""
        processor = self.audio_processors.get(call_id)
        if not processor:
            return
        
        # Process with VAD
        if processor.is_speech(frame):
            processor.add_to_buffer(frame)
        else:
            if processor.has_complete_utterance():
                # Process utterance
                audio_data = processor.get_utterance()
                response = await self._process_with_playbook(call_id, audio_data)
                
                # Send response back
                await processor.send_response(response)

class AudioTransformTrack(MediaStreamTrack):
    """Transform audio track for real-time processing"""
    
    kind = "audio"
    
    def __init__(self, voice_bot):
        super().__init__()
        self.voice_bot = voice_bot
        self.buffer = []
        self.vad_state = {'speaking': False, 'silence_frames': 0}
        
    async def recv(self):
        """Receive and process audio frame"""
        # This gets called for each audio frame
        frame = await self.get_next_frame()
        
        # Process frame for speech
        processed_frame = await self.process_frame(frame)
        
        return processed_frame
    
    def is_speech(self, frame) -> bool:
        """Check if frame contains speech"""
        # Simple energy-based VAD
        energy = self.calculate_energy(frame)
        return energy > self.energy_threshold