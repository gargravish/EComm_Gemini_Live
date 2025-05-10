import vertexai
import vertexai.vision_models as vision_models
from vertexai.vision_models import (
    MultiModalEmbeddingModel,
    Image
)
from google.cloud.aiplatform_v1beta1 import (
    FeatureOnlineStoreAdminServiceClient,
    FeatureOnlineStoreServiceClient
)
from google.cloud.aiplatform_v1beta1.types import (
    NearestNeighborQuery,
    feature_online_store_service as feature_online_store_service_pb2
)
import base64
import io
from PIL import Image as PILImage
import tempfile
import os
import re
import logging

class VertexAIService:
    def __init__(self, project_id, location, feature_store_id=None, feature_view_id=None):
        self.project_id = project_id
        self.location = location
        self.feature_store_id = feature_store_id
        self.feature_view_id = feature_view_id
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        
        # Initialize multimodal embedding model
        self.model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")
        
        # Initialize feature store clients if IDs are provided
        if feature_store_id and feature_view_id:
            self.admin_client = FeatureOnlineStoreAdminServiceClient(
                client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"}
            )
            
            feature_online_store_instance = self.admin_client.get_feature_online_store(
                name=f"projects/{project_id}/locations/{location}/featureOnlineStores/{feature_store_id}"
            )
            
            public_endpoint = feature_online_store_instance.dedicated_serving_endpoint.public_endpoint_domain_name
            self.data_client = FeatureOnlineStoreServiceClient(
                client_options={"api_endpoint": public_endpoint}
            )
    
    def _base64_to_image(self, base64_string):
        """Convert base64 string to PIL Image"""
        image_data = base64.b64decode(base64_string)
        image = PILImage.open(io.BytesIO(image_data))
        return image
    
    def _save_temp_image(self, image):
        """Save PIL Image to temporary file and return path"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            image.save(temp_file.name)
            return temp_file.name
    
    def get_image_embeddings(self, image_data=None, contextual_text=None):
        """Generate embeddings from image data and/or text"""
        try:
            if image_data:
                try:
                    # Handle data URLs (e.g., data:image/jpeg;base64,/9j/4AAQSkZJRg...)
                    if image_data.startswith('data:'):
                        # Extract the base64 part after the comma
                        image_data = image_data.split(',', 1)[1]
                    
                    # Create a temporary file to store the image
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                        temp_file.write(base64.b64decode(image_data))
                        temp_file_path = temp_file.name
                    
                    logging.info(f"Saved image to temporary file: {temp_file_path}")

                    # Load image from the temporary file
                    image = vision_models.Image.load_from_file(temp_file_path)
                    logging.info("Successfully loaded image with Vertex AI")
                    
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_file_path)
                    except Exception as cleanup_error:
                        logging.warning(f"Failed to clean up temporary file: {str(cleanup_error)}")
                except Exception as img_error:
                    logging.error(f"Failed to process image: {str(img_error)}")
                    raise Exception(f"Failed to process image: {str(img_error)}")
            else:
                image = None
            
            # Get embeddings
            logging.info("Generating embeddings with Vertex AI")
            embeddings = self.model.get_embeddings(
                image=image,
                contextual_text=contextual_text,
            )
            
            # Use image embedding if available, otherwise use text embedding
            embedding_value = embeddings.image_embedding or embeddings.text_embedding
            logging.info(f"Successfully generated embeddings of length {len(embedding_value)}")
            return [v for v in embedding_value]
        
        except Exception as e:
            logging.error(f"Error generating embeddings: {str(e)}")
            raise
    
    def search_feature_store(self, embedding, neighbor_count=5):
        """Search feature store for similar products"""
        if not self.feature_store_id or not self.feature_view_id:
            raise ValueError("Feature store ID and feature view ID must be provided")
        
        request = feature_online_store_service_pb2.SearchNearestEntitiesRequest(
            feature_view=f"projects/{self.project_id}/locations/{self.location}/featureOnlineStores/{self.feature_store_id}/featureViews/{self.feature_view_id}",
            query=NearestNeighborQuery(
                embedding=NearestNeighborQuery.Embedding(value=embedding),
                neighbor_count=neighbor_count,
            ),
            return_full_entity=True,
        )
        
        response = self.data_client.search_nearest_entities(request=request)
        
        # Extract product IDs and GCS URIs
        results = []
        for i in range(min(neighbor_count, len(response.nearest_neighbors.neighbors))):
            neighbor = response.nearest_neighbors.neighbors[i]
            
            # Extract product ID from the feature value
            product_id_str = str(neighbor.entity_key_values.key_values.features[8].value)
            # Try different patterns to match the product ID
            match = None
            patterns = [
                r'"(\d+)"',  # Matches "1234"
                r'string_value: "(\d+)"',  # Matches string_value: "1234"
                r'(\d+)\.jpg',  # Matches 1234.jpg
                r'(\d+)'  # Matches any sequence of digits
            ]
            
            for pattern in patterns:
                match = re.search(pattern, product_id_str)
                if match:
                    break
            
            if not match:
                logging.warning(f"Could not extract product ID from string: {product_id_str}")
                continue
            
            product_id = match.group(1)
            
            # Extract GCS URI
            gcs_uri = str(neighbor.entity_key_values.key_values.features[9].value)
            
            results.append({
                'product_id': product_id,
                'gcs_uri': gcs_uri
            })
            
        return results