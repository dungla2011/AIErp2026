#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script to verify query_invoices tool works"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from data_provider import query_invoices
import json

print("\n" + "="*60)
print("🧪 Testing query_invoices() tool")
print("="*60)

# Test 1: Total revenue
print("\n\n1️⃣ TEST: Tổng doanh thu là bao nhiêu?")
result = query_invoices("Tổng doanh thu là bao nhiêu?", user_role='admin')
print(json.dumps(result, indent=2, ensure_ascii=False))

# Test 2: Count invoices today
print("\n\n2️⃣ TEST: Hôm nay bán bao nhiêu đơn?")
result2 = query_invoices("Hôm nay bán bao nhiêu đơn?", user_role='staff')
print(json.dumps(result2, indent=2, ensure_ascii=False))

# Test 3: Customer denied
print("\n\n3️⃣ TEST: Customer role (should be denied)")
result3 = query_invoices("Tổng doanh thu là bao nhiêu?", user_role='customer')
print(json.dumps(result3, indent=2, ensure_ascii=False))

print("\n✅ Test complete!")
