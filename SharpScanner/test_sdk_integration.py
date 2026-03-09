"""
Test script to verify SDK integration works
Tests both Kalshi official SDK and Polymarket CLOB client
"""

# Test 1: Kalshi Official SDK
print("=" * 80)
print("TEST 1: KALSHI OFFICIAL SDK")
print("=" * 80)

try:
    from kalshi_python import Configuration, KalshiClient
    print("✅ kalshi-python SDK imported successfully")
    
    # Setup config
    config = Configuration()
    config.host = "https://api.elections.kalshi.com/trade-api/v2"
    config.api_key_id = "4c67f48e-3c17-43e5-8eaa-8be0bf26ac37"
    
    # Load private key (from existing code)
    PRIVATE_KEY_BLOCK = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAqMO3W9q3hIXHdKEvZ/J9q/hFvIiFdYOnpgcbOrM5+L26BDjM
7Ih1CKQT6mcQ627dvuQGMVFZbLBRf/xPS3Om0MuEF1AIAjApACYfQ/nqMVZZnR+u
ay+VOMLl917ryiJXXMsX8z+Zf2fkDzelonYYO/1djVCVF4HtUhHTbV9g7G0HuNG0
mdQTKdI1EU2KpJMZEIRIjJGS3y6GrV3GHT9NAy+WIUTJqUnBrAtBG96K+4OnekUt
ttiqPcWlpDirllt7UZB8KERK1PhOkLvE8hdLWb62Qx5vQdSYU0+gt4WDvx7B1tgH
JmUlDAyzfkAJhWgBHZF4WZEqCuJch6jaaq0mewIDAQABAoIBAAIohp2lr7dvco6R
t2+iLCNGv2xtHotA6Vr4E3Ck4v/phUB/JFM08LI6TvZS5kHH+nrfftHsEyEhJUdm
LITdgn3t9YYT8c0h7x1xzRTZCzqzurjO/HzGJyevHCBew6/H9PARS7eLrWS7BLGB
INOWW1b8fqyCIghHXBoOKk55ostDPhb0tDMo/xj93w7ZJHbrpfQVkXd2LakxC5sk
QN/nYMtmwPMEZT622TLrU2NtaSY2RaA2kks1Qqoq/DvKpQmrYGyOOdi6+/N3hT6Y
AwN/om2qtjwC6YmnVmOo9/GgGmpnDTWFh2AnLPlSrjVhJ+x9laXiJ+WHStrAaq8g
a2G77VkCgYEA3MjDLs/PP+Y9+NpRdaREl08orewWf7G1agZXX6BqHrtkpg+F6NLo
m/3PIz07gEywvYM4FaBkn889layuWHN0a8uXv9APLqTq2Jc8cJ/VYvqFcel8df7q
tjPiKfhf0icXVIYHqKSQ3a0d4uAYswIhdCFjRMjx9cF3Gq4MbTUtDx8CgYEAw67X
7sUovpXLdeWtW7ZmacBIPKFf5a91/QxMbYIfXP4O/J5cDgIz+BEfnfeGom0Gtpc2
6kCQtBST+5Ig9Ri9fhy/D05PhMVxHxu3IEjleEWRWa8ylUw+6aDpMxt2UQ1ZRZu5
4q8gmWy9TXrJQgaLqwlq9p4XNhsgunZxd2qCKSUCgYApUoIFfuuBQCyVKPdaF1an
Iy+v7aIAYFhd8bXktfdmrRgXZIxhmSfkGkrsg4dhafkiXy7eDVkH+BfErb8r2uAN
VNugEObmigNSamvrgF7F2bGkMlkTFJUFaQyJYm08vghFz5gbXkGm28HeNqcoydtN
CvqzYxC2OHF8UtsMjYlTbQKBgCRBzjKoh08g1C0JHGDk3/7yKLBLOkiFhTgYwkR8
GrGRRVebQ/U4hUaObaxIQ8LurpLAW+V1hxpGwdCYF9Ex/1JRozkDyooQR1B7QygR
OataQH88jgPJt9J0BSF6EicccRELtJqC1mh3FHA5svav3csYGKCPVD+rMRo7ffSh
YHKdAoGALIvT1Pc2e3k1vc3GhkNXKvHUs59DQTetBPupHpUy8DG50djN04OeG7dM
j3EW8ppWqWb9hIuBmhk4qg6zuTtoz8mu8zvC57gtfv+y2H9gcKTa9FL/XL644Tkh
homIQ9oXbpR/hpG1+t9b2EfUQfVLyYdFRr62EWZRwTVx3cy/je8=
-----END RSA PRIVATE KEY-----
"""
    config.private_key_pem = PRIVATE_KEY_BLOCK.strip()
    
    # Create client
    client = KalshiClient(config)
    print("✅ KalshiClient created successfully")
    
    # Test: Get markets
    try:
        markets_response = client.get_markets(limit=10, status="open")
        print(f"✅ Fetched {len(markets_response.markets)} markets using SDK")
        if markets_response.markets:
            print(f"   Sample: {markets_response.markets[0].title}")
    except Exception as e:
        print(f"❌ Error fetching markets: {e}")
        
except ImportError as e:
    print(f"❌ kalshi-python SDK not installed: {e}")
    print("   Install with: pip install kalshi-python")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Polymarket CLOB Client
print("\n" + "=" * 80)
print("TEST 2: POLYMARKET CLOB CLIENT")
print("=" * 80)

try:
    from py_clob_client.client import ClobClient
    print("✅ py-clob-client imported successfully")
    
    # Setup client
    host = "https://clob.polymarket.com"
    client = ClobClient(host)
    print("✅ ClobClient created successfully")
    
    # Test: Get book (need a token_id - this is just a test)
    # In production, we'd get token_id from Gamma API first
    print("✅ CLOB client ready (need token_id to test book fetch)")
    
except ImportError as e:
    print(f"❌ py-clob-client not installed: {e}")
    print("   Install with: pip install py-clob-client")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: aiopolymarket (async wrapper)
print("\n" + "=" * 80)
print("TEST 3: AIOPOLYMARKET (ASYNC WRAPPER)")
print("=" * 80)

try:
    import aiopolymarket
    print("✅ aiopolymarket imported successfully")
    print("   This is an async wrapper for faster fetching")
except ImportError as e:
    print(f"❌ aiopolymarket not installed: {e}")
    print("   Install with: pip install aiopolymarket")
    print("   Note: May need to check GitHub for correct package name")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("If all tests pass, we can refactor to use official SDKs")
print("This will make the code cleaner and potentially faster")

