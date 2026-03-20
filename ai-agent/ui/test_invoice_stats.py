#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script to verify get_invoice_stats tool works"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from data_provider import get_invoice_stats
import json

print("\n" + "="*60)
print("🧪 Testing get_invoice_stats() tool")
print("="*60)

# Test total_revenue
result = get_invoice_stats(stat_type='total_revenue', user_role='admin')
print("\n💰 Total Revenue (admin role):")
print(json.dumps(result, indent=2, ensure_ascii=False))

# Test invoice_count
result2 = get_invoice_stats(stat_type='invoice_count', user_role='staff')
print("\n📊 Invoice Count (staff role):")
print(json.dumps(result2, indent=2, ensure_ascii=False))

# Test customer access (denied)
result3 = get_invoice_stats(stat_type='total_revenue', user_role='customer')
print("\n❌ Total Revenue (customer role - should be denied):")
print(json.dumps(result3, indent=2, ensure_ascii=False))

print("\n✅ Test complete!")
