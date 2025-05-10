import { useState } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  TextField, 
  Button, 
  Select, 
  MenuItem, 
  FormControl, 
  InputLabel,
  Divider,
  CircularProgress
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import ReactMarkdown from 'react-markdown';
import LiveChat from './LiveChat';
import Live2Chat from './Live2Chat';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface Product {
  id: string;
  name: string;
  description?: string;
  image_url: string;
  price: string;
  aisle?: string;
}

interface RavMartAssistantProps {
  onSearchResults: (results: Product[]) => void;
}

const RavMartAssistant = ({ onSearchResults }: RavMartAssistantProps) => {
  const [mode, setMode] = useState<'multimodal' | 'live' | 'live2'>('multimodal');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleModeChange = (event: SelectChangeEvent<string>) => {
    const newMode = event.target.value as 'multimodal' | 'live' | 'live2';
    setMode(newMode);
    setMessages([]); // Clear messages when switching modes
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages([...messages, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      let response;
      if (mode === 'multimodal') {
        // Use the multimodal API
        response = await fetch('http://localhost:5000/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: input,
            history: messages.map(msg => ({
              role: msg.role,
              content: msg.content
            }))
          }),
        });
        const data = await response.json();
        if (data.function_results && data.function_results.length > 0) {
          const functionResult = data.function_results[0];
          if (functionResult.function_name === 'search_products' && functionResult.results) {
            onSearchResults(functionResult.results);
          }
        }
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.text || 'Sorry, I could not generate a response.',
          timestamp: new Date()
        };
        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, there was an error processing your request. Please try again.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" component="h2">
          RavMart Assistant
        </Typography>
        <FormControl variant="outlined" size="small" sx={{ minWidth: 150 }}>
          <InputLabel id="chat-mode-label">Mode</InputLabel>
          <Select
            labelId="chat-mode-label"
            value={mode}
            onChange={handleModeChange}
            label="Mode"
          >
            <MenuItem value="multimodal">Standard</MenuItem>
            <MenuItem value="live">Live Chat</MenuItem>
            <MenuItem value="live2">Live2 (VAD+Camera)</MenuItem>
          </Select>
        </FormControl>
      </Box>
      <Divider sx={{ mb: 2 }} />
      <div style={{ display: mode === 'live' ? 'block' : 'none' }}>
        <LiveChat onSearchResults={onSearchResults} />
      </div>
      <div style={{ display: mode === 'live2' ? 'block' : 'none' }}>
        <Live2Chat onSearchResults={onSearchResults} />
      </div>
      <div style={{ display: mode === 'live' || mode === 'live2' ? 'none' : 'block' }}>
        {/* Messages display area */}
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
                Ask me about products or how I can help you shop at RavMart!
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
        {/* Input area */}
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Ask about products or how I can help..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
            multiline
            maxRows={3}
            sx={{ mr: 1 }}
          />
          <Button
            variant="contained"
            color="primary"
            endIcon={<SendIcon />}
            onClick={handleSendMessage}
            disabled={!input.trim() || isLoading}
          >
            Send
          </Button>
        </Box>
      </div>
    </Paper>
  );
};

export default RavMartAssistant;
