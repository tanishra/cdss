"""OCR Service - Gemini Vision"""
import google.generativeai as genai
from PIL import Image
import io
import os
from app.core.logging import get_logger

logger = get_logger(__name__)


class OCRService:
    def __init__(self):
        # Get API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """Extract lab values using Gemini Vision."""
        try:
            # Open image
            image = Image.open(io.BytesIO(file_bytes))
            
            # Optimized prompt for lab reports
            prompt = """You are the best OCR Model in the world.
            Extract ALL lab test results and all information from this medical report.
            
            Return ONLY the lab values in this exact format (one per line):
            TestName: Value
            
            For example:
            WBC: 12.5
            Hemoglobin: 10.2
            Glucose: 145
            many more
            
            Extract every test and every vital thing you can find. Include units if visible."""
            
            # Generate response
            response = self.model.generate_content([prompt, image])
            text = response.text
            
            logger.info("gemini_vision_ocr_complete", text_length=len(text))
            return text
            
        except Exception as e:
            logger.error("gemini_vision_error", error=str(e))
            raise


ocr_service = OCRService()