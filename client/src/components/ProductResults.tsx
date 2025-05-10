import { Box, Card, CardMedia, CardContent, Typography, Chip } from '@mui/material';
import Grid from '@mui/material/Grid';

interface Product {
  id: string;
  name: string;
  description?: string;
  image_url: string;
  price: string;
  aisle?: string;
}

interface ProductResultsProps {
  products: Product[];
}

const ProductResults = ({ products }: ProductResultsProps) => {
  if (products.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="h6" color="text.secondary">
          No products found. Try a different search term.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>
        Search Results ({products.length})
      </Typography>
      
      <Grid container spacing={3}>
        {products.map((product) => (
          <Grid item xs={12} sm={6} md={4} key={product.id}>
            <Card 
              elevation={2}
              sx={{ 
                height: '100%', 
                display: 'flex', 
                flexDirection: 'column',
                transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
                '&:hover': {
                  transform: 'translateY(-5px)',
                  boxShadow: 6
                }
              }}
            >
              <CardMedia
                component="img"
                height="200"
                image={product.image_url}
                alt={product.name}
                sx={{ objectFit: 'contain', p: 2, bgcolor: '#f5f5f5' }}
              />
              <CardContent sx={{ flexGrow: 1 }}>
                <Typography gutterBottom variant="h6" component="div" noWrap>
                  {product.name}
                </Typography>
                
                {product.description && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {product.description}
                  </Typography>
                )}
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
                  <Typography variant="h6" color="primary">
                    {product.price}
                  </Typography>
                  
                  {product.aisle && (
                    <Chip 
                      label={product.aisle} 
                      size="small" 
                      color="secondary" 
                      variant="outlined" 
                    />
                  )}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default ProductResults;
