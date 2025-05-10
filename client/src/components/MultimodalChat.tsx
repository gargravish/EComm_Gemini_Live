import { useState, useRef } from 'react';
import { 
  Box, 
  TextField, 
  Button, 
  Paper, 
  Typography, 
  CircularProgress,
  IconButton,
  Divider
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import ImageIcon from '@mui/icons-material/Image';
import ReactMarkdown from 'react-markdown';
import axios from 'axios';

// Define message type
interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  imageUrl?: string;
}

// Define product type for search results
interface Product {
  name: string;
  price: string;
  rating: number;
}

const MultimodalChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [image, setImage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Function to scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Handle file selection for image upload
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  // Handle sending a message
  const handleSendMessage = async () => {
    if ((!input.trim() && !image) || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date(),
      imageUrl: image || undefined
    };

    setMessages([...messages, userMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      // Determine which API endpoint to use based on whether an image is included
      const endpoint = image 
        ? 'http://localhost:5000/api/chat/image'
        : 'http://localhost:5000/api/chat';
      
      // Prepare request data
      const requestData = {
        message: input,
        history: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        })),
        ...(image && { image })
      };
      
      // Send request to backend
      const response = await axios.post(endpoint, requestData);
      
      // Process response
      if (response.data.error) {
        // Handle error
        const errorMessage: Message = {
          role: 'assistant',
          content: `Error: ${response.data.error}`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, errorMessage]);
      } else {
        // Handle successful response
        const assistantMessage: Message = {
          role: 'assistant',
          content: response.data.text || '',
          timestamp: new Date()
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        
        // Handle function results (e.g., product search)
        if (response.data.function_results && response.data.function_results.length > 0) {
          const functionResult = response.data.function_results[0];
          if (functionResult.function_name === 'search_products' && functionResult.results) {
            setProducts(functionResult.results);
          }
        }
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
      setImage(null);
      setTimeout(scrollToBottom, 100);
    }
  };

  // Handle key press (Enter to send)
  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Box sx={{ height: '70vh', display: 'flex', flexDirection: 'column' }}>
      {/* Messages display area */}
      <Paper 
        elevation={3} 
        sx={{ 
          flexGrow: 1, 
          p: 2, 
          mb: 2, 
          overflow: 'auto', 
          maxHeight: 'calc(70vh - 80px)',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        {messages.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Typography variant="body1" color="text.secondary">
              Send a message to start a conversation
            </Typography>
          </Box>
        ) : (
          messages.map((message, index) => (
            <Box 
              key={index} 
              sx={{ 
                mb: 2, 
                alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%'
              }}
            >
              <Paper 
                elevation={1} 
                sx={{ 
                  p: 2, 
                  bgcolor: message.role === 'user' ? 'primary.light' : 'background.paper',
                  color: message.role === 'user' ? 'white' : 'text.primary'
                }}
              >
                {message.imageUrl && (
                  <Box sx={{ mb: 1 }}>
                    <img 
                      src={message.imageUrl} 
                      alt="User uploaded" 
                      style={{ maxWidth: '100%', maxHeight: '200px', borderRadius: '4px' }} 
                    />
                  </Box>
                )}
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </Paper>
              <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
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
        <div ref={messagesEndRef} />
      </Paper>

      {/* Product search results display */}
      {products.length > 0 && (
        <Paper elevation={2} sx={{ mb: 2, p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Product Search Results
          </Typography>
          <Divider sx={{ mb: 1 }} />
          {products.map((product, index) => (
            <Box key={index} sx={{ mb: 1 }}>
              <Typography variant="subtitle1">{product.name}</Typography>
              <Typography variant="body2">Price: {product.price} | Rating: {product.rating}/5</Typography>
              {index < products.length - 1 && <Divider sx={{ my: 1 }} />}
            </Box>
          ))}
        </Paper>
      )}

      {/* Image preview */}
      {image && (
        <Box sx={{ mb: 2, position: 'relative' }}>
          <img 
            src={image} 
            alt="Preview" 
            style={{ maxHeight: '100px', borderRadius: '4px' }} 
          />
          <IconButton 
            size="small" 
            sx={{ position: 'absolute', top: 0, right: 0, bgcolor: 'rgba(0,0,0,0.5)', color: 'white' }}
            onClick={() => setImage(null)}
          >
            &times;
          </IconButton>
        </Box>
      )}

      {/* Input area */}
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <input
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          ref={fileInputRef}
          onChange={handleFileChange}
        />
        <IconButton 
          color="primary" 
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
        >
          <ImageIcon />
        </IconButton>
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Type your message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isLoading}
          multiline
          maxRows={4}
          sx={{ mx: 1 }}
        />
        <Button
          variant="contained"
          color="primary"
          endIcon={<SendIcon />}
          onClick={handleSendMessage}
          disabled={(!input.trim() && !image) || isLoading}
        >
          Send
        </Button>
      </Box>
    </Box>
  );
};

export default MultimodalChat;
