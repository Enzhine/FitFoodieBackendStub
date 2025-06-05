import os
import random

import uuid
import yaml
from flask import Flask, jsonify, request
from faker import Faker
import re

app = Flask(__name__)
fake = Faker()


def load_spec(path="recipe.yaml"):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


spec = load_spec()


def generate_from_schema(schema):
    if schema is None:
        return None

    # --- If enum is present
    if "enum" in schema:
        enum_values = schema.get("enum", [])
        if enum_values:
            return random.choice(enum_values)

    # --- Handle allOf
    if "allOf" in schema:
        combined = {}
        for sub_schema in schema["allOf"]:
            part = generate_from_schema(sub_schema)
            if isinstance(part, dict):
                combined.update(part)
        return combined

    # --- Разворачиваем $ref
    if "$ref" in schema:
        ref_path = schema["$ref"]
        parts = ref_path.lstrip("#/").split("/")
        ref_schema = spec
        for part in parts:
            ref_schema = ref_schema.get(part)
            if ref_schema is None:
                return None
        return generate_from_schema(ref_schema)

    # --- Обычные типы
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties", {})
        return {k: generate_from_schema(v) for k, v in props.items()}
    elif t == "array":
        item_schema = schema.get("items", {})
        return [generate_from_schema(item_schema) for _ in range(fake.random_int(min=1, max=3))]
    elif t == "string":
        fmt = schema.get("format")
        if fmt == "date":
            return fake.date()
        if fmt == "date-time":
            return fake.iso8601()
        return fake.word()
    elif t == "integer":
        minimum = schema.get("minimum", 0)
        maximum = schema.get("maximum", minimum + 100)
        return fake.random_int(min=minimum, max=maximum)
    elif t == "number":
        return fake.pyfloat(left_digits=2, right_digits=2)
    elif t == "boolean":
        return fake.boolean()
    else:
        return None


def to_flask_route(path):
    return re.sub(r"\{([^}]+)\}", r"<\1>", path)


custom_handlers = {}

def register_handler(operation_id):
    def decorator(func):
        custom_handlers[operation_id] = func
        return func
    return decorator


users_db = {}
active_tokens = {}

mock_products = [
    {
        "id": 1,
        "name": "Рис",
        "quant": 100,
        "unit": "g",
        "tags": [],
        "image": "rice.jpg"
    },
    {
        "id": 2,
        "name": "Курица",
        "quant": 150,
        "unit": "g",
        "tags": ["MEAT"],
        "image": "chicken.jpg"
    },
    {
        "id": 3,
        "name": "Сыр",
        "quant": 50,
        "unit": "g",
        "tags": ["MILK"],
        "image": "cheese.jpg"
    },
    {
        "id": 4,
        "name": "Лосось",
        "quant": 120,
        "unit": "g",
        "tags": ["FISH"],
        "image": "salmon.jpg"
    }
]

mock_dishes = [
    {
        "id": 1,
        "name": "Курица с рисом",
        "description": "Питательное блюдо с курицей и гарниром из риса",
        "productIds": [[1, 2], [300, 450]],
        "calories": 450,
        "cookMinutes": 30,
        "tags": ["MEAT"],
        "order": 1,
        "image": "rice_chicken.jpg",
        "props": [
            {"name": "Белки", "value": "35г"},
            {"name": "Жиры", "value": "20г"},
            {"name": "Углеводы", "value": "50г"},
            {"name": "Калорий", "value": "450"},
            {"name": "Время приготовления", "value": "30 минут"},
        ],
        "recipe": "1. Отварить рис.\n2. Обжарить курицу.\n3. Смешать.",
        "chefAdvice": "Используйте жасминовый рис для аромата."
    },
    {
        "id": 2,
        "name": "Сырный лосось",
        "description": "Сливочный лосось с сыром",
        "productIds": [[3, 4], [150, 240]],
        "calories": 600,
        "cookMinutes": 20,
        "tags": ["FISH", "MILK"],
        "order": 2,
        "image": "salmon_cheese.jpg",
        "props": [
            {"name": "Белки", "value": "45г"},
            {"name": "Жиры", "value": "35г"},
            {"name": "Углеводы", "value": "10г"},
        ],
        "recipe": "1. Запеките лосось. 2. Добавьте плавленый сыр. 3. Подавайте горячим.",
        "chefAdvice": "Добавьте немного лимона для баланса вкуса."
    }
]


images_dir = 'img'
images: dict[str, bytes] = dict()
for f_name in os.listdir(images_dir):
    with open(images_dir+'/'+f_name, mode='rb') as file:
        images[f_name] = file.read()


def is_dish_allowed(dish, user):
    if not user:
        return True
    for tag in dish.get("tags", []):
        if tag == "MEAT" and user.get("meatPreference") == "EXCL":
            return False
        if tag == "FISH" and user.get("fishPreference") == "EXCL":
            return False
        if tag == "MILK" and user.get("milkPreference") == "EXCL":
            return False
    return True

'''
ПОЛУЧЕНИЕ ИЗОБРАЖЕНИЯ ПРОДУКТА
'''
@register_handler("productImage")
def get_product_image(id: int):
    product = next((d for d in mock_products if str(d["id"]) == str(id)), None)
    if product and product["image"] in images:
        return images[product["image"]]
    return jsonify({"error": "Image not found"}), 404

'''
ПОЛУЧЕНИЕ ИЗОБРАЖЕНИЯ БЛЮДА
'''
@register_handler("dishImage")
def get_dish_image(id):
    print('123!!!')
    dish = next((d for d in mock_dishes if str(d["id"]) == str(id)), None)
    if dish and dish["image"] in images:
        print(dish, dish["image"])
        return images[dish["image"]]
    print('!!!321')
    return jsonify({"error": "Image not found"}), 404

'''
ЗАРЕГИСТРИРОВАТЬ ПОЛЬЗОВАТЕЛЯ
'''
@register_handler("authRegister")
def register():
    data = request.json
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if username in users_db:
        return jsonify({"error": "User already exists"}), 409

    user_id = len(users_db) + 1
    user = {
        "id": user_id,
        "username": username,
        "email": email,
        "password_hash": password,
        "meatPreference": "LIKE",
        "fishPreference": "LIKE",
        "milkPreference": "LIKE"
    }

    users_db[email] = user
    return jsonify({"message": "User registered successfully"}), 201

'''
ЗАЛОГИНИТЬ ПОЛЬЗОВАТЕЛЯ
'''
@register_handler("authLogin")
def login_handler():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = users_db.get(email)
    if not user or not (user["password_hash"] == password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = str(uuid.uuid4())
    active_tokens[token] = user

    return jsonify({
        "token": token,
    }), 200

'''
ПОЛУЧЕНИЕ АВТОРИЗОВАННОГО ПОЛЬЗОВАТЕЛЯ
'''
def get_authenticated_user():
    print(request.headers)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        return active_tokens.get(token)
    return None

'''
ПОЛУЧЕНИЕ ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ
'''
@register_handler("usersMe")
def get_current_user():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "meatPreference": user["meatPreference"],
        "fishPreference": user["fishPreference"],
        "milkPreference": user["milkPreference"]
    }), 200

'''
ПОЛУЧЕНИЕ ВСЕХ ПРОДУКТОВ
'''
@register_handler("products")
def get_products():
    return jsonify(mock_products), 200

'''
ПОЛУЧЕНИЕ ИЗОБРАЖЕНИЯ ПРОДУКТА
'''
@register_handler("productImage")
def get_product_image(id):
    product = next((p for p in mock_products if str(p["id"]) == str(id)), None)
    if product and product["image"] in images:
        return images[product["image"]]
    return jsonify({"error": "Image not found"}), 404

'''
ПОЛУЧЕНИЕ ВСЕХ БЛЮД
'''
@register_handler("dishesAll")
def get_dishes():
    query = request.args
    user = get_authenticated_user()

    search = query.get("search", "").lower()
    min_cal = float(query.get("minCalories", 0))
    max_cal = float(query.get("maxCalories", 100_000))
    min_time = int(query.get("minCookingTime", 0))
    max_time = int(query.get("maxCookingTime", 100_000))
    page = int(query.get("page", 0))
    size = int(query.get("size", 20))

    filtered = []
    for dish in mock_dishes:
        if not is_dish_allowed(dish, user):
            continue
        if search and search not in dish["name"].lower():
            continue
        if not (min_cal <= dish["calories"] <= max_cal):
            continue
        if not (min_time <= dish["cookMinutes"] <= max_time):
            continue
        filtered.append(dish)

    total_elements = len(filtered)
    total_pages = (total_elements + size - 1) // size
    start = page * size
    end = start + size

    content = [{
        "id": d["id"],
        "name": d["name"],
        "calories": d["calories"],
        "cookMinutes": d["cookMinutes"],
        "tags": d["tags"],
        "order": d.get("order", 1)
    } for d in filtered[start:end]]

    return jsonify({
        "content": content,
        "totalPages": total_pages,
        "totalElements": total_elements,
        "pageNumber": page,
        "pageSize": size
    }), 200

'''
ПОЛУЧЕНИЕ БЛЮДА
'''
@register_handler("dish")
def get_dish(id):
    dish = next((d for d in mock_dishes if str(d["id"]) == str(id)), None)
    if not dish:
        return jsonify({"error": "Dish not found"}), 404

    dto = {
        "id": dish["id"],
        "name": dish["name"],
        "calories": dish["calories"],
        "cookMinutes": dish["cookMinutes"],
        "tags": dish["tags"],
        "order": dish.get("order", 1),
        "props": dish.get("props", []),
        "recipe": dish.get("recipe", ""),
        "chefAdvice": dish.get("chefAdvice", "")
    }

    return jsonify(dto), 200

'''
ПОЛУЧЕНИЕ ПРОДУКТОВ БЛЮДА
'''
@register_handler("dishProducts")
def get_dish_products(id):
    dish = next((d for d in mock_dishes if str(d["id"]) == str(id)), None)
    if not dish or "productIds" not in dish or len(dish["productIds"]) < 2:
        return jsonify({"error": "Invalid dish data"}), 404

    product_ids = dish["productIds"][0]
    quantities = dish["productIds"][1]

    if len(product_ids) != len(quantities):
        return jsonify({"error": "Mismatched product and quantity lengths"}), 400

    result = []
    for pid, qty in zip(product_ids, quantities):
        result.append({
            "productId": pid,
            "quantity": qty
        })

    return jsonify(result), 200

'''
ОБНОВЛЕНИЕ ПИЩЕВЫХ ПРЕДПОЧТЕНИЙ
'''
@register_handler("usersPreferences")
def update_preferences():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}

    for pref in ["meatPreference", "fishPreference", "milkPreference"]:
        if pref in data:
            if data[pref] in ["LIKE", "RARE", "EXCL"]:
                user[pref] = data[pref]
            else:
                return jsonify({"error": f"Invalid value for {pref}"}), 400

    return jsonify({"message": "Preferences updated"}), 200

'''
ПОЛУЧАЕМ БЛЮДА ПО СТРАНИЧКАМ
'''
@register_handler("dishesSuggest")
def suggest_dishes():
    request_data = request.json or []
    user = get_authenticated_user()

    available = {item["productId"]: item["quantity"] for item in request_data}
    result = []

    for dish in mock_dishes:
        if not is_dish_allowed(dish, user):
            continue

        missing = 0
        possible = float("inf")

        for pid, needed in zip(dish["productIds"][0], dish["productIds"][1]):
            have = available.get(pid, 0)
            if have < needed:
                missing += needed - have
            else:
                possible = min(possible, have // needed)

        dish_copy = {
            "id": dish["id"],
            "name": dish["name"],
            "calories": dish["calories"],
            "cookMinutes": dish["cookMinutes"],
            "tags": dish["tags"],
            "order": -missing if missing > 0 else possible
        }

        result.append(dish_copy)

    return jsonify(result), 200

# --- Генерация маршрутов
for path, methods in spec.get("paths", {}).items():
    flask_path = to_flask_route(path)
    for method, operation in methods.items():
        operation_id = operation.get("operationId") or f"{method}_{path}"
        endpoint = re.sub(r"[^a-zA-Z0-9_]", "_", operation_id)

        responses = operation.get("responses", {})
        resp = responses.get("200") or responses.get("201")
        if not resp:
            continue

        content = resp.get("content", {})
        app_json = content.get("application/json", {})
        schema = app_json.get("schema")

        if operation_id in custom_handlers:
            handler = custom_handlers[operation_id]
        else:
            def make_handler(schema):
                def handler(**kwargs):
                    if schema:
                        return jsonify(generate_from_schema(schema))
                    return jsonify({})
                return handler

            handler = make_handler(schema)

        app.add_url_rule(
            rule=flask_path,
            endpoint=endpoint,
            view_func=handler,
            methods=[method.upper()]
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
