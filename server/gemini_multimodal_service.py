import os
import json
import logging
import base64
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from gemini_tool_definitions import SEARCH_PRODUCTS_TOOL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

class GeminiMultimodalService:
    def __init__(self):
        """Initialize the Gemini Multimodal Service with API client and model configuration"""
        logger.info("Initializing GeminiMultimodalService")
        
        # Get the model name from environment variables
        self.model_name = os.getenv("GEMINI_MULTIMODAL_MODEL", "gemini-2.5-pro-exp-03-25")
        logger.info(f"Using Gemini model: {self.model_name}")
        
        # Configure tools
        self.tools = [SEARCH_PRODUCTS_TOOL]
        
        # Configure generation parameters from environment variables
        self.generation_config = {
            "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.7")),
            "top_p": float(os.getenv("GEMINI_TOP_P", "0.95")),
            "top_k": int(os.getenv("GEMINI_TOP_K", "40")),
            "max_output_tokens": int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048")),
        }
        
        logger.info(f"Generation config: {self.generation_config}")
        
        # Initialize the model
        try:
            self.model = genai.GenerativeModel(
                self.model_name,
                generation_config=self.generation_config,
                tools=[self.tools]
            )
            
            # System instructions from environment variables
            default_instructions = """You are an intelligent assistant that helps users find products, 
            answer questions, and provide helpful information. You can search for products when asked.
            Always provide concise and helpful responses."""
            
            self.system_instructions = os.getenv("GEMINI_MULTIMODAL_INSTRUCTIONS", default_instructions)
            
            logger.info("GeminiMultimodalService initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Gemini model: {e}")
            raise
    
    def _format_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format the conversation history for the Gemini API"""
        formatted_history = []
        
        for message in history:
            role = message.get("role", "")
            content = message.get("content", "")
            
            if role == "user":
                formatted_history.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                formatted_history.append({"role": "model", "parts": [{"text": content}]})
        
        return formatted_history
    
    def _process_function_call(self, function_call):
        """Process a function call from the model"""
        logger.info(f"Processing function call: {function_call.name}")
        
        if function_call.name == "search_products":
            try:
                # Handle different types of args (str or MapComposite)
                if hasattr(function_call.args, 'get'):
                    # Handle MapComposite object directly
                    query = function_call.args.get("query", "")
                    logger.info(f"Extracted query from MapComposite: {query}")
                else:
                    # Handle string JSON
                    try:
                        args = json.loads(function_call.args)
                        query = args.get("query", "")
                        logger.info(f"Extracted query from JSON string: {query}")
                    except Exception as json_err:
                        logger.error(f"Error parsing function args as JSON: {json_err}")
                        query = str(function_call.args)
                        logger.info(f"Using function args as string: {query}")
                
                # Make a request to our search API
                import requests
                logger.info(f"Searching for products with query: {query}")
                response = requests.get(f"http://localhost:5000/api/search?query={query}")
                data = response.json()
                
                if 'results' in data:
                    # Format the results for the model
                    search_results = []
                    for product in data['results'][:5]:  # Limit to 5 products for cleaner responses
                        search_results.append({
                            "id": product.get('id', ''),
                            "name": product.get('name', ''),
                            "price": product.get('price', ''),
                            "image_url": product.get('image_url', ''),
                            "aisle": product.get('aisle', '')
                        })
                    
                    return {
                        "function_name": "search_products",
                        "results": search_results
                    }
                else:
                    return {
                        "function_name": "search_products",
                        "results": []
                    }
            except Exception as e:
                logger.error(f"Error processing search_products function call: {e}")
                return {
                    "function_name": "search_products",
                    "error": str(e)
                }
        
        return {
            "function_name": function_call.name,
            "error": "Unsupported function"
        }
    
    def generate_content(self, message: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a response to a text message using the Gemini API"""
        try:
            logger.info(f"Generating content for message: {message[:50]}...")
            
            # Format history if provided
            formatted_history = self._format_history(history) if history else []
            
            # Create a chat session with system instructions as first message if no history
            if not formatted_history:
                # Add system instruction as a first hidden message
                system_message = {"role": "user", "parts": [{"text": self.system_instructions}]}
                system_response = {"role": "model", "parts": [{"text": "I'll help you find products and answer your questions."}]}
                formatted_history = [system_message, system_response]
            
            # Create a chat session without system_instruction parameter
            chat = self.model.start_chat(history=formatted_history)
            
            # Send the message
            response = chat.send_message(message)
            
            # Process the response
            result = {
                "text": "",
                "function_results": []
            }
            
            # Handle function calls
            if hasattr(response, 'parts'):
                for part in response.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_result = self._process_function_call(part.function_call)
                        result["function_results"].append(function_result)
                        
                        # Continue the conversation with the function results
                        function_response = chat.send_message({
                            "function_response": {
                                "name": function_result["function_name"],
                                "response": {"products": function_result.get("results", [])}
                            }
                        })
                        
                        # Add the function response text
                        if hasattr(function_response, 'text'):
                            result["text"] += function_response.text
                    
                    # Add text content
                    elif hasattr(part, 'text') and part.text:
                        result["text"] += part.text
            
            logger.info(f"Generated response: {result['text'][:50]}...")
            return result
        
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return {"error": str(e)}
    
    def generate_content_with_image(self, message: str, image_data: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a response to a message with an image using the Gemini API"""
        try:
            logger.info(f"Generating content for message with image: {message[:50]}...")
            
            # Format history if provided
            formatted_history = self._format_history(history) if history else []
            
            # Process the image
            if image_data.startswith("data:image"):
                # Extract the base64 data from the data URL
                image_data = image_data.split(",")[1]
            
            # Decode the base64 image
            image_bytes = base64.b64decode(image_data)
            
            # Create a chat session with system instructions as first message if no history
            if not formatted_history:
                # Add system instruction as a first hidden message
                system_message = {"role": "user", "parts": [{"text": self.system_instructions}]}
                system_response = {"role": "model", "parts": [{"text": "I'll help you find products and answer your questions."}]}
                formatted_history = [system_message, system_response]
            
            # Create a chat session without system_instruction parameter
            chat = self.model.start_chat(history=formatted_history)
            
            # Create the message with image
            message_with_image = [
                {"text": message},
                {"image": genai.types.Blob(data=image_bytes, mime_type="image/jpeg")}
            ]
            
            # Send the message with image
            response = chat.send_message(message_with_image)
            
            # Process the response
            result = {
                "text": "",
                "function_results": []
            }
            
            # Handle function calls
            if hasattr(response, 'parts'):
                for part in response.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_result = self._process_function_call(part.function_call)
                        result["function_results"].append(function_result)
                        
                        # Continue the conversation with the function results
                        function_response = chat.send_message({
                            "function_response": {
                                "name": function_result["function_name"],
                                "response": {"products": function_result.get("results", [])}
                            }
                        })
                        
                        # Add the function response text
                        if hasattr(function_response, 'text'):
                            result["text"] += function_response.text
                    
                    # Add text content
                    elif hasattr(part, 'text') and part.text:
                        result["text"] += part.text
            
            logger.info(f"Generated response for image: {result['text'][:50]}...")
            return result
        
        except Exception as e:
            logger.error(f"Error generating content with image: {e}")
            return {"error": str(e)}
