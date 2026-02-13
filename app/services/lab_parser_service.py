"""
Lab Results Parser Service
"""
from typing import Dict, List, Any, Optional
import re
from app.core.logging import get_logger

logger = get_logger(__name__)


class LabParserService:
    """Parse and interpret lab results."""
    
    # Reference ranges for common tests
    REFERENCE_RANGES = {
        # Complete Blood Count (CBC)
        "wbc": {"min": 4.5, "max": 11.0, "unit": "10^3/µL", "name": "White Blood Cells"},
        "rbc": {"min": 4.5, "max": 5.9, "unit": "10^6/µL", "name": "Red Blood Cells"},
        "hemoglobin": {"min": 13.5, "max": 17.5, "unit": "g/dL", "name": "Hemoglobin"},
        "hematocrit": {"min": 38.8, "max": 50.0, "unit": "%", "name": "Hematocrit"},
        "platelets": {"min": 150, "max": 400, "unit": "10^3/µL", "name": "Platelets"},
        
        # Comprehensive Metabolic Panel (CMP)
        "glucose": {"min": 70, "max": 100, "unit": "mg/dL", "name": "Glucose"},
        "sodium": {"min": 136, "max": 145, "unit": "mEq/L", "name": "Sodium"},
        "potassium": {"min": 3.5, "max": 5.0, "unit": "mEq/L", "name": "Potassium"},
        "chloride": {"min": 98, "max": 107, "unit": "mEq/L", "name": "Chloride"},
        "co2": {"min": 23, "max": 29, "unit": "mEq/L", "name": "CO2"},
        "bun": {"min": 7, "max": 20, "unit": "mg/dL", "name": "BUN"},
        "creatinine": {"min": 0.7, "max": 1.3, "unit": "mg/dL", "name": "Creatinine"},
        "calcium": {"min": 8.5, "max": 10.5, "unit": "mg/dL", "name": "Calcium"},
        
        # Liver Panel
        "alt": {"min": 7, "max": 56, "unit": "U/L", "name": "ALT"},
        "ast": {"min": 10, "max": 40, "unit": "U/L", "name": "AST"},
        "alkaline_phosphatase": {"min": 44, "max": 147, "unit": "U/L", "name": "Alkaline Phosphatase"},
        "bilirubin_total": {"min": 0.1, "max": 1.2, "unit": "mg/dL", "name": "Total Bilirubin"},
        "albumin": {"min": 3.5, "max": 5.5, "unit": "g/dL", "name": "Albumin"},
        
        # Lipid Panel
        "total_cholesterol": {"min": 0, "max": 200, "unit": "mg/dL", "name": "Total Cholesterol"},
        "ldl": {"min": 0, "max": 100, "unit": "mg/dL", "name": "LDL Cholesterol"},
        "hdl": {"min": 40, "max": 999, "unit": "mg/dL", "name": "HDL Cholesterol"},
        "triglycerides": {"min": 0, "max": 150, "unit": "mg/dL", "name": "Triglycerides"},
    }
    
    def parse_lab_text(self, lab_text: str) -> Dict[str, Any]:
        """Parse lab results from text input."""
        try:
            results = {}
            abnormalities = []
            
            # Common patterns for lab results
            patterns = [
                r'(\w+)\s*[:\-]?\s*(\d+\.?\d*)',  # "WBC: 12.5" or "WBC 12.5"
                r'(\w+)\s*=\s*(\d+\.?\d*)',  # "WBC = 12.5"
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, lab_text, re.IGNORECASE)
                for test_name, value in matches:
                    test_key = test_name.lower().replace(" ", "_")
                    
                    # Check if this is a known test
                    if test_key in self.REFERENCE_RANGES:
                        results[test_key] = {
                            "value": float(value),
                            "name": self.REFERENCE_RANGES[test_key]["name"],
                            "unit": self.REFERENCE_RANGES[test_key]["unit"],
                            "reference_range": {
                                "min": self.REFERENCE_RANGES[test_key]["min"],
                                "max": self.REFERENCE_RANGES[test_key]["max"],
                            }
                        }
                        
                        # Check if abnormal
                        abnormality = self._check_abnormal(test_key, float(value))
                        if abnormality:
                            abnormalities.append(abnormality)
            
            return {
                "parsed_results": results,
                "abnormalities": abnormalities,
                "total_tests": len(results),
                "abnormal_count": len(abnormalities),
            }
            
        except Exception as e:
            logger.error("lab_parsing_error", error=str(e))
            return {"error": str(e)}
    
    def parse_lab_json(self, lab_data: Dict[str, float]) -> Dict[str, Any]:
        """Parse lab results from JSON/dict input."""
        try:
            results = {}
            abnormalities = []
            
            for test_name, value in lab_data.items():
                test_key = test_name.lower().replace(" ", "_")
                
                if test_key in self.REFERENCE_RANGES:
                    results[test_key] = {
                        "value": float(value),
                        "name": self.REFERENCE_RANGES[test_key]["name"],
                        "unit": self.REFERENCE_RANGES[test_key]["unit"],
                        "reference_range": {
                            "min": self.REFERENCE_RANGES[test_key]["min"],
                            "max": self.REFERENCE_RANGES[test_key]["max"],
                        }
                    }
                    
                    abnormality = self._check_abnormal(test_key, float(value))
                    if abnormality:
                        abnormalities.append(abnormality)
            
            return {
                "parsed_results": results,
                "abnormalities": abnormalities,
                "total_tests": len(results),
                "abnormal_count": len(abnormalities),
            }
            
        except Exception as e:
            logger.error("lab_json_parsing_error", error=str(e))
            return {"error": str(e)}
    
    def _check_abnormal(self, test_key: str, value: float) -> Optional[Dict[str, Any]]:
        """Check if a lab value is abnormal."""
        if test_key not in self.REFERENCE_RANGES:
            return None
        
        ref = self.REFERENCE_RANGES[test_key]
        
        if value < ref["min"]:
            return {
                "test": ref["name"],
                "value": value,
                "unit": ref["unit"],
                "status": "LOW",
                "severity": self._get_severity(test_key, value, "low"),
                "reference_range": f"{ref['min']}-{ref['max']} {ref['unit']}",
            }
        elif value > ref["max"]:
            return {
                "test": ref["name"],
                "value": value,
                "unit": ref["unit"],
                "status": "HIGH",
                "severity": self._get_severity(test_key, value, "high"),
                "reference_range": f"{ref['min']}-{ref['max']} {ref['unit']}",
            }
        
        return None
    
    def _get_severity(self, test_key: str, value: float, direction: str) -> str:
        """Determine severity of abnormal value."""
        ref = self.REFERENCE_RANGES[test_key]
        
        if direction == "low":
            deviation = (ref["min"] - value) / ref["min"]
        else:
            deviation = (value - ref["max"]) / ref["max"]
        
        if deviation > 0.5:  # >50% deviation
            return "CRITICAL"
        elif deviation > 0.2:  # >20% deviation
            return "MODERATE"
        else:
            return "MILD"
    
    def get_clinical_interpretation(self, abnormalities: List[Dict]) -> str:
        """Generate clinical interpretation of abnormal labs."""
        if not abnormalities:
            return "All lab values are within normal limits."
        
        interpretations = []
        
        for abnormality in abnormalities:
            test = abnormality["test"]
            status = abnormality["status"]
            severity = abnormality["severity"]
            
            # Clinical interpretations
            if "WBC" in test.upper() and status == "HIGH":
                interpretations.append("Elevated WBC suggests infection or inflammation")
            elif "WBC" in test.upper() and status == "LOW":
                interpretations.append("Low WBC may indicate immunosuppression or bone marrow issue")
            elif "Hemoglobin" in test and status == "LOW":
                interpretations.append("Low hemoglobin indicates anemia")
            elif "Glucose" in test and status == "HIGH":
                interpretations.append("Elevated glucose suggests diabetes or impaired glucose tolerance")
            elif "Creatinine" in test and status == "HIGH":
                interpretations.append("Elevated creatinine may indicate kidney dysfunction")
            elif "ALT" in test or "AST" in test and status == "HIGH":
                interpretations.append("Elevated liver enzymes suggest hepatic dysfunction")
            elif "Potassium" in test and status == "HIGH":
                interpretations.append("Hyperkalemia - cardiac monitoring recommended")
            elif "Potassium" in test and status == "LOW":
                interpretations.append("Hypokalemia - may cause cardiac arrhythmias")
        
        return "; ".join(interpretations) if interpretations else "Abnormal values detected - clinical correlation advised."


# Global instance
lab_parser_service = LabParserService()