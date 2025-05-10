import { useState } from 'react';
import { Box, TextField, Button, CircularProgress } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

interface Product {
  id: string;
  name: string;
  description?: string;
  image_url: string;
  price: string;
  aisle?: string;
}

interface SearchBarProps {
  onSearchResults: (results: Product[]) => void;
  onSetLoading: (loading: boolean) => void;
}

const SearchBar = ({ onSearchResults, onSetLoading }: SearchBarProps) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsLoading(true);
    onSetLoading(true);
    
    try {
      // Connect to the Flask backend API
      const response = await fetch(`http://localhost:5000/api/search?query=${encodeURIComponent(searchQuery)}`);
      const data = await response.json();
      
      if (data.results) {
        onSearchResults(data.results);
      } else {
        onSearchResults([]);
        console.error('No results found or invalid response format');
      }
    } catch (error) {
      console.error('Error searching:', error);
      onSearchResults([]);
    } finally {
      setIsLoading(false);
      onSetLoading(false);
    }
  };

  return (
    <Box component="form" onSubmit={handleSearch} sx={{ display: 'flex', alignItems: 'center', mb: 3, gap: 2}}>
      <Card sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1, boxShadow: 1, borderRadius: 3, width: '100%' }}>
        <TextField
          fullWidth
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search products (e.g., 'blue t-shirt')"
          variant="outlined"
          size="medium"
          sx={{ mr: 1, flex: 1}}
        />
      </Card>
      <Button
        type="submit"
        variant="contained"
        color="primary"
        disabled={isLoading || !searchQuery.trim()}
        startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
        sx={{
          flexShrink: 0, // Prevent the button from shrinking if space is tight
        }}
      >
        Search
      </Button>
    </Box>
  );
};

export default SearchBar;
