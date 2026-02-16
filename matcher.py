"""Matching engine for payment reconciliation using exact and fuzzy matching."""

import re
from typing import Dict, Any, Optional, Tuple
from rapidfuzz import fuzz
import logging
from db import stream_rows, transaction, execute_update

logger = logging.getLogger(__name__)

# Configuration thresholds
CONFIG = {
    "DATE_WINDOW_DAYS": 1,
    "FUZZY_REF_THRESHOLD": 90,
    "FUZZY_PAYEE_THRESHOLD": 85,
    "AMOUNT_TOLERANCE_PERCENT": 0.5,
    "FETCH_SIZE": 500,
    "MIN_MATCH_SCORE": 80,  # Minimum score for  considering a match
}


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, remove punctuation."""
    if not text:
        return ""
    
    
    normalized = text.lower().strip()
    
    
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized


def score_pair(payment_row: Dict[str, Any], bank_row: Dict[str, Any]) -> Tuple[int, str]:
    """
    Score a payment-bank transaction pair.
    
    Returns:
        Tuple of (score, match_type) where score is 0-100
    """
    payment_amount = float(payment_row['amount'])
    bank_amount = float(bank_row['amount'])
    
    payment_date = payment_row['date']
    bank_date = bank_row['date']
    
    payment_ref = normalize_text(payment_row.get('reference', '') or '')
    bank_ref = normalize_text(bank_row.get('reference', '') or '')
    
    payment_payee = normalize_text(payment_row.get('payee', '') or '')
    bank_payee = normalize_text(bank_row.get('payee', '') or '')
    
    
    date_diff = abs((payment_date - bank_date).days)
    # these are the core rules of the algorithm
    # Rule 1: Exact match
    # Amount == amount AND date within ±1 day AND normalized reference equal
    if (payment_amount == bank_amount and 
        date_diff <= CONFIG["DATE_WINDOW_DAYS"] and 
        payment_ref == bank_ref and payment_ref):
        return 100, "exact"
    
    # Rule 2: Fuzzy reference match
    # Amount == amount AND fuzzy(reference) >= 90
    if payment_amount == bank_amount and payment_ref and bank_ref:
        ref_score = fuzz.ratio(payment_ref, bank_ref)
        if ref_score >= CONFIG["FUZZY_REF_THRESHOLD"]:
            return 90, "fuzzy_reference"
    
    # Rule 3: Amount-close + payee fuzzy
    # Amount within ±0.5% AND fuzzy(payee) >= 85
    amount_diff_percent = abs(payment_amount - bank_amount) / max(abs(payment_amount), 0.01) * 100
    if amount_diff_percent <= CONFIG["AMOUNT_TOLERANCE_PERCENT"]:
        if payment_payee and bank_payee:
            payee_score = fuzz.ratio(payment_payee, bank_payee)
            if payee_score >= CONFIG["FUZZY_PAYEE_THRESHOLD"]:
                return 80, "fuzzy_payee"
    
    return 0, "no_match"


def reconcile():
    """
    Run reconciliation job using server-side cursors for memory efficiency.
    
    Iterates through payments in batches, finds candidate bank transactions,
    scores matches, and inserts results into matches table.
    """
    logger.info("Starting reconciliation job")
    
    with transaction() as conn:
        # First, mark all existing matches as needing review if payment/bank status changed
        
        
       
        # This avoids loading all payments into memory
        payments_query = """
            SELECT id, amount, date, reference, payee, status
            FROM payments
            WHERE status = 'pending'
            ORDER BY id
        """
        
        match_count = 0
        unmatched_count = 0
        
        
        for payment in stream_rows(payments_query, name="payments_cursor", 
                                   fetch_size=CONFIG["FETCH_SIZE"]):
            payment_id = payment['id']
            payment_amount = float(payment['amount'])
            
            # Find candidate bank transactions using blocking strategy
            # Candidates: exact amount OR rounded amount within tolerance
            # We'll use a window around the payment amount
            amount_tolerance = payment_amount * (CONFIG["AMOUNT_TOLERANCE_PERCENT"] / 100)
            min_amount = payment_amount - amount_tolerance
            max_amount = payment_amount + amount_tolerance
            
            # Also check exact amount for faster lookup
            candidates_query = """
                SELECT id, amount, date, reference, payee, status
                FROM bank_transactions
                WHERE status = 'pending'
                  AND amount BETWEEN %s AND %s
                ORDER BY ABS(amount - %s), date
            """
            
            best_score = 0
            best_bank_txn = None
            best_match_type = None
            
           
            # This ensures we don't load all candidates into memory
            
            # to avoid cursor conflicts
            for bank_txn in stream_rows(candidates_query, 
                                       params=(min_amount, max_amount, payment_amount),
                                       name=f"bank_candidates_{payment_id}",
                                       fetch_size=CONFIG["FETCH_SIZE"]):
                
                score, match_type = score_pair(payment, bank_txn)
                
                if score > best_score and score >= CONFIG["MIN_MATCH_SCORE"]:
                    best_score = score
                    best_bank_txn = bank_txn
                    best_match_type = match_type
            
            # Insert match if found
            if best_bank_txn:
                # Check if bank transaction is already matched 
                from db import get_conn
                conn = get_conn()
                with conn.cursor() as check_cursor:
                    check_cursor.execute(
                        "SELECT COUNT(*) as cnt FROM matches WHERE bank_txn_id = %s AND confirmed = TRUE",
                        (best_bank_txn['id'],)
                    )
                    result = check_cursor.fetchone()
                    if result and result[0] > 0:
                        # Already matched, skip
                        execute_update("UPDATE payments SET status = 'unmatched' WHERE id = %s", (payment_id,))
                        unmatched_count += 1
                        continue
                
                insert_match_query = """
                    INSERT INTO matches (payment_id, bank_txn_id, match_score, match_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (payment_id, bank_txn_id) DO NOTHING
                """
                execute_update(insert_match_query, 
                              (payment_id, best_bank_txn['id'], best_score, best_match_type))
                
                # Update status
                execute_update("UPDATE payments SET status = 'matched' WHERE id = %s", (payment_id,))
                execute_update("UPDATE bank_transactions SET status = 'matched' WHERE id = %s", 
                              (best_bank_txn['id'],))
                
                match_count += 1
                logger.debug(f"Matched payment {payment_id} with bank_txn {best_bank_txn['id']} "
                           f"(score: {best_score}, type: {best_match_type})")
            else:
                # Mark as unmatched for manual review
                execute_update("UPDATE payments SET status = 'unmatched' WHERE id = %s", (payment_id,))
                unmatched_count += 1
        
        logger.info(f"Reconciliation complete: {match_count} matched, {unmatched_count} unmatched")
        return {"matched": match_count, "unmatched": unmatched_count}


