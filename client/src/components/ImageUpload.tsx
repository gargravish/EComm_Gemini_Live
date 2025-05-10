import { useState, useRef } from 'react';
import { Box, Paper, Typography, Button, CircularProgress } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import SearchIcon from '@mui/icons-material/Search';

interface Product {
  id: string;
  name: string;
  description?: string;
  image_url: string;
  price: string;
  aisle?: string;
}

interface ImageUploadProps {
  onSearchResults: (results: Product[]) => void;
  onSetLoading: (loading: boolean) => void;
}

const ImageUpload = ({ onSearchResults, onSetLoading }: ImageUploadProps) => {
  const [image, setImage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (event) => {
          if (event.target && typeof event.target.result === 'string') {
            setImage(event.target.result);
          }
        };
        reader.readAsDataURL(file);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (event) => {
          if (event.target && typeof event.target.result === 'string') {
            setImage(event.target.result);
          }
        };
        reader.readAsDataURL(file);
      }
    }
  };

  const handleButtonClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleClearImage = () => {
    setImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSearchByImage = async () => {
    if (!image) return;

    setIsLoading(true);
    onSetLoading(true);

    try {
      const response = await fetch('http://localhost:5000/api/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_data: image
        }),
      });

      const data = await response.json();
      
      if (data.results) {
        onSearchResults(data.results);
      } else {
        onSearchResults([]);
        console.error('No results found or invalid response format');
      }
    } catch (error) {
      console.error('Error searching by image:', error);
      onSearchResults([]);
    } finally {
      setIsLoading(false);
      onSetLoading(false);
    }
  };

  return (
    <Box sx={{ mb: 3 }}>
      <input
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        ref={fileInputRef}
        style={{ display: 'none' }}
      />
      
      {!image ? (
        <Paper
          elevation={3}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          sx={{
            p: 3,
            textAlign: 'center',
            cursor: 'pointer',
            backgroundColor: isDragging ? 'rgba(25, 118, 210, 0.1)' : 'white',
            border: isDragging ? '2px dashed #1976d2' : '2px dashed #ccc',
            borderRadius: 2,
            transition: 'all 0.3s ease',
            height: '200px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center'
          }}
          onClick={handleButtonClick}
        >
          <CloudUploadIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Drag & Drop an Image
          </Typography>
          <Typography variant="body2" color="textSecondary">
            or click to browse
          </Typography>
        </Paper>
      ) : (
        <Box sx={{ position: 'relative' }}>
          <Paper 
            elevation={3}
            sx={{ 
              p: 2,
              borderRadius: 2,
              overflow: 'hidden'
            }}
          >
            <img 
              src={image} 
              alt="Uploaded preview" 
              style={{ 
                width: '100%', 
                maxHeight: '300px', 
                objectFit: 'contain',
                borderRadius: '4px',
                marginBottom: '16px'
              }} 
            />
            
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Button 
                variant="outlined" 
                color="error" 
                startIcon={<DeleteIcon />}
                onClick={handleClearImage}
              >
                Remove
              </Button>
              
              <Button 
                variant="contained" 
                color="primary"
                startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
                onClick={handleSearchByImage}
                disabled={isLoading}
              >
                Search by Image
              </Button>
            </Box>
          </Paper>
        </Box>
      )}
    </Box>
  );
};

export default ImageUpload;
