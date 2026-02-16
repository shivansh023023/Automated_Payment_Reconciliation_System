"""FastAPI application for Automated Payment Reconciliation System."""

import csv
import io
import logging
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from db import get_conn, execute_query, execute_update, transaction
from matcher import reconcile

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Reconciliation System", version="1.0.0")


class ConfirmMatchRequest(BaseModel):
    reviewer: str
    action: str


@app.on_event("startup")
async def startup():
    """Initialize database connection on startup."""
    try:
        get_conn()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Close database connection on shutdown."""
    from db import close_conn
    close_conn()
    logger.info("Database connection closed")


@app.post("/upload/payments")
async def upload_payments(file: UploadFile = File(...)):
    """Upload ledger payments CSV file."""
    try:
        contents = await file.read()
        text = contents.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        
        rows_inserted = 0
        with transaction() as conn:
            for row in reader:
                # Parse CSV row
                amount = float(row.get('amount', 0))
                date = row.get('date')
                reference = row.get('reference', '')
                payee = row.get('payee', '')
                
               
                insert_query = """
                    INSERT INTO payments (amount, date, reference, payee, raw, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """
                import json
                execute_update(insert_query, (
                    amount, date, reference, payee, 
                    json.dumps(row)
                ))
                rows_inserted += 1
        
        logger.info(f"Uploaded {rows_inserted} payment records")
        return JSONResponse({
            "status": "success",
            "rows_inserted": rows_inserted,
            "message": f"Successfully uploaded {rows_inserted} payment records"
        })
    
    except Exception as e:
        logger.error(f"Error uploading payments: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/upload/bank")
async def upload_bank(file: UploadFile = File(...)):
    """Upload bank transactions CSV file."""
    try:
        contents = await file.read()
        text = contents.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        
        rows_inserted = 0
        with transaction() as conn:
            for row in reader:
                # Parse CSV row
                amount = float(row.get('amount', 0))
                date = row.get('date')
                reference = row.get('reference', '')
                payee = row.get('payee', '')
                
                
                insert_query = """
                    INSERT INTO bank_transactions (amount, date, reference, payee, raw, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """
                import json
                execute_update(insert_query, (
                    amount, date, reference, payee,
                    json.dumps(row)
                ))
                rows_inserted += 1
        
        logger.info(f"Uploaded {rows_inserted} bank transaction records")
        return JSONResponse({
            "status": "success",
            "rows_inserted": rows_inserted,
            "message": f"Successfully uploaded {rows_inserted} bank transaction records"
        })
    
    except Exception as e:
        logger.error(f"Error uploading bank transactions: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/reconcile")
async def run_reconcile():
    """Trigger reconciliation job."""
    try:
        result = reconcile()
        return JSONResponse({
            "status": "success",
            "result": result,
            "message": f"Reconciliation complete: {result['matched']} matched, {result['unmatched']} unmatched"
        })
    except Exception as e:
        logger.error(f"Error during reconciliation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/matches")
async def get_matches(status: Optional[str] = None, limit: int = 100):
    """Get recent matches, optionally filtered by status."""
    try:
        query = """
            SELECT 
                m.id,
                m.payment_id,
                m.bank_txn_id,
                m.match_score,
                m.match_type,
                m.matched_at,
                m.reviewer,
                m.confirmed,
                p.amount as payment_amount,
                p.date as payment_date,
                p.reference as payment_reference,
                p.payee as payment_payee,
                b.amount as bank_amount,
                b.date as bank_date,
                b.reference as bank_reference,
                b.payee as bank_payee
            FROM matches m
            JOIN payments p ON m.payment_id = p.id
            JOIN bank_transactions b ON m.bank_txn_id = b.id
        """
        
        params = []
        if status:
            if status == "confirmed":
                query += " WHERE m.confirmed = TRUE"
            elif status == "pending":
                query += " WHERE m.confirmed = FALSE"
        
        query += " ORDER BY m.matched_at DESC LIMIT %s"
        params.append(limit)
        
        matches = execute_query(query, tuple(params) if params else (limit,))
        
        # This part Converts date/datetime objects and Decimal to strings/float for JSON serialization
        from decimal import Decimal
        for match in matches:
            if 'payment_date' in match and match['payment_date']:
                match['payment_date'] = str(match['payment_date'])
            if 'bank_date' in match and match['bank_date']:
                match['bank_date'] = str(match['bank_date'])
            if 'matched_at' in match and match['matched_at']:
                match['matched_at'] = str(match['matched_at'])
            # this part Converts Decimal to float
            if 'payment_amount' in match and isinstance(match['payment_amount'], Decimal):
                match['payment_amount'] = float(match['payment_amount'])
            if 'bank_amount' in match and isinstance(match['bank_amount'], Decimal):
                match['bank_amount'] = float(match['bank_amount'])
            if 'match_score' in match and isinstance(match['match_score'], Decimal):
                match['match_score'] = int(match['match_score'])
        
        return JSONResponse({
            "status": "success",
            "count": len(matches),
            "matches": matches
        })
    
    except Exception as e:
        logger.error(f"Error fetching matches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/matches/{match_id}/confirm")
async def confirm_match(match_id: int, request: ConfirmMatchRequest):
    """Confirm or unmatch a reconciliation result."""
    try:
        if request.action not in ["confirm", "unmatch"]:
            raise HTTPException(status_code=400, detail="action must be 'confirm' or 'unmatch'")
        
        with transaction() as conn:
            # This part Checks if match exists
            check_query = "SELECT id, payment_id, bank_txn_id FROM matches WHERE id = %s"
            match = execute_query(check_query, (match_id,))
            
            if not match:
                raise HTTPException(status_code=404, detail="Match not found")
            
            match_data = match[0]
            
            if request.action == "confirm":
                # Confirm the match
                update_query = """
                    UPDATE matches 
                    SET confirmed = TRUE, reviewer = %s
                    WHERE id = %s
                """
                execute_update(update_query, (request.reviewer, match_id))
                
                # This code Update payment and bank transaction status
                execute_update("UPDATE payments SET status = 'confirmed' WHERE id = %s", 
                              (match_data['payment_id'],))
                execute_update("UPDATE bank_transactions SET status = 'confirmed' WHERE id = %s", 
                              (match_data['bank_txn_id'],))
                
                logger.info(f"Match {match_id} confirmed by {request.reviewer}")
                return JSONResponse({
                    "status": "success",
                    "message": f"Match {match_id} confirmed"
                })
            
            else:  # unmatch
               
                execute_update("DELETE FROM matches WHERE id = %s", (match_id,))
                
                # Reset payment and bank transaction status
                execute_update("UPDATE payments SET status = 'pending' WHERE id = %s", 
                              (match_data['payment_id'],))
                execute_update("UPDATE bank_transactions SET status = 'pending' WHERE id = %s", 
                              (match_data['bank_txn_id'],))
                
                logger.info(f"Match {match_id} removed by {request.reviewer}")
                return JSONResponse({
                    "status": "success",
                    "message": f"Match {match_id} removed"
                })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming match: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Payment Reconciliation System",
        "version": "1.0.0",
        "endpoints": {
            "POST /upload/payments": "Upload ledger payments CSV",
            "POST /upload/bank": "Upload bank transactions CSV",
            "POST /reconcile": "Run reconciliation job",
            "GET /matches": "Get recent matches (optional ?status=confirmed|pending&limit=100)",
            "POST /matches/{id}/confirm": "Confirm or unmatch a reconciliation result"
        }
    }

