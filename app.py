
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

# 🔥 Gemini API Setup
genai.configure(api_key="AIzaSyDgcB4xJ3642uoqTOZ4X2gfMjSdGDgz1rM")

# 🏪 3 Independent AI Shopkeepers
gemini_shop1 = genai.GenerativeModel("gemini-2.0-flash")
gemini_shop2 = genai.GenerativeModel("gemini-2.0-flash")
gemini_shop3 = genai.GenerativeModel("gemini-2.0-flash")

app = Flask(__name__)

# 📌 Shop Details
shops = {
    1: {"name": "ElectroMart", "ai": gemini_shop1},
    2: {"name": "CircuitWorld", "ai": gemini_shop2},
    3: {"name": "WireHub", "ai": gemini_shop3}
}

# 🎲 Shared Market Context (Common Data)
market_context = {
    "prices": {"Bulb": 50, "Wire": 20, "Resistor": 10, "Capacitor": 30, "Battery": 100},
    "demand": 1.0,  # 1 = Normal Demand, >1 = High Demand, <1 = Low Demand
    "transactions": []  # Past negotiations
}

# 🎒 User Inventory (Initial Goods)
user_inventory = {
    "Bulb": {"quantity": 5, "price": 50},
    "Wire": {"quantity": 10, "price": 20},
    "Resistor": {"quantity": 15, "price": 10},
    "Capacitor": {"quantity": 8, "price": 30},
    "Battery": {"quantity": 3, "price": 100}
}

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/inventory')
def inventory():
    """Returns user inventory in readable format"""
    items = ", ".join([f"{k} (x{v['quantity']}) - ₹{v['price']}" for k, v in user_inventory.items()])
    return jsonify({"items": items})

def ai_response(shop_id, user_message):
    """AI Response with Shared Market Context"""
    global market_context

    # Get specific AI shopkeeper
    shop = shops.get(shop_id)
    if not shop:
        return "Invalid shop selection."

    ai_model = shop["ai"]  # Unique AI per shop

    # 📌 AI Awareness (Each AI has the same market data but thinks differently)
    context = f"""You are an independent AI shopkeeper in a competitive electronics marketplace.
    - Your shop: {shop['name']}
    - Competing shops: {', '.join([s['name'] for sid, s in shops.items() if sid != shop_id])}
    - Current Market Prices: {market_context['prices']}
    - Demand Factor: {market_context['demand']}
    - Recent Transactions: {market_context['transactions'][-3:]} (last 3 deals)
    - You should negotiate prices based on market conditions, competition, and user strategy."""

    # ❌ OLD (Incorrect) format that caused KeyError
    # response = ai_model.generate_content([
    #     {"role": "system", "content": context},
    #     {"role": "user", "content": user_message}
    # ])

    # ✅ NEW (Corrected) format for Gemini API
    response = ai_model.generate_content(f"{context}\n\nUser: {user_message}\nAI:")

    return response.text if response else "I am not sure what you want to trade."


@app.route('/chat', methods=['POST'])
def chat():
    """Handles user chat with AI shopkeepers"""
    data = request.json
    shop_id = data.get("shop_id")
    user_message = data.get("user_message")

    if shop_id not in shops:
        return jsonify({"error": "Invalid shop ID"}), 400

    reply = ai_response(shop_id, user_message)

    # 📌 Save this negotiation in market context
    market_context["transactions"].append({"shop": shops[shop_id]["name"], "message": user_message, "reply": reply})

    return jsonify({"shop_name": shops[shop_id]["name"], "reply": reply})

if __name__ == '__main__':
    app.run(debug=True)
