# Complete debugging script for the encryption issue
# Run this inside your API container: docker-compose exec api python debug_encryption.py

import json
import binascii
from app.database import SessionLocal
from app.models import ContentSession
from app.auth import field_encryption
from app.config import settings


def debug_encryption_system():
    """Debug the entire encryption/decryption pipeline"""

    print("=" * 60)
    print("DEBUGGING ENCRYPTION SYSTEM")
    print("=" * 60)

    # 1. Check encryption configuration
    print("\n1. CHECKING ENCRYPTION CONFIGURATION:")
    print(f"   Encryption key configured: {bool(settings.ENCRYPTION_KEY)}")
    print(
        f"   Encryption key length: {len(settings.ENCRYPTION_KEY) if settings.ENCRYPTION_KEY else 0}"
    )
    print(
        f"   Encryption key preview: {settings.ENCRYPTION_KEY[:20] + '...' if settings.ENCRYPTION_KEY else 'None'}"
    )

    # 2. Test basic encryption/decryption
    print("\n2. TESTING BASIC ENCRYPTION/DECRYPTION:")
    test_data = "Hello World Test - Special chars: éñ中文"
    print(f"   Original data: {test_data}")

    try:
        encrypted = field_encryption.encrypt(test_data)
        print(f"   ✅ Encryption successful")
        print(f"   Encrypted type: {type(encrypted)}")
        print(f"   Encrypted length: {len(encrypted)}")
        print(
            f"   Encrypted preview: {encrypted[:50] if len(encrypted) > 50 else encrypted}"
        )

        decrypted = field_encryption.decrypt(encrypted)
        print(f"   ✅ Decryption successful")
        print(f"   Decrypted: {decrypted}")
        print(f"   Round trip match: {test_data == decrypted}")

    except Exception as e:
        print(f"   ❌ Basic encryption test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 3. Test JSON encryption/decryption
    print("\n3. TESTING JSON CONTENT ENCRYPTION:")
    json_data = {
        "title": "Test Story",
        "content": "Once upon a time, there was a happy elephant named Ellie who loved to dance.",
        "questions": ["What was the elephant's name?", "What did Ellie love to do?"],
        "metadata": {"word_count": 15, "test": True},
    }

    try:
        json_string = json.dumps(json_data, ensure_ascii=False)
        print(f"   JSON string length: {len(json_string)}")

        encrypted_json = field_encryption.encrypt(json_string)
        print(f"   ✅ JSON encryption successful")
        print(f"   Encrypted JSON type: {type(encrypted_json)}")
        print(f"   Encrypted JSON length: {len(encrypted_json)}")

        decrypted_json = field_encryption.decrypt(encrypted_json)
        parsed_json = json.loads(decrypted_json)
        print(f"   ✅ JSON decryption successful")
        print(f"   Parsed title: {parsed_json['title']}")

    except Exception as e:
        print(f"   ❌ JSON encryption test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


def analyze_stored_content(session_id):
    """Analyze the content stored in database for a specific session"""

    print(f"\n4. ANALYZING STORED CONTENT FOR SESSION: {session_id}")

    db = SessionLocal()
    try:
        session = (
            db.query(ContentSession).filter(ContentSession.id == session_id).first()
        )

        if not session:
            print(f"   ❌ Session not found: {session_id}")
            return False

        print(f"   Session found: {session.generated_title}")
        print(f"   Status: {session.status}")
        print(f"   Content type in DB: {type(session.generated_content)}")
        print(
            f"   Content length: {len(session.generated_content) if session.generated_content else 0}"
        )

        if not session.generated_content:
            print("   ❌ No content stored in database")
            return False

        # Check if content looks like hex
        content = session.generated_content
        print(f"   Content preview: {repr(content[:100])}")

        # Try different decoding strategies
        print("\n   TRYING DIFFERENT DECODING STRATEGIES:")

        # Strategy 1: Direct decryption (assuming it's bytes)
        try:
            if isinstance(content, str):
                # If it's a string, it might be base64 or hex encoded
                print("   Strategy 1: Treating as hex-encoded string...")

                # Remove any escape sequences
                if content.startswith("\\x"):
                    hex_content = content[2:]  # Remove \x prefix
                elif content.startswith("\\\\x"):
                    hex_content = content[4:]  # Remove \\x prefix
                else:
                    hex_content = content

                # Convert hex to bytes
                content_bytes = binascii.unhexlify(hex_content)
                print(f"   Converted to {len(content_bytes)} bytes")

                decrypted = field_encryption.decrypt(content_bytes)
                if decrypted:
                    parsed = json.loads(decrypted)
                    print(f"   ✅ Strategy 1 SUCCESS!")
                    print(f"   Title: {parsed.get('title', 'No title')}")
                    print(f"   Content length: {len(parsed.get('content', ''))}")
                    return True

            else:
                # It's already bytes
                print("   Strategy 1: Direct decryption of bytes...")
                decrypted = field_encryption.decrypt(content)
                parsed = json.loads(decrypted)
                print(f"   ✅ Strategy 1 SUCCESS!")
                print(f"   Title: {parsed.get('title', 'No title')}")
                return True

        except Exception as e:
            print(f"   Strategy 1 failed: {e}")

        # Strategy 2: Try as base64
        try:
            print("   Strategy 2: Treating as base64...")
            import base64

            if isinstance(content, str):
                content_bytes = base64.b64decode(content)
                decrypted = field_encryption.decrypt(content_bytes)
                parsed = json.loads(decrypted)
                print(f"   ✅ Strategy 2 SUCCESS!")
                print(f"   Title: {parsed.get('title', 'No title')}")
                return True
        except Exception as e:
            print(f"   Strategy 2 failed: {e}")

        # Strategy 3: Raw string as is
        try:
            print("   Strategy 3: Direct string decryption...")
            decrypted = field_encryption.decrypt(content)
            parsed = json.loads(decrypted)
            print(f"   ✅ Strategy 3 SUCCESS!")
            print(f"   Title: {parsed.get('title', 'No title')}")
            return True
        except Exception as e:
            print(f"   Strategy 3 failed: {e}")

        print("   ❌ All decoding strategies failed")
        return False

    finally:
        db.close()


def fix_worker_storage_issue():
    """Provide recommendations for fixing the worker storage issue"""

    print("\n5. RECOMMENDATIONS FOR FIXING WORKER STORAGE:")
    print("   Based on the analysis, here are the likely issues and fixes:")
    print()
    print("   ISSUE: Encrypted bytes being stored as hex string representation")
    print("   FIX: Ensure worker stores encrypted content as bytes, not string")
    print()
    print("   Check your worker code (generate_content_task) for:")
    print("   - Make sure field_encryption.encrypt() result is stored as-is (bytes)")
    print("   - Don't convert encrypted bytes to string representation")
    print("   - Database column should accept BYTEA (PostgreSQL) or BLOB (SQLite)")
    print()
    print("   IMMEDIATE FIX:")
    print("   1. Update worker to store encrypted content properly")
    print("   2. Or add decoding logic to handle hex-encoded content")
    print("   3. Test with new content generation")


if __name__ == "__main__":
    # Run basic encryption tests
    encryption_works = debug_encryption_system()

    if encryption_works:
        # Analyze the problematic session
        session_id = "89373415-3c3a-4cc9-8110-ae632cd08426"
        analyze_stored_content(session_id)

        # Provide fix recommendations
        fix_worker_storage_issue()
    else:
        print(
            "\n❌ Basic encryption system is not working. Check your encryption configuration first."
        )
