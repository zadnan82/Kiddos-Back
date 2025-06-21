# Script to fix the encryption storage issue
# Run this inside your API container: docker-compose exec api python fix_encryption.py

import json
import binascii
from app.database import SessionLocal
from app.models import ContentSession
from app.auth import field_encryption


def fix_hex_encoded_content(session_id):
    """Fix a specific session with hex-encoded content"""

    db = SessionLocal()
    try:
        session = (
            db.query(ContentSession).filter(ContentSession.id == session_id).first()
        )

        if not session:
            print(f"❌ Session not found: {session_id}")
            return False

        if not session.generated_content:
            print(f"❌ No content to fix for session: {session_id}")
            return False

        print(f"Fixing session: {session.generated_title}")
        content = session.generated_content

        try:
            # Handle hex-encoded content
            if isinstance(content, str) and ("\\x" in content or len(content) > 1000):
                print("Detected hex-encoded content, converting...")

                # Clean up the hex string
                hex_content = content
                if hex_content.startswith("\\\\x"):
                    hex_content = hex_content[4:]  # Remove \\x prefix
                elif hex_content.startswith("\\x"):
                    hex_content = hex_content[2:]  # Remove \x prefix

                # Convert hex to bytes
                content_bytes = binascii.unhexlify(hex_content)
                print(f"Converted hex string to {len(content_bytes)} bytes")

                # Decrypt
                decrypted = field_encryption.decrypt(content_bytes)

                if decrypted:
                    # Parse and display content
                    parsed = json.loads(decrypted)

                    print("\n" + "=" * 60)
                    print(f"RECOVERED CONTENT: {parsed.get('title', 'No title')}")
                    print("=" * 60)
                    print(parsed.get("content", "No content"))

                    if "questions" in parsed:
                        print("\nQUESTIONS:")
                        for i, q in enumerate(parsed["questions"], 1):
                            print(f"{i}. {q}")

                    print(f"\nMetadata: {parsed.get('metadata', {})}")
                    print("\n✅ Successfully recovered content!")

                    # Optionally fix the storage by re-encrypting properly
                    print(
                        "\nWould you like to fix the storage? (This will re-encrypt properly)"
                    )
                    # For now, just show the content - implement fix logic as needed

                    return True
                else:
                    print("❌ Decryption returned empty content")
                    return False

        except Exception as e:
            print(f"❌ Failed to fix content: {e}")
            import traceback

            traceback.print_exc()
            return False

    finally:
        db.close()


def create_test_content():
    """Create test content to verify the fix works"""

    print("\nCreating test content to verify encryption works...")

    # Simulate proper content generation
    test_content = {
        "title": "The Magical Forest Adventure",
        "content": "Once upon a time, in a magical forest filled with talking animals, there lived a brave little rabbit named Luna. Luna loved to explore and help her friends whenever they needed it. One sunny morning, she discovered a hidden path that led to the most beautiful garden she had ever seen, filled with flowers that sparkled like diamonds in the sunlight.",
        "questions": [
            "What was the rabbit's name?",
            "What did Luna love to do?",
            "What did the flowers look like in the garden?",
        ],
        "metadata": {
            "word_count": 65,
            "reading_level": "easy",
            "age_group": 5,
            "content_type": "story",
        },
    }

    try:
        # Convert to JSON
        json_content = json.dumps(test_content, ensure_ascii=False)
        print(f"JSON content length: {len(json_content)}")

        # Encrypt properly
        encrypted_content = field_encryption.encrypt(json_content)
        print(f"Encrypted content type: {type(encrypted_content)}")
        print(f"Encrypted content length: {len(encrypted_content)}")

        # Verify decryption works
        decrypted_content = field_encryption.decrypt(encrypted_content)
        parsed_content = json.loads(decrypted_content)

        print("✅ Test encryption/decryption successful!")
        print(f"Test title: {parsed_content['title']}")

        # This is what should be stored in the database
        print(f"\nFor proper storage, worker should store:")
        print(f"- Type: {type(encrypted_content)} (should be bytes)")
        print(f"- Length: {len(encrypted_content)}")
        print(f"- NOT as hex string representation")

        return True

    except Exception as e:
        print(f"❌ Test content creation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_worker_code_recommendations():
    """Provide specific recommendations for fixing the worker code"""

    print("\n" + "=" * 60)
    print("WORKER CODE FIX RECOMMENDATIONS")
    print("=" * 60)

    print("""
The issue is in your worker's generate_content_task function. Here's what to check:

1. CURRENT PROBLEM:
   - Encrypted bytes are being converted to string representation
   - Database stores hex-encoded string instead of raw bytes
   - Decryption fails because it expects bytes, not hex string

2. WORKER CODE TO CHECK:
   Look for code like this in your worker:
   
   # WRONG - converts bytes to string representation
   encrypted_content = field_encryption.encrypt(json_content)
   session.generated_content = str(encrypted_content)  # ← PROBLEM
   
   # CORRECT - store bytes directly  
   encrypted_content = field_encryption.encrypt(json_content)
   session.generated_content = encrypted_content  # ← SOLUTION

3. DATABASE SCHEMA:
   Ensure your generated_content column can store binary data:
   - PostgreSQL: BYTEA type
   - SQLite: BLOB type
   - Should NOT be TEXT/VARCHAR

4. QUICK FIX FOR EXISTING DATA:
   - Option A: Add hex decoding logic to your decryption function
   - Option B: Regenerate content with fixed worker
   - Option C: Write migration script to fix existing records

5. TEST THE FIX:
   - Generate new content after fixing worker
   - Verify it can be decrypted properly
   - Check that content_bytes type is preserved in database
""")


if __name__ == "__main__":
    print("FIXING ENCRYPTION STORAGE ISSUE")
    print("=" * 50)

    # Try to fix the specific problematic session
    session_id = "89373415-3c3a-4cc9-8110-ae632cd08426"
    success = fix_hex_encoded_content(session_id)

    if success:
        print("\n✅ Successfully recovered content from problematic session!")
    else:
        print("\n❌ Could not recover content from problematic session")

    # Create test content to verify system works
    test_success = create_test_content()

    if test_success:
        print("\n✅ Encryption system is working for new content")
    else:
        print("\n❌ Encryption system has fundamental issues")

    # Provide fix recommendations
    check_worker_code_recommendations()
