"""
Drug Interaction Service
"""
from typing import List, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class DrugInteractionService:
    """Check for drug interactions and contraindications."""
    
    # Common drug interactions database (simplified)
    INTERACTIONS = {
        "warfarin": {
            "aspirin": "Increased bleeding risk",
            "ibuprofen": "Increased bleeding risk",
            "naproxen": "Increased bleeding risk",
        },
        "aspirin": {
            "warfarin": "Increased bleeding risk",
            "ibuprofen": "Increased GI bleeding risk",
        },
        "metformin": {
            "alcohol": "Risk of lactic acidosis",
        },
        "atorvastatin": {
            "grapefruit": "Increased statin levels",
        },
        "lisinopril": {
            "potassium": "Risk of hyperkalemia",
        },
        "amoxicillin": {
            "methotrexate": "Increased methotrexate toxicity",
        },
    }
    
    def check_interactions(
        self,
        new_medication: str,
        current_medications: List[str],
        allergies: List[str]
    ) -> Dict[str, Any]:
        """Check for drug interactions and allergies."""
        try:
            warnings = []
            
            # Check allergies
            allergy_match = self._check_allergies(new_medication, allergies)
            if allergy_match:
                warnings.append({
                    "severity": "CRITICAL",
                    "type": "allergy",
                    "message": f"Patient is allergic to {allergy_match}",
                })
            
            # Check drug-drug interactions
            new_med_lower = new_medication.lower()
            
            if new_med_lower in self.INTERACTIONS:
                for current_med in current_medications:
                    current_med_lower = current_med.lower()
                    
                    if current_med_lower in self.INTERACTIONS[new_med_lower]:
                        warnings.append({
                            "severity": "MODERATE",
                            "type": "drug_interaction",
                            "drug1": new_medication,
                            "drug2": current_med,
                            "message": self.INTERACTIONS[new_med_lower][current_med_lower],
                        })
            
            # Check reverse interactions
            for current_med in current_medications:
                current_med_lower = current_med.lower()
                
                if current_med_lower in self.INTERACTIONS:
                    if new_med_lower in self.INTERACTIONS[current_med_lower]:
                        warnings.append({
                            "severity": "MODERATE",
                            "type": "drug_interaction",
                            "drug1": current_med,
                            "drug2": new_medication,
                            "message": self.INTERACTIONS[current_med_lower][new_med_lower],
                        })
            
            has_interactions = len(warnings) > 0
            
            logger.info(
                "interaction_check_complete",
                medication=new_medication,
                warnings_found=len(warnings),
            )
            
            return {
                "has_interactions": has_interactions,
                "warnings": warnings,
                "safe_to_prescribe": not any(w["severity"] == "CRITICAL" for w in warnings),
            }
            
        except Exception as e:
            logger.error("interaction_check_error", error=str(e))
            return {
                "has_interactions": False,
                "warnings": [],
                "safe_to_prescribe": True,
                "error": str(e),
            }
    
    def _check_allergies(self, medication: str, allergies: List[str]) -> str:
        """Check if medication matches any allergies."""
        med_lower = medication.lower()
        
        for allergy in allergies:
            allergy_lower = allergy.lower()
            
            # Exact match
            if med_lower == allergy_lower:
                return allergy
            
            # Check if medication contains allergy
            if allergy_lower in med_lower:
                return allergy
            
            # Check drug class matches (simplified)
            if self._same_drug_class(med_lower, allergy_lower):
                return allergy
        
        return None
    
    def _same_drug_class(self, med1: str, med2: str) -> bool:
        """Check if medications are in the same class."""
        drug_classes = {
            "penicillin": ["amoxicillin", "ampicillin", "penicillin"],
            "cephalosporin": ["cephalexin", "ceftriaxone"],
            "nsaid": ["ibuprofen", "naproxen", "aspirin"],
            "statin": ["atorvastatin", "simvastatin", "rosuvastatin"],
        }
        
        for drug_class, members in drug_classes.items():
            if med1 in members and med2 in members:
                return True
        
        return False


# Global instance
drug_interaction_service = DrugInteractionService()