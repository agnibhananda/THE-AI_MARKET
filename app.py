from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
import random
import time
import re
from datetime import datetime

# 🔥 Gemini API Setup
genai.configure(api_key="AIzaSyDgcB4xJ3642uoqTOZ4X2gfMjSdGDgz1rM")

# 🏪 3 Independent AI Shopkeepers
gemini_shop1 = genai.GenerativeModel("gemini-2.0-flash")
gemini_shop2 = genai.GenerativeModel("gemini-2.0-flash")
gemini_shop3 = genai.GenerativeModel("gemini-2.0-flash")

app = Flask(__name__)
app.secret_key = "ai_marketplace_secret_key"  # Required for session management

# 📌 Shop Details
shops = {
    1: {"name": "ElectroMart", "ai": gemini_shop1, "specialty": "Bulbs", "discount_rate": 0.95},
    2: {"name": "CircuitWorld", "ai": gemini_shop2, "specialty": "Resistors", "discount_rate": 0.90},
    3: {"name": "WireHub", "ai": gemini_shop3, "specialty": "Wires", "discount_rate": 0.93}
}

# 🎲 Shared Market Context (Common Data)
market_context = {
    "base_prices": {"Bulb": 50, "Wire": 20, "Resistor": 10, "Capacitor": 30, "Battery": 100},
    "current_prices": {"Bulb": 50, "Wire": 20, "Resistor": 10, "Capacitor": 30, "Battery": 100},
    "demand": {"Bulb": 1.0, "Wire": 1.0, "Resistor": 1.0, "Capacitor": 1.0, "Battery": 1.0},
    "volatility": {"Bulb": 0.15, "Wire": 0.10, "Resistor": 0.20, "Capacitor": 0.12, "Battery": 0.25},
    "transactions": [],  # Past negotiations
    "last_update": time.time(),
    "next_update": time.time() + 60  # Next scheduled update time
}

# Initial user data
def get_initial_user_data():
    return {
        "wallet": 1000,  # Starting with 1000 currency
        "inventory": {
            "Bulb": {"quantity": 5, "avg_buy_price": 50},
            "Wire": {"quantity": 10, "avg_buy_price": 20},
            "Resistor": {"quantity": 15, "avg_buy_price": 10},
            "Capacitor": {"quantity": 8, "avg_buy_price": 30},
            "Battery": {"quantity": 3, "avg_buy_price": 100}
        },
        "transaction_history": [],
        "profit_loss": 0
    }

def initialize_user_session():
    """Initialize user session data if not already set"""
    if 'user_data' not in session:
        session['user_data'] = get_initial_user_data()
    return session['user_data']

def update_market_prices():
    """Update market prices based on time passed and randomness"""
    global market_context
    
    current_time = time.time()
    time_diff = current_time - market_context["last_update"]
    
    # Only update prices if enough time has passed (every 60 seconds)
    if time_diff < 60:
        return
    
    for item in market_context["base_prices"]:
        # Random factor based on volatility
        random_factor = random.uniform(
            1 - market_context["volatility"][item], 
            1 + market_context["volatility"][item]
        )
        
        # Update demand randomly
        market_context["demand"][item] *= random.uniform(0.9, 1.1)
        # Keep demand within reasonable bounds
        market_context["demand"][item] = max(0.5, min(2.0, market_context["demand"][item]))
        
        # Calculate new price based on base price, demand and random factor
        new_price = market_context["base_prices"][item] * market_context["demand"][item] * random_factor
        
        # Ensure price doesn't change too drastically
        max_change = market_context["base_prices"][item] * 0.2  # Max 20% change
        old_price = market_context["current_prices"][item]
        if abs(new_price - old_price) > max_change:
            if new_price > old_price:
                new_price = old_price + max_change
            else:
                new_price = old_price - max_change
        
        # Ensure price stays positive and round to nearest integer
        market_context["current_prices"][item] = max(1, round(new_price))
    
    market_context["last_update"] = current_time
    market_context["next_update"] = current_time + 60  # Schedule next update

@app.route('/')
def home():
    initialize_user_session()
    update_market_prices()
    return render_template("index.html")

@app.route('/inventory')
def inventory():
    """Returns user inventory in readable format"""
    user_data = initialize_user_session()
    inventory_items = []
    
    for item, details in user_data["inventory"].items():
        if details['quantity'] > 0:  # Only show items with quantity > 0
            current_value = market_context["current_prices"][item] * details["quantity"]
            cost_basis = details["avg_buy_price"] * details["quantity"]
            profit_loss = current_value - cost_basis
            
            inventory_items.append(
                f"{item} (x{details['quantity']}) - Buy avg: ₹{details['avg_buy_price']}, Current: ₹{market_context['current_prices'][item]}, P/L: ₹{profit_loss}"
            )
    
    wallet_info = f"Wallet: ₹{user_data['wallet']}"
    market_info = "Market prices: " + ", ".join([f"{item}: ₹{price}" for item, price in market_context["current_prices"].items()])
    
    return jsonify({
        "wallet": wallet_info,
        "items": inventory_items,
        "market": market_info,
        "total_profit_loss": f"Total P/L: ₹{user_data['profit_loss']}"
    })

@app.route('/transaction-history')
def transaction_history():
    """Returns user transaction history"""
    user_data = initialize_user_session()
    
    return jsonify({
        "transactions": user_data["transaction_history"]
    })

def ai_response(shop_id, user_message):
    """AI Response with Shared Market Context"""
    global market_context
    update_market_prices()  # Update prices before AI response

    # Get specific AI shopkeeper
    shop = shops.get(shop_id)
    if not shop:
        return "Invalid shop selection."

    ai_model = shop["ai"]  # Unique AI per shop
    user_data = session.get('user_data', get_initial_user_data())

    # 📌 AI Awareness (Each AI has the same market data but thinks differently)
    context = f"""You are an independent AI shopkeeper in a competitive electronics marketplace.
    - Your shop: {shop['name']}
    - Your specialty: {shop['specialty']} (you offer better prices on this item)
    - Competing shops: {', '.join([s['name'] for sid, s in shops.items() if sid != shop_id])}
    - Current Market Prices: {market_context['current_prices']}
    - Demand Factors: {market_context['demand']}
    - Recent Transactions: {market_context['transactions'][-3:] if market_context['transactions'] else 'None'} (last 3 deals)
    
    IMPORTANT RULES:
    1. You should negotiate prices based on market conditions, competition, and user strategy.
    2. The user is trying to buy low and sell high to make profit.
    3. For item negotiations, always give a specific price in format ₹X (example: ₹50).
    4. If the user wants to buy or sell, use the format: "BUY/SELL [quantity] [item] for ₹[price]" to propose a deal.
    5. You can offer better prices (about {(1-shop['discount_rate'])*100}% off) on your specialty items.
    6. You may refuse deals that are too unfavorable to you.
    7. Keep negotiations conversational but business-focused.
    8. If user accepts your deal, confirm the transaction."""

    # ✅ Corrected format for Gemini API
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

    # Parse user message for transaction commands
    transaction_result = process_transaction(shop_id, user_message.lower())
    if transaction_result:
        return jsonify({"shop_name": shops[shop_id]["name"], "reply": transaction_result, "transaction": True})

    # Also check for special AI-proposed transaction acceptance
    if "accept" in user_message.lower() or "deal" in user_message.lower() or "ok" in user_message.lower():
        # Try to extract transaction from AI's previous message
        transaction_result = process_ai_transaction(shop_id, user_message.lower())
        if transaction_result:
            return jsonify({"shop_name": shops[shop_id]["name"], "reply": transaction_result, "transaction": True})

    reply = ai_response(shop_id, user_message)

    # 📌 Save this negotiation in market context
    market_context["transactions"].append({"shop": shops[shop_id]["name"], "message": user_message, "reply": reply})

    return jsonify({"shop_name": shops[shop_id]["name"], "reply": reply, "transaction": False})

def process_ai_transaction(shop_id, user_message):
    """Process transaction when user accepts an AI-proposed deal"""
    if not market_context["transactions"]:
        return None
    
    # Get the last transaction for this shop
    shop_transactions = [t for t in market_context["transactions"] if t["shop"] == shops[shop_id]["name"]]
    if not shop_transactions:
        return None
    
    last_ai_message = shop_transactions[-1]["reply"]
    
    # Look for BUY pattern in AI's message
    buy_match = re.search(r"(?i)(?:buy|purchase|I can sell you)\s+(\d+)\s+([A-Za-z]+)(?:s)?\s+(?:for|at)\s+₹(\d+)", last_ai_message)
    if buy_match and ("accept" in user_message or "deal" in user_message or "ok" in user_message or "yes" in user_message):
        quantity = int(buy_match.group(1))
        item_raw = buy_match.group(2)
        price = int(buy_match.group(3))
        
        # Try to match the item name with our known items
        item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
        if item:
            return handle_buy(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
    
    # Look for SELL pattern in AI's message
    sell_match = re.search(r"(?i)(?:sell|I'll buy|I will buy|I can buy)\s+(\d+)\s+([A-Za-z]+)(?:s)?\s+(?:for|at)\s+₹(\d+)", last_ai_message)
    if sell_match and ("accept" in user_message or "deal" in user_message or "ok" in user_message or "yes" in user_message):
        quantity = int(sell_match.group(1))
        item_raw = sell_match.group(2)
        price = int(sell_match.group(3))
        
        # Try to match the item name with our known items
        item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
        if item:
            return handle_sell(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
    
    return None

def process_transaction(shop_id, message):
    """Process potential transaction commands from user"""
    user_data = session.get('user_data', get_initial_user_data())
    shop = shops[shop_id]
    
    # Advanced pattern matching for buy commands
    buy_match = re.search(r"(?i)(?:buy|purchase|acquire)\s+(\d+)\s+([A-Za-z]+)(?:s)?\s+(?:for|at)?\s+(?:₹|rs|price\s+)?\s*(\d+)", message)
    if buy_match:
        try:
            quantity = int(buy_match.group(1))
            item_raw = buy_match.group(2)
            price = int(buy_match.group(3))
            
            # Try to match the item name with our known items
            item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
            
            if item and quantity > 0 and price > 0:
                return handle_buy(shop_id, item, quantity, price, user_data)
            else:
                return f"I couldn't understand that transaction. Please specify a valid item, quantity, and price."
        except Exception as e:
            return f"I couldn't process that transaction. Please try a format like 'buy 5 bulbs at ₹45'. Error: {str(e)}"
    
    # Advanced pattern matching for sell commands
    sell_match = re.search(r"(?i)(?:sell|offer|give)\s+(\d+)\s+([A-Za-z]+)(?:s)?\s+(?:for|at)?\s+(?:₹|rs|price\s+)?\s*(\d+)", message)
    if sell_match:
        try:
            quantity = int(sell_match.group(1))
            item_raw = sell_match.group(2)
            price = int(sell_match.group(3))
            
            # Try to match the item name with our known items
            item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
            
            if item and quantity > 0 and price > 0:
                return handle_sell(shop_id, item, quantity, price, user_data)
            else:
                return f"I couldn't understand that transaction. Please specify a valid item, quantity, and price."
        except Exception as e:
            return f"I couldn't process that transaction. Please try a format like 'sell 3 wires for ₹25'. Error: {str(e)}"
    
    return None

def handle_buy(shop_id, item, quantity, price, user_data):
    """Handle user buying from shop"""
    shop = shops[shop_id]
    current_market_price = market_context["current_prices"][item]
    shop_specialty_discount = 1.0
    
    # Apply specialty discount if applicable
    if shop["specialty"] == item:
        shop_specialty_discount = shop["discount_rate"]
    
    shop_price = round(current_market_price * shop_specialty_discount)
    
    # Shop decides whether to accept user's price
    if price >= shop_price * 0.9:  # Accept if user offers at least 90% of shop's price
        total_cost = price * quantity
        
        # Check if user has enough money
        if user_data["wallet"] < total_cost:
            return f"Sorry, you don't have enough funds for this purchase. You have ₹{user_data['wallet']} but need ₹{total_cost}."
        
        # Process the purchase
        user_data["wallet"] -= total_cost
        
        # Update inventory
        if item not in user_data["inventory"]:
            user_data["inventory"][item] = {"quantity": 0, "avg_buy_price": 0}
        
        # Calculate new average purchase price
        current_qty = user_data["inventory"][item]["quantity"]
        current_avg_price = user_data["inventory"][item]["avg_buy_price"]
        new_qty = current_qty + quantity
        
        if new_qty > 0:  # Avoid division by zero
            user_data["inventory"][item]["avg_buy_price"] = round(
                (current_qty * current_avg_price + quantity * price) / new_qty
            )
        
        user_data["inventory"][item]["quantity"] = new_qty
        
        # Record transaction
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        transaction = {
            "type": "buy",
            "item": item,
            "quantity": quantity,
            "price": price,
            "total": total_cost,
            "shop": shop["name"],
            "timestamp": timestamp
        }
        
        user_data["transaction_history"].append(transaction)
        session['user_data'] = user_data
        
        return f"Deal! You purchased {quantity} {item}(s) for ₹{price} each. Total cost: ₹{total_cost}. Your new wallet balance is ₹{user_data['wallet']}."
    else:
        return f"I can't accept that price. The current market price for {item} is ₹{current_market_price}, and the best I can offer is ₹{shop_price} per unit."

def handle_sell(shop_id, item, quantity, price, user_data):
    """Handle user selling to shop"""
    shop = shops[shop_id]
    current_market_price = market_context["current_prices"][item]
    
    # Check if user has enough of the item
    if item not in user_data["inventory"] or user_data["inventory"][item]["quantity"] < quantity:
        return f"You don't have enough {item}s to sell. You have {user_data['inventory'].get(item, {}).get('quantity', 0)} but want to sell {quantity}."
    
    # Shop decides whether to accept user's price
    if price <= current_market_price * 1.1:  # Accept if user asks at most 110% of market price
        total_earning = price * quantity
        
        # Process the sale
        user_data["wallet"] += total_earning
        user_data["inventory"][item]["quantity"] -= quantity
        
        # Calculate profit/loss
        avg_buy_price = user_data["inventory"][item]["avg_buy_price"]
        transaction_profit = (price - avg_buy_price) * quantity
        user_data["profit_loss"] += transaction_profit
        
        # Record transaction
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        transaction = {
            "type": "sell",
            "item": item,
            "quantity": quantity,
            "price": price,
            "total": total_earning,
            "profit": transaction_profit,
            "shop": shop["name"],
            "timestamp": timestamp
        }
        
        user_data["transaction_history"].append(transaction)
        session['user_data'] = user_data
        
        profit_message = ""
        if transaction_profit > 0:
            profit_message = f" You made a profit of ₹{transaction_profit}!"
        elif transaction_profit < 0:
            profit_message = f" You took a loss of ₹{abs(transaction_profit)}."
        
        return f"Deal! You sold {quantity} {item}(s) for ₹{price} each. Total received: ₹{total_earning}.{profit_message} Your new wallet balance is ₹{user_data['wallet']}."
    else:
        return f"I can't pay that much for {item}. The current market price is ₹{current_market_price}, and I can offer at most ₹{round(current_market_price * 0.95)} per unit."

@app.route('/market')
def market():
    """Returns current market prices"""
    update_market_prices()
    seconds_until_update = max(0, round(market_context["next_update"] - time.time()))
    return jsonify({
        "prices": market_context["current_prices"],
        "next_update_in": seconds_until_update
    })

@app.route('/reset')
def reset_game():
    """Reset user data to start fresh"""
    session['user_data'] = get_initial_user_data()
    return jsonify({"status": "success", "message": "Game reset successfully!"})

@app.route('/market-trend')
def market_trend():
    """Returns market trend data for charting"""
    # For now, return random trend data (in a real app, we would store historical data)
    data = {}
    for item in market_context["current_prices"]:
        # Generate fake historical data points for demonstration
        historical = []
        start_price = market_context["base_prices"][item]
        current_price = market_context["current_prices"][item]
        
        # Create 10 historical price points
        for i in range(10):
            factor = i / 10
            # Linear interpolation between start and current price with some randomness
            historical_price = start_price + (current_price - start_price) * factor
            historical_price *= random.uniform(0.9, 1.1)  # Add some randomness
            historical.append(round(historical_price))
        
        # Add current price as the last point
        historical.append(current_price)
        
        data[item] = historical
    
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
