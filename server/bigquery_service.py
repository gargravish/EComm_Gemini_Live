from google.cloud import bigquery
from google.cloud import storage
import re
import logging
from functools import lru_cache

class BigQueryService:
    def __init__(self, project_id, dataset):
        self.project_id = project_id
        self.dataset = dataset
        self.client = bigquery.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)
        
    def get_signed_urls(self, urls):
        """Get signed URLs for GCS images"""
        # Convert the list of URIs into a string for the IN clause
        uris = [re.search(r'"(gs://[^"]+)"', item).group(1) for item in urls]
        uri_string = ", ".join([f"'{uri}'" for uri in uris])
        
        query = f"""
        SELECT signed_url
        FROM EXTERNAL_OBJECT_TRANSFORM(TABLE `{self.project_id}.{self.dataset}.product_images`, ['SIGNED_URL'])
        WHERE uri IN ({uri_string})
        """

        query_job = self.client.query(query)
        results = query_job.result()
        
        return [row.signed_url for row in results]
        
    def get_product_info(self, product_ids):
        """Get product information - only aisle information is available"""
        # Convert product IDs to integers
        product_id_list = [int(pid) for pid in product_ids]
        
        query = f"""
        SELECT p.productid, 
               p.aisle
        FROM `{self.project_id}.{self.dataset}.product_qty` p
        WHERE p.productid IN ({','.join(map(str, product_id_list))})
        """
        
        query_job = self.client.query(query)
        results = query_job.result()
        
        product_info = []
        for row in results:
            product_info.append({
                'productid': row.productid,
                'aisle': row.aisle
            })
            
        return product_info
        
    def search_products(self, embeddings, k=5):
        """Search for products using embeddings."""
        try:
            # Convert embeddings to string format for BigQuery
            embedding_str = ','.join(map(str, embeddings))
            
            query = f"""
            WITH similarities AS (
                SELECT 
                    product_id,
                    image_uri,
                    aisle,
                    (
                        SELECT 
                            1 - ACOS(LEAST(1.0, GREATEST(-1.0, 
                                SUM(e1 * e2) / SQRT(SUM(e1 * e1) * SUM(e2 * e2))
                            ))) / PI()
                        FROM UNNEST(embedding) e1 WITH OFFSET pos
                        CROSS JOIN UNNEST([{embedding_str}]) e2 WITH OFFSET pos2
                        WHERE pos = pos2
                    ) as similarity
                FROM `{self.project_id}.{self.dataset}.product_embeddings`
            )
            SELECT 
                product_id,
                image_uri,
                aisle,
                ROUND(similarity * 100, 2) as similarity_score
            FROM similarities
            WHERE similarity > 0
            ORDER BY similarity DESC
            LIMIT {k}
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            # Process results
            processed_results = []
            for row in results:
                # Get signed URL for the image
                image_uri = row.image_uri
                if image_uri.startswith('gs://'):
                    bucket_name = image_uri.split('/')[2]
                    blob_name = '/'.join(image_uri.split('/')[3:])
                    bucket = self.storage_client.bucket(bucket_name)
                    blob = bucket.blob(blob_name)
                    signed_url = blob.generate_signed_url(
                        version="v4",
                        expiration=3600,  # URL expires in 1 hour
                        method="GET"
                    )
                else:
                    signed_url = image_uri
                
                processed_results.append({
                    'product_id': row.product_id,
                    'product_image_url': signed_url,
                    'aisle_location': row.aisle,
                    'similarity_score': row.similarity_score
                })
            
            return processed_results
            
        except Exception as e:
            logging.error(f"Error in search_products: {str(e)}")
            raise