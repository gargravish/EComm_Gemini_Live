import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Box, Paper, Typography, Button, CircularProgress, LinearProgress } from '@mui/material';
import io, { Socket } from 'socket.io-client';

interface Product {
  id: string;
  name: string;
  description?: string;
  image_url: string;
  price: string;
  aisle?: string;
}

interface Live2ChatProps {
  onSearchResults: (results: Product[]) => void;
}

interface ChatMessage {
  sender: 'User' | 'Gemini';
  text: string;
  timestamp: number;
  isComplete?: boolean;
  function_name?: string;
  results?: Product[];
}

const SOCKET_URL = 'http://localhost:5000';

const Live2Chat: React.FC<Live2ChatProps> = ({ onSearchResults }) => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [readyToStream, setReadyToStream] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const socketRef = useRef<Socket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioWorkletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletStartedRef = useRef(false);
  const videoFrameIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Clean up all resources
  const cleanup = useCallback(() => {
    if (socketRef.current) {
      if (sessionId) {
        socketRef.current.emit('end_live2_session', { session_id: sessionId });
      }
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    if (audioWorkletNodeRef.current) {
      audioWorkletNodeRef.current.disconnect();
      audioWorkletNodeRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    setIsStreaming(false);
    setAudioLevel(0);
    setSessionId(null);
    setReadyToStream(false);
    setSessionReady(false);
    workletStartedRef.current = false;
  }, [sessionId]);

  // Start socket and session, but NOT audio/video yet
  const startSession = async () => {
    setIsLoading(true);
    try {
      if (!socketRef.current) {
        const socket = io(`${SOCKET_URL}/live2`, { transports: ['websocket'] });
        socketRef.current = socket;
        socket.on('connect', () => {
          setIsStreaming(true);
          setIsLoading(false);
          setMessages([]);
          socket.emit('start_live2_session');
        });
        socket.on('live2_session_started', (data) => {
          setSessionId(data.session_id);
          setReadyToStream(true); // Only now allow audio to start (legacy)
        });
        socket.on('live2_session_ready', (data) => {
          if (data.session_id) {
            setSessionReady(true); // Only now allow video/audio streaming
          }
        });
        socket.on('live2_audio_ack', () => {});
        socket.on('live2_session_ended', () => {
          cleanup();
        });
        socket.on('status', (data) => {});
        socket.on('disconnect', () => {
          cleanup();
        });
        socket.on('error', (data) => {
          setIsStreaming(false);
          setIsLoading(false);
          alert('Live2 error: ' + (data?.message || 'Unknown error'));
        });
        socket.on('live2_message', (data) => {
          if (data.function_name && data.results) {
            onSearchResults(data.results);
          }
          if (data.text) {
            setMessages((prev) => [
              ...prev,
              {
                sender: data.sender || 'Gemini',
                text: data.text,
                timestamp: Date.now(),
                isComplete: data.isComplete,
                function_name: data.function_name,
                results: data.results
              },
            ]);
          }
        });
        socket.on('live2_audio', (data) => {
          // Optionally play audio response
        });
      }
    } catch (err) {
      setIsLoading(false);
      setIsStreaming(false);
      alert('Could not start Live2 session: ' + err);
    }
  };

  // Start audio worklet and streaming ONLY after session is ready
  const startAudioStreaming = useCallback(async () => {
    if (!sessionReady || workletStartedRef.current) return;
    workletStartedRef.current = true;
    try {
      // Only request audio by default
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      // Do NOT set videoRef.current.srcObject here
      const audioContext = new window.AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      await audioContext.audioWorklet.addModule('/worklets/audio-processor.js');
      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor', {
        processorOptions: { sampleRate: 16000, bufferSize: 4096 },
      });
      audioWorkletNodeRef.current = workletNode;
      source.connect(workletNode);
      workletNode.connect(audioContext.destination);
      workletNode.port.onmessage = (event) => {
        const { pcmData, level } = event.data;
        setAudioLevel(level);
        if (pcmData) {
          console.log('[Live2] Audio worklet output:', pcmData?.byteLength || pcmData?.length, 'bytes');
        }
        // Log all conditions
        console.log('[Live2] Emit check:', {
          socketConnected: !!(socketRef.current && socketRef.current.connected),
          sessionId,
          pcmData: !!pcmData
        });
        if (
          socketRef.current &&
          socketRef.current.connected &&
          sessionId &&
          pcmData
        ) {
          const b64 = btoa(String.fromCharCode(...new Uint8Array(pcmData)));
          console.log('[Live2] Emitting audio_chunk:', {
            session_id: sessionId,
            pcm_length: pcmData?.byteLength || pcmData?.length,
            b64_length: b64.length
          });
          socketRef.current.emit('audio_chunk', { session_id: sessionId, audio: b64 });
        }
      };
    } catch (err) {
      setIsLoading(false);
      setIsStreaming(false);
      alert('Could not start audio: ' + err);
    }
  }, [sessionReady, sessionId]);

  // Start audio streaming when ready
  useEffect(() => {
    if (sessionReady && sessionId) {
      startAudioStreaming();
    }
  }, [sessionReady, sessionId, startAudioStreaming]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
    // eslint-disable-next-line
  }, []);

  // --- Video frame capture and streaming (modular, ADA-style) ---
  // Helper: capture a frame from the video element, encode as JPEG, and send to backend
  const sendVideoFrame = useCallback(() => {
    console.log('sendVideoFrame called');
    if (!videoRef.current || !socketRef.current || !sessionId) return;
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const reader = new FileReader();
      reader.onloadend = () => {
        const dataUrl = reader.result as string; // Full data URL (e.g., 'data:image/jpeg;base64,...')
        // --- Debug log for emission ---
        console.log('[Live2] Emitting video_frame', { sessionId, dataUrlLength: dataUrl.length });
        try {
          socketRef.current!.emit('video_frame', { session_id: sessionId, frame: dataUrl });
        } catch (err) {
          console.error('[Live2] Error emitting video_frame:', err);
        }
      };
      reader.readAsDataURL(blob);
    }, 'image/jpeg', 0.8);
  }, [sessionId]);

  // Handler to enable video feed on demand and start frame streaming
  const enableVideoFeed = async () => {
    console.log('enableVideoFeed called');
    if (!sessionReady) {
      alert('Session not ready for video. Please wait...');
      return;
    }
    try {
      const videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
      console.log('getUserMedia resolved, videoStream:', videoStream);
      if (videoRef.current) {
        videoRef.current.srcObject = videoStream;
        console.log('[Live2] Video stream started');
      }
      // Start periodic frame capture and streaming (e.g., 5 FPS)
      if (videoFrameIntervalRef.current) clearInterval(videoFrameIntervalRef.current);
      videoFrameIntervalRef.current = setInterval(() => {
        console.log('Interval running, about to send frame');
        sendVideoFrame();
      }, 200);
      console.log('setInterval for sendVideoFrame set');
    } catch (err) {
      alert('Could not start video: ' + err);
      console.error('[Live2] Could not start video:', err);
    }
  };

  // Cleanup video frame interval on unmount or stop
  useEffect(() => {
    return () => {
      if (videoFrameIntervalRef.current) clearInterval(videoFrameIntervalRef.current);
    };
  }, []);

  // --- User feedback for connection, errors, and streaming state ---
  // (Add more detailed feedback as needed for testability)
  useEffect(() => {
    if (!isStreaming && !isLoading && !sessionId) {
      // Optionally show a message or toast: "Session stopped or not started"
    }
  }, [isStreaming, isLoading, sessionId]);

  // --- Comments for testability and modularity ---
  // All streaming logic is modular and isolated to Live2 mode.
  // Video streaming is stubbed for future extension and does not affect audio or other chat modes.
  // All error handling is user-friendly and testable.

  return (
    <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
        <Typography variant="h6" color="primary" gutterBottom>
          Live2 Mode (VAD + Camera + Audio)
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <Button
            variant="contained"
            color="primary"
            onClick={startSession}
            disabled={isStreaming || isLoading}
          >
            {isLoading ? <CircularProgress size={24} /> : 'Start Live2 Session'}
          </Button>
          <Button
            variant="outlined"
            onClick={enableVideoFeed}
            disabled={!isStreaming}
          >
            Enable Video Feed
          </Button>
          <Button variant="outlined" color="error" onClick={cleanup}>
            Stop Session
          </Button>
        </Box>
        <Box sx={{ width: '100%', maxWidth: 400, mb: 2 }}>
          <video ref={videoRef} autoPlay playsInline style={{ width: 320, height: 240, display: 'block', marginBottom: 16 }} />
        </Box>
        <Box sx={{ width: '100%', maxWidth: 400, mb: 2 }}>
          <Typography variant="caption">Audio Level</Typography>
          <LinearProgress variant="determinate" value={audioLevel} sx={{ height: 8, borderRadius: 4 }} />
        </Box>
        <Box sx={{ width: '100%', maxWidth: 400, mt: 2, bgcolor: '#f5f5f5', borderRadius: 2, p: 2, minHeight: 120 }}>
          <Typography variant="subtitle2" color="text.secondary">Chat</Typography>
          {messages.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No messages yet.</Typography>
          ) : (
            messages.map((msg, idx) => (
              <Box key={idx} sx={{ my: 1, textAlign: msg.sender === 'User' ? 'right' : 'left' }}>
                <Typography variant="body2" color={msg.sender === 'User' ? 'primary' : 'secondary'}>
                  <b>{msg.sender}:</b> {msg.text}
                </Typography>
                {msg.function_name && msg.results && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" color="secondary">Function: {msg.function_name}</Typography>
                    <pre style={{ fontSize: 12, background: '#eee', borderRadius: 4, padding: 4 }}>{JSON.stringify(msg.results, null, 2)}</pre>
                  </Box>
                )}
              </Box>
            ))
          )}
        </Box>
      </Box>
    </Paper>
  );
};

export default Live2Chat; 