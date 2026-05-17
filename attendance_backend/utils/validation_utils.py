"""
utils/validation_utils.py
─────────────────────────────────────────────────────────────────────────────
Validation utilities for testing endpoints and verifying system health.

Provides functions for:
- Health checks
- Endpoint validation  
- Data persistence verification
- Exception handling and logging
"""

import logging
from typing import Dict, Any, Optional, Tuple
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class EndpointError(Exception):
    """Raised when endpoint returns error status."""
    pass


def check_health(
    base_url: str = "http://127.0.0.1:8000",
    api_version: str = "v1",
    timeout: float = 5.0
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check system health status.
    
    Parameters
    ----------
    base_url : str
        Base URL of the API (default: http://127.0.0.1:8000)
    api_version : str
        API version (default: "v1")
    timeout : float
        Request timeout in seconds (default: 5.0)
    
    Returns
    -------
    tuple[bool, dict]
        (is_healthy, response_data) where is_healthy is True if overall status is "healthy"
    
    Raises
    ------
    ValidationError
        If health check fails due to network or parsing errors
    """
    try:
        url = f"{base_url}/api/{api_version}/attendance/health"
        logger.debug("Checking health at %s", url)
        
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        is_healthy = data.get("status") == "healthy"
        
        logger.info("Health check: status=%s", data.get("status"))
        return is_healthy, data
        
    except requests.Timeout as exc:
        logger.error("Health check timed out after %.1fs: %s", timeout, exc)
        raise ValidationError(f"Health check timeout: {exc}") from exc
    except requests.RequestException as exc:
        logger.error("Health check request failed: %s", exc)
        raise ValidationError(f"Health check failed: {exc}") from exc
    except ValueError as exc:
        logger.error("Failed to parse health check response: %s", exc)
        raise ValidationError(f"Invalid health response: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected error during health check: %s", exc, exc_info=True)
        raise ValidationError(f"Health check error: {exc}") from exc


def validate_endpoint(
    method: str,
    path: str,
    token: Optional[str] = None,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, str]] = None,
    base_url: str = "http://127.0.0.1:8000",
    api_version: str = "v1",
    expected_status: int = 200,
    timeout: float = 5.0
) -> Tuple[int, Any]:
    """
    Validate an API endpoint response.
    
    Parameters
    ----------
    method : str
        HTTP method ("GET", "POST", "PUT", "DELETE")
    path : str
        API endpoint path (e.g., "/teacher/attendance/history")
    token : str, optional
        JWT authentication token
    json_data : dict, optional
        JSON request body
    params : dict, optional
        Query parameters
    base_url : str
        Base URL of the API (default: http://127.0.0.1:8000)
    api_version : str
        API version (default: "v1")
    expected_status : int
        Expected HTTP status code (default: 200)
    timeout : float
        Request timeout in seconds (default: 5.0)
    
    Returns
    -------
    tuple[int, Any]
        (status_code, response_data)
    
    Raises
    ------
    EndpointError
        If endpoint returns unexpected status or fails
    ValidationError
        If request or parsing fails
    """
    try:
        url = f"{base_url}/api/{api_version}{path}"
        headers = {}
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        logger.debug(
            "Calling %s %s (expected_status=%d)",
            method.upper(),
            path,
            expected_status
        )
        
        # Make request based on method
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data, params=params, timeout=timeout)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=json_data, params=params, timeout=timeout)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params, timeout=timeout)
        else:
            raise ValidationError(f"Unsupported HTTP method: {method}")
        
        # Check status code
        if response.status_code == expected_status:
            try:
                data = response.json()
            except ValueError:
                data = response.text
            
            logger.debug(
                "Endpoint %s returned status %d (expected %d)",
                path,
                response.status_code,
                expected_status
            )
            return response.status_code, data
        else:
            # Status code doesn't match expected
            try:
                error_data = response.json()
            except ValueError:
                error_data = {"error": response.text}
            
            logger.warning(
                "Endpoint %s returned status %d (expected %d): %s",
                path,
                response.status_code,
                expected_status,
                error_data
            )
            raise EndpointError(
                f"Expected {expected_status}, got {response.status_code}: {error_data}"
            )
    
    except requests.Timeout as exc:
        logger.error("Endpoint %s timed out after %.1fs", path, timeout)
        raise ValidationError(f"Request timeout: {exc}") from exc
    except requests.RequestException as exc:
        logger.error("Endpoint %s request failed: %s", path, exc)
        raise ValidationError(f"Request failed: {exc}") from exc
    except EndpointError:
        raise  # Re-raise EndpointError as-is
    except Exception as exc:
        logger.error("Unexpected error validating endpoint %s: %s", path, exc, exc_info=True)
        raise ValidationError(f"Validation error: {exc}") from exc


def verify_firestore_persistence(
    collection: str,
    document_id: str,
    timeout: float = 5.0,
    max_retries: int = 3
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Verify that a document exists in Firestore.
    
    Parameters
    ----------
    collection : str
        Collection name (e.g., "verified_face_outcomes")
    document_id : str
        Document ID to verify
    timeout : float
        Timeout per retry (default: 5.0)
    max_retries : int
        Maximum number of retries (default: 3)
    
    Returns
    -------
    tuple[bool, dict]
        (document_exists, document_data)
    
    Raises
    ------
    ValidationError
        If Firestore access fails
    """
    try:
        import firebase_admin
        from firebase_admin import firestore as admin_firestore
        from google.cloud.firestore_v1 import Client as FirestoreClient
        
        # Get or initialize Firestore client
        try:
            db = admin_firestore.client()
        except ValueError:
            # Not initialized, try to initialize
            logger.debug("Initializing Firebase for persistence check")
            try:
                from google.oauth2.service_account import Credentials
                creds = Credentials.from_service_account_file("config/firebase-credentials.json")
                firebase_admin.initialize_app(options={"credentials": creds})
                db = admin_firestore.client()
            except Exception as init_exc:
                logger.error("Failed to initialize Firebase: %s", init_exc)
                raise ValidationError(f"Firebase initialization failed: {init_exc}") from init_exc
        
        # Try to get the document
        for attempt in range(max_retries):
            try:
                doc = db.collection(collection).document(document_id).get()
                
                if doc.exists:
                    data = doc.to_dict()
                    logger.info(
                        "Document %s/%s verified (attempt %d/%d)",
                        collection,
                        document_id,
                        attempt + 1,
                        max_retries
                    )
                    return True, data
                else:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(0.5)  # Brief wait before retry
                        continue
                    else:
                        logger.warning(
                            "Document %s/%s not found after %d attempts",
                            collection,
                            document_id,
                            max_retries
                        )
                        return False, None
            except Exception as doc_exc:
                if attempt < max_retries - 1:
                    logger.debug("Retry %d/%d for %s/%s: %s", attempt + 1, max_retries, collection, document_id, doc_exc)
                    import time
                    time.sleep(0.5)
                    continue
                else:
                    raise
        
        return False, None
    
    except ValidationError:
        raise
    except Exception as exc:
        logger.error(
            "Error verifying Firestore persistence for %s/%s: %s",
            collection,
            document_id,
            exc,
            exc_info=True
        )
        raise ValidationError(f"Persistence verification failed: {exc}") from exc


def log_validation_summary(results: Dict[str, bool], verbose: bool = False) -> None:
    """
    Log a summary of validation results.
    
    Parameters
    ----------
    results : dict
        Dictionary mapping test names to pass/fail status
    verbose : bool
        If True, log all results; if False, only log failures
    """
    try:
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        logger.info("═══ VALIDATION SUMMARY ═══")
        logger.info("Results: %d/%d tests passed", passed, total)
        
        for name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            if verbose or not result:
                logger.info("%s: %s", name, status)
        
        if passed == total:
            logger.info("✓ All validations passed")
        else:
            logger.warning("⚠ %d test(s) failed", total - passed)
    except Exception as exc:
        logger.error("Error logging validation summary: %s", exc)
