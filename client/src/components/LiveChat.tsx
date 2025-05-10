import { useState, useEffect, useRef, useCallback } from 'react';
import { Box, TextField, Button, Typography, Paper, CircularProgress } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import MicIcon from '@mui/icons-material/Mic';
import Tooltip from '@mui/material/Tooltip';
import ReactMarkdown from 'react-markdown';
import io, { Socket } from 'socket.io-client';
import VideoStream from './VideoStream';
import type { VideoStreamHandle } from './VideoStream';
import StreamControls from './StreamControls';

// Define message type
interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isComplete?: boolean;
}

// Define props interface
interface LiveChatProps {
  onSearchResults: (results: any[]) => void;
}

const LiveChat = ({ onSearchResults }: LiveChatProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 3;
  const [videoEnabled, setVideoEnabled] = useState(false);
  const recognitionRef = useRef<any>(null);
  const [isRecognizing, setIsRecognizing] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const shouldResumeAfterAudioRef = useRef(false);
  const [isMuted, setIsMuted] = useState(false);

  // Track if recognition should be running
  const recognizingRef = useRef(false);

  const videoStreamRef = useRef<VideoStreamHandle>(null);

  // --- Streaming audio playback (modular, ADA-style) ---
  const audioChunksRef = useRef<Uint8Array[]>([]);
  const [isStreamingAudio, setIsStreamingAudio] = useState(false);

  // Ref to store the current TTS Audio object
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  const [isTTSPlaying, setIsTTSPlaying] = useState(false);

  // Ref to track if TTS is playing (prevents mic auto-restart during TTS)
  const isTTSPlayingRef = useRef(false);

  // Ref to track latest isMuted state
  const isMutedRef = useRef(isMuted);
  useEffect(() => { isMutedRef.current = isMuted; }, [isMuted]);

  // Ref to track if recognition should be restarted after TTS (robust pattern)
  const shouldRestartAfterTTS = useRef(false);

  // Ref for delayed recognition restart after TTS
  const restartTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleVideoChange = useCallback((enabled: boolean) => {
    setVideoEnabled(enabled);
  }, []);

  useEffect(() => {
    // Initialize socket connection
    const initializeSocket = () => {
      if (socketRef.current?.connected) return;

      const socket = io('http://localhost:5000', {
        transports: ['websocket'],
        reconnection: true,
        reconnectionAttempts: maxReconnectAttempts,
        reconnectionDelay: 1000,
      });

      socket.on('connect', () => {
        console.log('Socket connected');
        setIsConnected(true);
        reconnectAttempts.current = 0;
        socket.emit('start_session');
      });

      socket.on('disconnect', () => {
        console.log('Socket disconnected');
        setIsConnected(false);
        setSessionId(null);
      });

      socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        setIsConnected(false);
        reconnectAttempts.current++;
        
        if (reconnectAttempts.current >= maxReconnectAttempts) {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: '⚠️ Connection lost. Please refresh the page.',
            timestamp: new Date(),
            isComplete: true
          }]);
        }
      });

      socket.on('session_created', (data) => {
        console.log('Session created:', data.session_id);
        setSessionId(data.session_id);
      });

      socket.on('error', (data) => {
        console.error('Socket error:', data);
        let errorMessage = 'An error occurred. Please try again.';
        
        switch (data.error) {
          case 'session_not_found':
            errorMessage = 'Session not found. Please refresh the page.';
            break;
          case 'connection_error':
            errorMessage = 'Connection error. Please check your internet connection.';
            break;
          default:
            errorMessage = data.error || 'An error occurred. Please try again.';
        }

        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `⚠️ **${errorMessage}**`,
          timestamp: new Date(),
          isComplete: true
        }]);
      });

      socket.on('response_chunk', (data) => {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'assistant' && !last.isComplete) {
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                content: last.content + (data.text || ''),
              }
            ];
          }
          return [
            ...prev,
            {
              role: 'assistant',
              content: data.text || '',
              timestamp: new Date(),
              isComplete: false
            }
          ];
        });
      });

      socket.on('response_complete', (data) => {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'assistant' && !last.isComplete) {
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                content: data.text || last.content,
                isComplete: true
              }
            ];
          }
          return [
            ...prev,
            {
              role: 'assistant',
              content: data.text || '',
              timestamp: new Date(),
              isComplete: true
            }
          ];
        });
        setIsLoading(false);
      });

      // Listen for function_result event for product search results
      socket.on('function_result', (data) => {
        if (data.function_name === 'search_products' && data.results) {
          onSearchResults(data.results);
          setIsLoading(false);
        }
      });

      socket.on('receive_audio_chunk', (data) => {
        if (data.audio) {
          const audioData = atob(data.audio);
          const arrayBuffer = new Uint8Array(audioData.length);
          for (let i = 0; i < audioData.length; i++) {
            arrayBuffer[i] = audioData.charCodeAt(i);
          }
          audioChunksRef.current.push(arrayBuffer);
          setIsStreamingAudio(true);
        }
      });

      socket.on('audio_stream_end', () => {
        if (audioChunksRef.current.length > 0) {
          const totalLength = audioChunksRef.current.reduce((acc, arr) => acc + arr.length, 0);
          const merged = new Uint8Array(totalLength);
          let offset = 0;
          for (const chunk of audioChunksRef.current) {
            merged.set(chunk, offset);
            offset += chunk.length;
          }
          const blob = new Blob([merged], { type: 'audio/mp3' });
          const url = URL.createObjectURL(blob);
          setAudioUrl(url);
          // Stop any previous TTS
          if (ttsAudioRef.current) {
            ttsAudioRef.current.pause();
            ttsAudioRef.current.currentTime = 0;
            ttsAudioRef.current = null;
          }
          const audio = new Audio(url);
          ttsAudioRef.current = audio;
          isTTSPlayingRef.current = true;
          setIsTTSPlaying(true);
          console.log('[TTS] Started playback');
          audio.onended = () => {
            isTTSPlayingRef.current = false;
            setIsTTSPlaying(false);
            ttsAudioRef.current = null;
            console.log('[TTS] Playback ended');
            // Robust: After TTS, set flag and stop recognition, restart in onend
            if (!isMutedRef.current && recognitionRef.current) {
              shouldRestartAfterTTS.current = true;
              try { recognitionRef.current.stop(); } catch (e) {}
              console.log('[MIC] Will restart after TTS via onend');
            }
          };
          audio.play();
        } else {
          setIsStreamingAudio(false);
        }
        audioChunksRef.current = [];
      });

      socketRef.current = socket;
    };

    initializeSocket();

    // Cleanup function
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [onSearchResults]);

  useEffect(() => {
    // Check for browser support
    if (!('webkitSpeechRecognition' in window)) {
      setSpeechSupported(false);
    }
  }, []);

  // Clean up audio URL
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const handleToggleSpeech = () => {
    if (!('webkitSpeechRecognition' in window)) {
      setSpeechSupported(false);
      return;
    }
    if (!recognitionRef.current) {
      const SpeechRecognition = (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = 'en-US';
      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[event.results.length - 1][0].transcript.trim();
        if (transcript) {
          setInput('');
          setMessages(prev => [...prev, {
            role: 'user',
            content: transcript,
            timestamp: new Date()
          }]);
          setIsLoading(true);
          if (socketRef.current && isConnected && sessionId) {
            socketRef.current.emit('send_message', { session_id: sessionId, message: transcript });
          }
        }
      };
      recognitionRef.current.onerror = (event: any) => {
        setIsRecognizing(false);
        recognizingRef.current = false;
      };
      recognitionRef.current.onend = () => {
        if (recognizingRef.current) {
          recognitionRef.current.start(); // Restart for persistent listening
        } else {
          setIsRecognizing(false);
        }
      };
    }
    if (!isRecognizing) {
      recognizingRef.current = true;
      setIsRecognizing(true);
      recognitionRef.current.start();
    } else {
      recognizingRef.current = false;
      setIsRecognizing(false);
      recognitionRef.current.stop();
    }
  };

  // Play TTS audio when received in response_complete
  useEffect(() => {
    if (!socketRef.current) return;
    const socket = socketRef.current;
    const handleResponseComplete = (data: any) => {
      if (data.audio) {
        // If listening, pause recognition before playing audio
        if (isRecognizing && recognitionRef.current) {
          recognizingRef.current = false;
          setIsRecognizing(false);
          recognitionRef.current.stop();
          shouldResumeAfterAudioRef.current = true;
        } else {
          shouldResumeAfterAudioRef.current = false;
        }
        const audioData = atob(data.audio);
        const arrayBuffer = new Uint8Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
          arrayBuffer[i] = audioData.charCodeAt(i);
        }
        const blob = new Blob([arrayBuffer], { type: 'audio/mp3' });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        // Stop any previous TTS
        if (ttsAudioRef.current) {
          ttsAudioRef.current.pause();
          ttsAudioRef.current.currentTime = 0;
          ttsAudioRef.current = null;
        }
        const audio = new Audio(url);
        ttsAudioRef.current = audio;
        isTTSPlayingRef.current = true;
        setIsTTSPlaying(true);
        console.log('[TTS] Started playback');
        audio.onended = () => {
          isTTSPlayingRef.current = false;
          setIsTTSPlaying(false);
          ttsAudioRef.current = null;
          console.log('[TTS] Playback ended');
          // Robust: After TTS, set flag and stop recognition, restart in onend
          if (!isMutedRef.current && recognitionRef.current) {
            shouldRestartAfterTTS.current = true;
            try { recognitionRef.current.stop(); } catch (e) {}
            console.log('[MIC] Will restart after TTS via onend');
          }
        };
        audio.play();
      }
    };
    socket.on('response_complete', handleResponseComplete);
    return () => {
      socket.off('response_complete', handleResponseComplete);
    };
  }, [socketRef, isConnected, isRecognizing]);

  // Handler to stop TTS playback
  const handleStopTTS = () => {
    if (ttsAudioRef.current) {
      console.log('[TTS] Stop Voice pressed, pausing audio');
      ttsAudioRef.current.pause();
      ttsAudioRef.current.currentTime = 0;
      ttsAudioRef.current = null;
      setIsTTSPlaying(false);
    } else {
      console.log('[TTS] Stop Voice pressed, but no audio to stop');
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading || !isConnected || !sessionId) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    let frame: string | null = null;
    if (videoEnabled && videoStreamRef.current) {
      frame = await videoStreamRef.current.getLatestFrame();
    }
    // Only include frame if videoEnabled and frame is available
    if (socketRef.current) {
      if (videoEnabled && frame) {
        socketRef.current.emit('send_message', { session_id: sessionId, message: input, frame });
      } else {
        socketRef.current.emit('send_message', { session_id: sessionId, message: input });
      }
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  // Patch: Prevent auto-restart of recognition during TTS (with robust restart after TTS)
  useEffect(() => {
    if (!recognitionRef.current) return;
    const recognition = recognitionRef.current;
    const originalOnEnd = recognition.onend;
    recognition.onend = function (...args: any[]) {
      // Robust: If TTS just ended, restart recognition now (with delay)
      if (shouldRestartAfterTTS.current) {
        shouldRestartAfterTTS.current = false;
        if (restartTimer.current) clearTimeout(restartTimer.current);
        restartTimer.current = setTimeout(() => {
          try {
            recognition.start();
            recognizingRef.current = true;
            setIsRecognizing(true);
            console.log('[MIC] Enabled (after TTS ended, via onend, delayed)');
          } catch (e) {
            console.warn('[MIC] Error starting recognition (via onend, delayed):', e);
          }
        }, 300); // 300ms delay
      } else if (!isTTSPlayingRef.current && recognizingRef.current) {
        try {
          recognition.start();
          setIsRecognizing(true);
          console.log('[MIC] Enabled (auto-restart after recognition end)');
        } catch (e) {
          console.warn('Could not auto-restart recognition:', e);
        }
      } else {
        console.log('[MIC] Not enabled: TTS still playing (auto-restart blocked)');
      }
      if (originalOnEnd) originalOnEnd.apply(this, args);
    };
    return () => {
      if (restartTimer.current) clearTimeout(restartTimer.current);
      // Restore original handler on cleanup
      if (recognition) recognition.onend = originalOnEnd;
    };
  }, [recognitionRef]);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Stream controls and Stop Voice button in one row */}
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'stretch', mb: 1, gap: 1 }}>
        <StreamControls onVideoChange={handleVideoChange} />
        <Button
          variant="outlined"
          color="secondary"
          onClick={handleStopTTS}
          fullWidth
        >
          Stop Voice
        </Button>
      </Box>
      {/* Video preview if enabled */}
      {videoEnabled && socketRef.current && sessionId && (
        <VideoStream ref={videoStreamRef} enabled={videoEnabled} />
      )}
      {/* Existing chat UI */}
      <Box sx={{ 
        height: '300px', 
        overflowY: 'auto', 
        mb: 2, 
        p: 1,
        border: '1px solid #e0e0e0',
        borderRadius: 1,
        bgcolor: '#f5f5f5'
      }}>
        {messages.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Typography variant="body1" color="text.secondary">
              {!isConnected ? 'Connecting to chat server...' : 'Ask me about products or how I can help you shop at RavMart!'}
            </Typography>
          </Box>
        ) : (
          messages.map((message, index) => (
            <Box 
              key={index} 
              sx={{ 
                mb: 2, 
                display: 'flex',
                flexDirection: 'column',
                alignItems: message.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <Paper 
                elevation={1} 
                sx={{ 
                  p: 2, 
                  maxWidth: '80%',
                  bgcolor: message.role === 'user' ? 'primary.light' : 'white',
                  color: message.role === 'user' ? 'white' : 'text.primary'
                }}
              >
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </Paper>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                {message.timestamp.toLocaleTimeString()}
              </Typography>
            </Box>
          ))
        )}
        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
            <CircularProgress size={24} />
          </Box>
        )}
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Tooltip title={speechSupported ? (isRecognizing ? 'Listening... (click to stop)' : 'Speak your message (click to start)') : 'Speech recognition not supported in this browser.'}>
          <span>
            <Button
              variant="outlined"
              color={isRecognizing ? 'error' : 'primary'}
              onClick={handleToggleSpeech}
              disabled={isLoading || !isConnected || !sessionId || !speechSupported}
              sx={{ mr: 1, minWidth: 0, padding: '8px' }}
            >
              <MicIcon />
            </Button>
          </span>
        </Tooltip>
        {/* Optionally show a listening indicator */}
        {isRecognizing && <Typography variant="caption" color="error" sx={{ mr: 1 }}>Listening...</Typography>}
        <TextField
          fullWidth
          variant="outlined"
          placeholder={!isConnected ? "Connecting..." : "Ask about products or how I can help..."}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isLoading || !isConnected || !sessionId}
          multiline
          maxRows={3}
          sx={{ mr: 1 }}
        />
        <Button
          variant="contained"
          color="primary"
          endIcon={<SendIcon />}
          onClick={handleSendMessage}
          disabled={!input.trim() || isLoading || !isConnected || !sessionId}
        >
          Send
        </Button>
      </Box>
    </Box>
  );
};

export default LiveChat;
