from fastapi import APIRouter, Depends, HTTPException
from database.firebase_client import FirebaseClient
from datetime import datetime, timedelta
import secrets
import qrcode
from io import BytesIO
import base64
import json

router = APIRouter(prefix="/qr", tags=["qr-attendance"])

def get_db():
    return FirebaseClient()

@router.post("/generate")
async def generate_qr_code(
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Generate a secure QR code for attendance"""
    try:
        # Generate unique token
        token = secrets.token_urlsafe(32)
        
        # Set expiry to 5 minutes
        expiry = datetime.now() + timedelta(minutes=5)
        
        # Store token in Firebase with expiry
        qr_ref = db.get_reference("qr_tokens").child(token)
        qr_ref.set({
            "created_at": datetime.now().isoformat(),
            "expires_at": expiry.isoformat(),
            "scans": 0,
            "status": "active"
        })
        
        # Generate QR code
        qr_data = f"http://localhost:3000/qr-scan?token={token}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return {
            "success": True,
            "token": token,
            "qr_code": f"data:image/png;base64,{img_str}",
            "expires_in": 300,  # 5 minutes in seconds
            "message": "QR code generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
async def scan_qr_code(
    data: dict,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Mark attendance from QR scan"""
    try:
        token = data.get("token")
        student_id = data.get("student_id")
        
        if not token or not student_id:
            raise HTTPException(status_code=400, detail="Missing token or student_id")
        
        # Verify token
        qr_ref = db.get_reference("qr_tokens").child(token)
        qr_data = qr_ref.get()
        
        if not qr_data:
            raise HTTPException(status_code=404, detail="Invalid QR code")
        
        qr_info = qr_data
        
        # Check expiry
        expiry_time = datetime.fromisoformat(qr_info["expires_at"])
        if datetime.now() > expiry_time:
            raise HTTPException(status_code=400, detail="QR code expired")
        
        # Check if already marked today
        today = datetime.now().strftime("%Y-%m-%d")
        attendance_ref = db.get_reference("attendance").child(today).child(student_id)
        existing = attendance_ref.get()
        
        if existing:
            raise HTTPException(status_code=400, detail="Already marked attendance today")
        
        # Mark attendance
        attendance_ref.set({
            "student_id": student_id,
            "method": "qr_code",
            "marked_at": datetime.now().isoformat(),
            "status": "present",
            "qr_token": token,
            "confidence": 1.0  # QR code is 100% confident
        })
        
        # Update scan count
        qr_ref.update({"scans": qr_info["scans"] + 1})
        
        return {
            "success": True,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "method": "qr_code",
            "message": "Attendance marked successfully via QR code"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/{token}")
async def validate_qr_token(
    token: str,
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Validate QR token"""
    try:
        qr_ref = db.get_reference("qr_tokens").child(token)
        qr_data = qr_ref.get()
        
        if not qr_data:
            return {
                "valid": False,
                "message": "Invalid QR code"
            }
        
        qr_info = qr_data
        
        # Check expiry
        expiry_time = datetime.fromisoformat(qr_info["expires_at"])
        is_valid = datetime.now() <= expiry_time and qr_info["status"] == "active"
        
        return {
            "valid": is_valid,
            "token": token,
            "expires_at": qr_info["expires_at"],
            "scans": qr_info["scans"],
            "message": "Token is valid" if is_valid else "Token expired or inactive"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_expired_tokens(
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Remove expired QR tokens (admin task)"""
    try:
        qr_ref = db.get_reference("qr_tokens")
        all_tokens = qr_ref.get()
        
        if not all_tokens:
            return {
                "success": True,
                "cleaned": 0,
                "message": "No tokens to clean"
            }
        
        cleaned_count = 0
        for token, token_info in all_tokens.items():
            try:
                expiry_time = datetime.fromisoformat(token_info["expires_at"])
                if datetime.now() > expiry_time:
                    qr_ref.child(token).delete()
                    cleaned_count += 1
            except:
                continue
        
        return {
            "success": True,
            "cleaned": cleaned_count,
            "message": f"Cleaned {cleaned_count} expired tokens"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_qr_statistics(
    db: FirebaseClient = Depends(get_db)
) -> dict:
    """Get QR attendance statistics"""
    try:
        qr_ref = db.get_reference("qr_tokens")
        all_tokens = qr_ref.get()
        
        if not all_tokens:
            return {
                "total_qr_codes": 0,
                "active_qr_codes": 0,
                "total_scans": 0,
                "average_scans_per_qr": 0
            }
        
        tokens = all_tokens
        active_count = 0
        total_scans = 0
        
        for token_info in tokens.values():
            if token_info["status"] == "active":
                expiry_time = datetime.fromisoformat(token_info["expires_at"])
                if datetime.now() <= expiry_time:
                    active_count += 1
            total_scans += token_info.get("scans", 0)
        
        return {
            "total_qr_codes": len(tokens),
            "active_qr_codes": active_count,
            "total_scans": total_scans,
            "average_scans_per_qr": total_scans / len(tokens) if tokens else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
