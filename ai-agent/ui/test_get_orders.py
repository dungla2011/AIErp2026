#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script to verify get_orders tool works"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from data_provider import get_orders
import json

print("\n" + "="*60)
print("🧪 Testing get_orders() tool")
print("="*60)

result = get_orders(limit=4, user_role='customer')
print("\n📦 Result:")
print(json.dumps(result, indent=2, ensure_ascii=False))

print("\n✅ Test complete!")
