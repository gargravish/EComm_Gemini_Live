import { useState, useEffect, useRef } from 'react'
import { Container, Box, Tabs, Tab, Typography, CssBaseline, ThemeProvider, createTheme, Divider, CircularProgress, Button, Card, IconButton, useMediaQuery } from '@mui/material'
import './App.css'
import { MultimodalChat, LiveChat, SearchBar, ImageUpload, ProductResults, RavMartAssistant } from './components'
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import AddAPhotoIcon from '@mui/icons-material/AddAPhoto';
import ChatIcon from '@mui/icons-material/Chat';
import Modal from '@mui/material/Modal';
import { useTheme } from '@mui/material/styles';
import TextField from '@mui/material/TextField';

// Create a theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
});

// Product interface
interface Product {
  id: string;
  name: string;
  description?: string;
  image_url: string;
  price: string;
  aisle?: string;
}

function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [bannerQuote, setBannerQuote] = useState('');
  const [chatOpen, setChatOpen] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Add a list of quotes and pick one at random on mount
  const quotes = [
    "Shopping is always a good idea!",
    "Life is short. Buy the shoes.",
    "Add to cart. It's a lifestyle.",
    "Retail therapy in session...",
    "You can't buy happiness, but you can buy new arrivals!",
    "Good things come to those who shop RavMart.",
    "Keep calm and shop on.",
    "One more item won't hurt!",
    "Online shopping: because it's frowned upon to be in a store in pajamas.",
    "Treat yourself to something new today!"
  ];

  useEffect(() => {
    setBannerQuote(quotes[Math.floor(Math.random() * quotes.length)]);
  }, []);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
    // Clear search results when switching tabs
    setSearchResults([]);
  };

  const handleSearchResults = (results: Product[]) => {
    setSearchResults(results);
  };

  const handleBannerImageUpload = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    // Handle the selected file (image upload logic)
    // You can call your image upload handler here
  };

  const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchInput(event.target.value);
  };

  const handleSearch = async () => {
    if (!searchInput.trim()) return;
    setIsLoading(true);
    setSearchResults([]);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchInput })
      });
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (err) {
      setSearchResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleImageUpload = () => {
    // Implementation for handling image upload
  };

  const handleOpenChat = () => {
    setChatOpen(true);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ width: '100%', minHeight: '100vh', bgcolor: 'white', display: 'flex', flexDirection: 'column' }}>
        {/* Simple Banner */}
        <Box sx={{ width: '100%', bgcolor: 'white', boxShadow: 2, py: 2 }}>
          <Container maxWidth={false} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: { xs: 2, sm: 3, md: 4 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <ShoppingCartIcon color="primary" sx={{ fontSize: 40 }} />
              <Typography variant="h4" color="primary" fontWeight={700} sx={{ letterSpacing: 1 }}>
                RavMart
              </Typography>
            </Box>
            <Box sx={{ flex: 1, ml: 4 }}>
              <Typography variant="subtitle1" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                Welcome to RavMart!
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {bannerQuote || "Shopping is always a good idea!"}
              </Typography>
            </Box>
          </Container>
        </Box>

        {/* Main Content */}
        <Container
          maxWidth={false}
          sx={{
            maxWidth: 1200,
            width: '100%',
            mx: 'auto',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            mt: 6,
            px: 2,
          }}
        >
          {/* Search Bar Row */}
          <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', mb: 3, gap: 2 }}>
            <Card sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1, boxShadow: 1, borderRadius: 3, width: '100%' }}>
              <TextField
                variant="standard"
                placeholder="Search products (e.g., 'blue shoes')"
                value={searchInput}
                onChange={handleSearchInputChange}
                fullWidth
                InputProps={{ disableUnderline: true, style: { fontSize: 18, background: 'transparent' } }}
                sx={{ flex: 1, mr: 2 }}
              />
              <Button variant="contained" color="primary" onClick={handleSearch} sx={{ borderRadius: 3 }}>
                SEARCH
              </Button>
            </Card>
            {/* Drag & Drop ImageUpload next to search */}
            <Box sx={{ minWidth: 260, maxWidth: 340, width: '25%' }}>
              <ImageUpload onSearchResults={handleSearchResults} onSetLoading={setIsLoading} />
            </Box>
          </Box>

          {isLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 4, width: '100%' }}>
              <CircularProgress />
            </Box>
          )}
          {!isLoading && searchResults.length > 0 && (
            <ProductResults products={searchResults} />
          )}
        </Container>

        {/* Floating Chat Assistant Button */}
        <IconButton
          color="secondary"
          size="large"
          sx={{
            position: 'fixed',
            bottom: isMobile ? 16 : 32,
            right: isMobile ? 16 : 32,
            zIndex: 1300,
            bgcolor: '#e91e63',
            boxShadow: 3,
            '&:hover': { bgcolor: '#ad1457' },
          }}
          onClick={handleOpenChat}
        >
          <ChatIcon sx={{ color: 'white', fontSize: 32 }} />
        </IconButton>

        {/* Chat Assistant Modal */}
        <Modal open={chatOpen} onClose={() => setChatOpen(false)}>
          <Box sx={{
            position: 'fixed',
            bottom: 32,
            right: 32,
            width: 400,
            maxWidth: '90vw',
            bgcolor: 'background.paper',
            borderRadius: 4,
            boxShadow: 24,
            p: 0,
            zIndex: 2000
          }}>
            <RavMartAssistant onSearchResults={handleSearchResults} />
          </Box>
        </Modal>
      </Box>
    </ThemeProvider>
  )
}

export default App
