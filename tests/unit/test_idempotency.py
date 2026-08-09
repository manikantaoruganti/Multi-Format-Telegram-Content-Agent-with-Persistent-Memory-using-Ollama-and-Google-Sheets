import pytest
import aiosqlite
from datetime import datetime
from app.database.idempotency_store import IdempotencyStore
from app.database.style_memory import StyleMemory
from app.services.idempotency_service import IdempotencyService
from app.utils.hashing import generate_sha256

@pytest.fixture
async def in_memory_db():
    """Fixture for an in-memory SQLite database for testing."""
    async with aiosqlite.connect(":memory:") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_styles (
                user_id INTEGER PRIMARY KEY,
                style_prompt TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_generations (
                generation_key TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                source_identifier TEXT NOT NULL,
                style_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()
        yield db

@pytest.fixture
def idempotency_store(in_memory_db):
    return IdempotencyStore(":memory:") # Path doesn't matter for in-memory fixture

@pytest.fixture
def style_memory(in_memory_db):
    return StyleMemory(":memory:") # Path doesn't matter for in-memory fixture

@pytest.fixture
def idempotency_service(idempotency_store, style_memory):
    return IdempotencyService(idempotency_store, style_memory)

@pytest.mark.asyncio
async def test_idempotency_store_record_and_check(idempotency_store):
    key = "test_key_123"
    user_id = 1
    source_id = "source_abc"
    style_hash = "style_xyz"

    assert not await idempotency_store.check_generation_exists(key)
    await idempotency_store.record_generation(key, user_id, source_id, style_hash)
    assert await idempotency_store.check_generation_exists(key)

@pytest.mark.asyncio
async def test_idempotency_service_generate_key_default_style(idempotency_service):
    user_id = 101
    source_identifier = "http://example.com/article1"
    
    # No style set for user 101
    generation_key, style_hash = await idempotency_service.generate_generation_key(user_id, source_identifier)
    
    expected_style_hash = generate_sha256("default_style_no_style_set")
    expected_generation_identity_string = f"{user_id}-{source_identifier}-{expected_style_hash}"
    expected_generation_key = generate_sha256(expected_generation_identity_string)

    assert style_hash == expected_style_hash
    assert generation_key == expected_generation_key

@pytest.mark.asyncio
async def test_idempotency_service_generate_key_with_custom_style(idempotency_service, style_memory):
    user_id = 102
    source_identifier = "http://example.com/article2"
    custom_style = "witty and informal"
    await style_memory.set_style(user_id, custom_style)

    generation_key, style_hash = await idempotency_service.generate_generation_key(user_id, source_identifier)

    expected_style_hash = generate_sha256(custom_style)
    expected_generation_identity_string = f"{user_id}-{source_identifier}-{expected_style_hash}"
    expected_generation_key = generate_sha256(expected_generation_identity_string)

    assert style_hash == expected_style_hash
    assert generation_key == expected_generation_key

@pytest.mark.asyncio
async def test_idempotency_service_check_and_record_new_generation(idempotency_service):
    user_id = 201
    source_identifier = "source_new"
    style_hash = generate_sha256("style_new")
    generation_key = generate_sha256(f"{user_id}-{source_identifier}-{style_hash}")

    is_new = await idempotency_service.check_and_record_generation(generation_key, user_id, source_identifier, style_hash)
    assert is_new is True
    assert await idempotency_service.idempotency_store.check_generation_exists(generation_key)

@pytest.mark.asyncio
async def test_idempotency_service_check_and_record_duplicate_generation(idempotency_service):
    user_id = 202
    source_identifier = "source_duplicate"
    style_hash = generate_sha256("style_duplicate")
    generation_key = generate_sha256(f"{user_id}-{source_identifier}-{style_hash}")

    # Record once
    await idempotency_service.idempotency_store.record_generation(generation_key, user_id, source_identifier, style_hash)

    # Try to record again
    is_new = await idempotency_service.check_and_record_generation(generation_key, user_id, source_identifier, style_hash)
    assert is_new is False
    assert await idempotency_service.idempotency_store.check_generation_exists(generation_key)

@pytest.mark.asyncio
async def test_idempotency_service_same_source_same_user_same_style_is_duplicate(idempotency_service, style_memory):
    user_id = 301
    source_identifier = "http://example.com/article_A"
    style_prompt = "formal and academic"
    await style_memory.set_style(user_id, style_prompt)

    # First processing
    gen_key1, style_hash1 = await idempotency_service.generate_generation_key(user_id, source_identifier)
    is_new1 = await idempotency_service.check_and_record_generation(gen_key1, user_id, source_identifier, style_hash1)
    assert is_new1 is True

    # Second processing with same parameters
    gen_key2, style_hash2 = await idempotency_service.generate_generation_key(user_id, source_identifier)
    is_new2 = await idempotency_service.check_and_record_generation(gen_key2, user_id, source_identifier, style_hash2)
    assert is_new2 is False # Should be a duplicate

    assert gen_key1 == gen_key2
    assert style_hash1 == style_hash2

@pytest.mark.asyncio
async def test_idempotency_service_same_source_same_user_changed_style_is_new_generation(idempotency_service, style_memory):
    user_id = 302
    source_identifier = "http://example.com/article_B"
    
    # First style
    style_prompt1 = "witty and informal"
    await style_memory.set_style(user_id, style_prompt1)
    gen_key1, style_hash1 = await idempotency_service.generate_generation_key(user_id, source_identifier)
    is_new1 = await idempotency_service.check_and_record_generation(gen_key1, user_id, source_identifier, style_hash1)
    assert is_new1 is True

    # Change style
    style_prompt2 = "serious and analytical"
    await style_memory.set_style(user_id, style_prompt2)
    
    # Second processing with changed style
    gen_key2, style_hash2 = await idempotency_service.generate_generation_key(user_id, source_identifier)
    is_new2 = await idempotency_service.check_and_record_generation(gen_key2, user_id, source_identifier, style_hash2)
    assert is_new2 is True # Should be a new generation

    assert gen_key1 != gen_key2
    assert style_hash1 != style_hash2

@pytest.mark.asyncio
async def test_idempotency_service_different_user_same_source_same_style_is_new_generation(idempotency_service, style_memory):
    source_identifier = "http://example.com/article_C"
    style_prompt = "concise"

    # User 401
    user_id1 = 401
    await style_memory.set_style(user_id1, style_prompt)
    gen_key1, style_hash1 = await idempotency_service.generate_generation_key(user_id1, source_identifier)
    is_new1 = await idempotency_service.check_and_record_generation(gen_key1, user_id1, source_identifier, style_hash1)
    assert is_new1 is True

    # User 402
    user_id2 = 402
    await style_memory.set_style(user_id2, style_prompt) # Same style prompt
    gen_key2, style_hash2 = await idempotency_service.generate_generation_key(user_id2, source_identifier)
    is_new2 = await idempotency_service.check_and_record_generation(gen_key2, user_id2, source_identifier, style_hash2)
    assert is_new2 is True # Should be a new generation

    assert gen_key1 != gen_key2
    assert style_hash1 == style_hash2 # Style hash should be the same if prompt is identical
