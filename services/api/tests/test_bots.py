import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_bot_success(async_client: AsyncClient) -> None:
    payload = {
        "name": "Customer Support Assistant",
        "description": "Handles tier 1 support inquiries and pricing questions.",
        "system_prompt": "You are a professional customer support assistant.",
        "settings": {"temperature": 0.3, "model": "gpt-4o"},
    }
    response = await async_client.post("/api/v1/bots", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["system_prompt"] == payload["system_prompt"]
    assert data["settings"] == payload["settings"]
    assert data["status"] == "draft"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_bot_validation_error(async_client: AsyncClient) -> None:
    # Missing required 'name' field
    response = await async_client.post("/api/v1/bots", json={"description": "No name bot"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_bot_success(async_client: AsyncClient) -> None:
    create_res = await async_client.post(
        "/api/v1/bots",
        json={"name": "Sales Bot", "description": "Qualifies incoming leads."},
    )
    assert create_res.status_code == 201
    bot_id = create_res.json()["id"]

    response = await async_client.get(f"/api/v1/bots/{bot_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == bot_id
    assert data["name"] == "Sales Bot"


@pytest.mark.asyncio
async def test_get_bot_not_found(async_client: AsyncClient) -> None:
    random_id = str(uuid.uuid4())
    response = await async_client.get(f"/api/v1/bots/{random_id}")
    assert response.status_code == 404
    assert f"Bot with ID {random_id} not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_bots_pagination(async_client: AsyncClient) -> None:
    # Create 3 bots
    for i in range(3):
        await async_client.post(
            "/api/v1/bots",
            json={"name": f"Bot {i + 1}", "description": f"Description {i + 1}"},
        )

    # Page 1 (limit 2)
    res1 = await async_client.get("/api/v1/bots?skip=0&limit=2")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 3
    assert len(data1["items"]) == 2
    assert data1["skip"] == 0
    assert data1["limit"] == 2

    # Page 2 (skip 2, limit 2)
    res2 = await async_client.get("/api/v1/bots?skip=2&limit=2")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total"] == 3
    assert len(data2["items"]) == 1


@pytest.mark.asyncio
async def test_update_bot_success(async_client: AsyncClient) -> None:
    create_res = await async_client.post(
        "/api/v1/bots",
        json={"name": "Draft Bot", "status": "draft"},
    )
    bot_id = create_res.json()["id"]

    # Update name, system prompt, and status to ready
    update_payload = {
        "name": "Live Bot",
        "system_prompt": "Updated prompt",
        "status": "ready",
        "settings": {"temperature": 0.7},
    }
    patch_res = await async_client.patch(f"/api/v1/bots/{bot_id}", json=update_payload)
    assert patch_res.status_code == 200

    data = patch_res.json()
    assert data["name"] == "Live Bot"
    assert data["system_prompt"] == "Updated prompt"
    assert data["status"] == "ready"
    assert data["settings"] == {"temperature": 0.7}


@pytest.mark.asyncio
async def test_update_bot_not_found(async_client: AsyncClient) -> None:
    random_id = str(uuid.uuid4())
    patch_res = await async_client.patch(
        f"/api/v1/bots/{random_id}",
        json={"name": "New Name"},
    )
    assert patch_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_bot_success(async_client: AsyncClient) -> None:
    create_res = await async_client.post(
        "/api/v1/bots",
        json={"name": "Bot to Delete"},
    )
    bot_id = create_res.json()["id"]

    del_res = await async_client.delete(f"/api/v1/bots/{bot_id}")
    assert del_res.status_code == 204

    # Verify bot no longer exists
    get_res = await async_client.get(f"/api/v1/bots/{bot_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_bot_not_found(async_client: AsyncClient) -> None:
    random_id = str(uuid.uuid4())
    del_res = await async_client.delete(f"/api/v1/bots/{random_id}")
    assert del_res.status_code == 404
