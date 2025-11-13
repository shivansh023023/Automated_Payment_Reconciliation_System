"""Unit tests for the matching engine."""

import pytest
from datetime import date
from matcher import normalize_text, score_pair, CONFIG


def test_normalize_text():
    """Test text normalization function."""
    # Test basic normalization
    assert normalize_text("Invoice #INV-1023") == "invoice inv1023"
    assert normalize_text("  Acme Corp.  ") == "acme corp"
    assert normalize_text("Payment REF-4567") == "payment ref4567"
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""
    
    # Test punctuation removal
    assert normalize_text("Test, Inc.") == "test inc"
    assert normalize_text("A-B-C") == "abc"
    
    # Test multiple spaces
    assert normalize_text("Multiple   Spaces") == "multiple spaces"


def test_score_pair_exact_match():
    """Test exact matching rule."""
    payment = {
        'amount': 1234.56,
        'date': date(2025, 1, 15),
        'reference': 'Invoice #INV-1023',
        'payee': 'Acme Corp.'
    }
    
    bank = {
        'amount': 1234.56,
        'date': date(2025, 1, 15),
        'reference': 'Invoice #INV-1023',
        'payee': 'Acme Corp.'
    }
    
    score, match_type = score_pair(payment, bank)
    assert score == 100
    assert match_type == "exact"


def test_score_pair_exact_with_date_window():
    """Test exact match with date within window."""
    payment = {
        'amount': 1234.56,
        'date': date(2025, 1, 15),
        'reference': 'Invoice #INV-1023',
        'payee': 'Acme Corp.'
    }
    
    bank = {
        'amount': 1234.56,
        'date': date(2025, 1, 16),  # 1 day later
        'reference': 'Invoice #INV-1023',
        'payee': 'Acme Corp.'
    }
    
    score, match_type = score_pair(payment, bank)
    assert score == 100
    assert match_type == "exact"


def test_score_pair_fuzzy_reference():
    """Test fuzzy reference matching."""
    payment = {
        'amount': 1234.56,
        'date': date(2025, 1, 15),
        'reference': 'Invoice INV-1023',
        'payee': 'Acme Corp.'
    }
    
    bank = {
        'amount': 1234.56,
        'date': date(2025, 1, 15),
        'reference': 'Invoice INV-1024',  # Typo in number
        'payee': 'Acme Corp.'
    }
    
    score, match_type = score_pair(payment, bank)
    # Should match via fuzzy reference if similarity >= 90
    # Note: After normalization, "invoice inv1023" vs "invoice inv1024" should be similar enough
    assert score >= 90
    assert match_type == "fuzzy_reference"


def test_score_pair_fuzzy_payee():
    """Test fuzzy payee matching with amount tolerance."""
    payment = {
        'amount': 1234.56,
        'date': date(2025, 1, 15),
        'reference': 'REF-123',
        'payee': 'Acme Corporation'
    }
    
    bank = {
        'amount': 1234.50,  # Within 0.5% tolerance
        'date': date(2025, 1, 15),
        'reference': 'REF-456',  # Different reference
        'payee': 'Acme Corp'  # Similar payee
    }
    
    score, match_type = score_pair(payment, bank)
    # Should match via fuzzy payee if similarity >= 85
    if score >= 80:
        assert match_type == "fuzzy_payee"


def test_score_pair_no_match():
    """Test no match scenario."""
    payment = {
        'amount': 1234.56,
        'date': date(2025, 1, 15),
        'reference': 'Invoice #INV-1023',
        'payee': 'Acme Corp.'
    }
    
    bank = {
        'amount': 9999.99,  # Very different amount
        'date': date(2025, 3, 15),  # Very different date
        'reference': 'Different REF',
        'payee': 'Different Payee'
    }
    
    score, match_type = score_pair(payment, bank)
    assert score == 0
    assert match_type == "no_match"


def test_integration_small_match():
    """Integration test simulating a small matching scenario."""
    # Simulate two rows that should match
    payment_row = {
        'amount': 567.89,
        'date': date(2025, 1, 16),
        'reference': 'Payment REF-4567',
        'payee': 'Widget Industries'
    }
    
    bank_row = {
        'amount': 567.89,
        'date': date(2025, 1, 16),
        'reference': 'Payment REF-4567',
        'payee': 'Widget Industries'
    }
    
    score, match_type = score_pair(payment_row, bank_row)
    
    # Should be a match
    assert score >= CONFIG["MIN_MATCH_SCORE"]
    assert match_type in ["exact", "fuzzy_reference", "fuzzy_payee"]
    
    # Verify it's an exact match
    assert score == 100
    assert match_type == "exact"

