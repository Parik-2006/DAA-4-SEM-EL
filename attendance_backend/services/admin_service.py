"""
Admin Service - Business logic for admin portal operations.

Handles:
- CIE management (create, read, update, delete)
- Class and course management
- Bulk student and timetable imports
- Admin dashboards and reporting
- System configuration
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from database.firebase_client import FirebaseClient
from config.constants import (
    COLLECTION_CIES, COLLECTION_CLASSES, COLLECTION_STUDENTS,
    COLLECTION_TIMETABLE, COLLECTION_ATTENDANCE, COLLECTION_FACULTY
)

logger = logging.getLogger(__name__)


class AdminService:
    """Service class for admin operations."""
    
    def __init__(self, db: FirebaseClient = None):
        """Initialize admin service with database client."""
        self.db = db or FirebaseClient()
    
    # ==================== CIE Management ====================
    
    def create_cie(self, cie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new CIE."""
        try:
            cie_id = cie_data.get("cie_id")
            if not cie_id:
                return {"success": False, "error": "cie_id required"}
            
            # Create CIE document
            self.db.add_document(COLLECTION_CIES, {
                "cie_id": cie_id,
                "name": cie_data.get("name"),
                "code": cie_data.get("code"),
                "location": cie_data.get("location"),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "is_active": True
            })
            
            logger.info(f"CIE {cie_id} created")
            return {
                "success": True,
                "cie_id": cie_id,
                "message": f"CIE {cie_id} created successfully"
            }
        except Exception as e:
            logger.error(f"Error creating CIE: {e}")
            return {"success": False, "error": str(e)}
    
    def get_all_cies(self) -> Dict[str, Any]:
        """Get all CIEs."""
        try:
            cies = self.db.query_documents(COLLECTION_CIES, [])
            return {
                "success": True,
                "cies": cies,
                "total": len(cies)
            }
        except Exception as e:
            logger.error(f"Error fetching CIEs: {e}")
            return {"success": False, "error": str(e)}
    
    def update_cie(self, cie_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a CIE."""
        try:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            self.db.update_document(COLLECTION_CIES, cie_id, update_data)
            
            logger.info(f"CIE {cie_id} updated")
            return {
                "success": True,
                "cie_id": cie_id,
                "message": f"CIE {cie_id} updated"
            }
        except Exception as e:
            logger.error(f"Error updating CIE: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_cie(self, cie_id: str) -> Dict[str, Any]:
        """Delete a CIE."""
        try:
            self.db.delete_document(COLLECTION_CIES, cie_id)
            
            logger.info(f"CIE {cie_id} deleted")
            return {
                "success": True,
                "message": f"CIE {cie_id} deleted"
            }
        except Exception as e:
            logger.error(f"Error deleting CIE: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== Class Management ====================
    
    def create_class(self, class_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new class."""
        try:
            class_id = class_data.get("class_id")
            if not class_id:
                return {"success": False, "error": "class_id required"}
            
            self.db.add_document(COLLECTION_CLASSES, {
                "class_id": class_id,
                "cie_id": class_data.get("cie_id"),
                "name": class_data.get("name"),
                "semester": class_data.get("semester"),
                "section": class_data.get("section"),
                "total_students": class_data.get("total_students", 0),
                "created_at": datetime.utcnow().isoformat(),
                "is_active": True
            })
            
            logger.info(f"Class {class_id} created")
            return {
                "success": True,
                "class_id": class_id,
                "message": f"Class {class_id} created"
            }
        except Exception as e:
            logger.error(f"Error creating class: {e}")
            return {"success": False, "error": str(e)}
    
    def get_classes_by_cie(self, cie_id: str) -> Dict[str, Any]:
        """Get all classes in a CIE."""
        try:
            classes = self.db.query_documents(
                COLLECTION_CLASSES,
                [("cie_id", "==", cie_id)]
            )
            return {
                "success": True,
                "cie_id": cie_id,
                "classes": classes,
                "total": len(classes)
            }
        except Exception as e:
            logger.error(f"Error fetching classes: {e}")
            return {"success": False, "error": str(e)}
    
    def update_class(self, class_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a class."""
        try:
            self.db.update_document(COLLECTION_CLASSES, class_id, update_data)
            logger.info(f"Class {class_id} updated")
            return {
                "success": True,
                "class_id": class_id,
                "message": f"Class {class_id} updated"
            }
        except Exception as e:
            logger.error(f"Error updating class: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== Bulk Import ====================
    
    def bulk_import_students(self, students_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk import students from CSV."""
        try:
            success_count = 0
            failed_count = 0
            errors = []
            
            for idx, student in enumerate(students_list):
                try:
                    self.db.add_document(COLLECTION_STUDENTS, {
                        "student_id": student.get("student_id"),
                        "name": student.get("name"),
                        "email": student.get("email"),
                        "class_id": student.get("class_id"),
                        "roll_no": student.get("roll_no"),
                        "created_at": datetime.utcnow().isoformat(),
                        "is_active": True
                    })
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append({"index": idx, "error": str(e)})
                    logger.error(f"Error importing student at index {idx}: {e}")
            
            return {
                "success": True,
                "imported": success_count,
                "failed": failed_count,
                "errors": errors,
                "total": len(students_list)
            }
        except Exception as e:
            logger.error(f"Error bulk importing students: {e}")
            return {"success": False, "error": str(e)}
    
    def bulk_import_timetable(self, timetable_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk import timetable entries."""
        try:
            success_count = 0
            failed_count = 0
            errors = []
            
            for idx, period in enumerate(timetable_list):
                try:
                    self.db.add_document(COLLECTION_TIMETABLE, {
                        "period_id": period.get("period_id"),
                        "class_id": period.get("class_id"),
                        "faculty_id": period.get("faculty_id"),
                        "course_id": period.get("course_id"),
                        "course_name": period.get("course_name"),
                        "day_of_week": period.get("day_of_week"),
                        "start_time": period.get("start_time"),
                        "end_time": period.get("end_time"),
                        "room": period.get("room"),
                        "is_lab_class": period.get("is_lab_class", False),
                        "created_at": datetime.utcnow().isoformat()
                    })
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append({"index": idx, "error": str(e)})
                    logger.error(f"Error importing timetable at index {idx}: {e}")
            
            return {
                "success": True,
                "imported": success_count,
                "failed": failed_count,
                "errors": errors,
                "total": len(timetable_list)
            }
        except Exception as e:
            logger.error(f"Error bulk importing timetable: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== Reports ====================
    
    def get_cie_attendance_summary(self, cie_id: str, date_from: Optional[str] = None,
                                   date_to: Optional[str] = None) -> Dict[str, Any]:
        """Get attendance summary for a CIE."""
        try:
            classes = self.db.query_documents(
                COLLECTION_CLASSES,
                [("cie_id", "==", cie_id)]
            )
            
            total_marked = 0
            total_present = 0
            total_absent = 0
            
            for cls in classes:
                # Get attendance for this class
                attendance = self.db.query_documents(
                    COLLECTION_ATTENDANCE,
                    [("class_id", "==", cls.get("class_id"))]
                )
                
                for record in attendance:
                    total_marked += 1
                    if record.get("status") == "present":
                        total_present += 1
                    elif record.get("status") == "absent":
                        total_absent += 1
            
            return {
                "success": True,
                "cie_id": cie_id,
                "total_classes": len(classes),
                "total_marked": total_marked,
                "total_present": total_present,
                "total_absent": total_absent,
                "attendance_percentage": (
                    (total_present / total_marked * 100) if total_marked > 0 else 0
                )
            }
        except Exception as e:
            logger.error(f"Error getting CIE summary: {e}")
            return {"success": False, "error": str(e)}
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get overall system statistics."""
        try:
            cies = self.db.query_documents(COLLECTION_CIES, [])
            classes = self.db.query_documents(COLLECTION_CLASSES, [])
            students = self.db.query_documents(COLLECTION_STUDENTS, [])
            faculty = self.db.query_documents(COLLECTION_FACULTY, [])
            
            return {
                "success": True,
                "total_cies": len(cies),
                "total_classes": len(classes),
                "total_students": len(students),
                "total_faculty": len(faculty),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== System Config ====================
    
    def save_system_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save system configuration."""
        try:
            # Store in a special config document
            self.db.update_document("config", "system", {
                "settings": config_data,
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": "admin"
            })
            
            logger.info("System config updated")
            return {
                "success": True,
                "message": "System configuration updated"
            }
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return {"success": False, "error": str(e)}
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration."""
        try:
            config = self.db.get_document("config", "system")
            
            if not config:
                return {
                    "success": True,
                    "config": {},
                    "message": "No config found"
                }
            
            return {
                "success": True,
                "config": config.get("settings", {})
            }
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return {"success": False, "error": str(e)}
