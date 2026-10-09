def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_public_menu_success(client):
    response = client.get("/api/v1/public/outlets/test-camp/menu")
    assert response.status_code == 200
    data = response.json()

    assert data["outlet_name"] == "Test Camp Outlet"
    assert data["public_slug"] == "test-camp"
    assert data["currency"] == "INR"

    # Only active categories should be returned (cat1)
    categories = data["categories"]
    assert len(categories) == 1
    assert categories[0]["name"] == "Starters"

    # Only active items should be returned (item1 and item_unavail, item_hidden excluded)
    items = categories[0]["items"]
    assert len(items) == 2
    item_names = [i["name"] for i in items]
    assert "Fried Fish" in item_names
    assert "Seasonal Fruit Bowl" in item_names
    assert "Deleted Dish" not in item_names

    # Check unavailable flag
    fruit_item = next(i for i in items if i["name"] == "Seasonal Fruit Bowl")
    assert fruit_item["is_available"] is False

    # Price verification
    fish_item = next(i for i in items if i["name"] == "Fried Fish")
    assert float(fish_item["price"]) == 250.0


def test_get_public_menu_not_found(client):
    response = client.get("/api/v1/public/outlets/non-existent-slug/menu")
    assert response.status_code == 404
    error = response.json()["detail"]["error"]
    assert error["code"] == "OUTLET_NOT_FOUND"


def test_generate_qr_code_success(client):
    response = client.get("/api/v1/public/outlets/test-camp/qr")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # PNG signature check (first 4 bytes are \x89PNG)
    assert response.content[:4] == b"\x89PNG"


def test_generate_qr_code_download(client):
    response = client.get("/api/v1/public/outlets/test-camp/qr?download=true")
    assert response.status_code == 200
    assert "attachment; filename=\"test-camp-qr-code.png\"" in response.headers["content-disposition"]
