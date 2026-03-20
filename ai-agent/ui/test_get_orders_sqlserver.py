#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test updated get_orders function"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from data_provider import get_orders

print("\n" + "="*60)
print("🧪 Testing updated get_orders() from SQL Server")
print("="*60)

result = get_orders(limit=3, user_role='customer')

print("\nResult:")
import json
print(json.dumps(result, indent=2, ensure_ascii=False))

print("\n✅ Done!")
