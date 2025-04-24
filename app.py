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
    "next_update": time.time() + 40  # Next scheduled update time (20 seconds)
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
    
    # Only update prices if enough time has passed (every 20 seconds instead of 60)
    if time_diff < 40:
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
    market_context["next_update"] = current_time + 40  # Schedule next update (20 seconds)

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
    user_message = data.get("user_message", "").strip()

    # Validate inputs
    if not user_message:
        return jsonify({"shop_name": "System", "reply": "Please enter a message.", "transaction": False})
        
    if shop_id not in shops:
        return jsonify({"error": "Invalid shop ID"}), 400

    # Initialize user session if not already done
    initialize_user_session()
    
    # Update market prices before processing any transactions
    update_market_prices()
    
    # Parse user message for direct transaction commands (buy/sell)
    transaction_result = process_transaction(shop_id, user_message.lower())
    if transaction_result:
        return jsonify({
            "shop_name": shops[shop_id]["name"], 
            "reply": transaction_result, 
            "transaction": True
        })

    # Check for AI-proposed transaction acceptance
    transaction_result = process_ai_transaction(shop_id, user_message.lower())
    if transaction_result:
        return jsonify({
            "shop_name": shops[shop_id]["name"], 
            "reply": transaction_result, 
            "transaction": True
        })

    # No transaction detected, get AI response
    try:
        reply = ai_response(shop_id, user_message)

        # Save this negotiation in market context
        market_context["transactions"].append({
            "shop": shops[shop_id]["name"], 
            "message": user_message, 
            "reply": reply
        })
        
        # Limit the size of the transactions history to prevent it from growing too large
        if len(market_context["transactions"]) > 50:
            market_context["transactions"] = market_context["transactions"][-50:]

        return jsonify({
            "shop_name": shops[shop_id]["name"], 
            "reply": reply, 
            "transaction": False
        })
    except Exception as e:
        # Handle AI response errors gracefully
        error_message = f"Sorry, I'm having trouble understanding. Could you rephrase that? (Error: {str(e)})"
        return jsonify({
            "shop_name": shops[shop_id]["name"], 
            "reply": error_message, 
            "transaction": False
        })

def process_ai_transaction(shop_id, user_message):
    """Process transaction when user accepts an AI-proposed deal or counters with a close offer"""
    if not market_context["transactions"]:
        return None
    
    # Get the last few transactions for this shop to look for proposed deals
    shop_transactions = [t for t in market_context["transactions"] if t["shop"] == shops[shop_id]["name"]]
    if not shop_transactions:
        return None
    
    # Expanded list of acceptance terms
    acceptance_terms = ["accept", "deal", "ok", "yes", "i'll take it", "sounds good", "let's do it", 
                        "agreed", "fine", "good", "alright", "sure", "done", "sold"]
    
    # Check for counter-offer terms
    counter_terms = ["counter", "how about", "what about", "instead", "offer", "i propose", "i'll pay"]
    
    # First check if this is an acceptance of a previous offer
    is_acceptance = any(term in user_message.lower() for term in acceptance_terms)
    is_counter = any(term in user_message.lower() for term in counter_terms)
    
    # If it's a clear acceptance, process the previous AI offer
    if is_acceptance and not is_counter:
        # Start with the most recent message and work backwards
        for i in range(min(3, len(shop_transactions))):
            last_ai_message = shop_transactions[-(i+1)]["reply"]
            
            # Look for BUY pattern in AI's message (shop selling to user)
            buy_match = re.search(r"(?i)(?:buy|purchase|I can sell you|I'll sell you|I will sell you)\s+(\d+)\s+([A-Za-z]+)(?:s)?\s+(?:for|at)?\s+(?:₹|rs)?(\d+)", last_ai_message)
            if buy_match:
                try:
                    quantity = int(buy_match.group(1))
                    item_raw = buy_match.group(2)
                    price = int(buy_match.group(3))
                    
                    # Try to match the item name with our known items
                    item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
                    if item and quantity > 0 and price > 0:
                        return handle_buy(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
                except Exception:
                    continue  # If there's an error, try the next message
            
            # Look for SELL pattern in AI's message (shop buying from user)
            sell_match = re.search(r"(?i)(?:sell|I'll buy|I will buy|I can buy|I would buy)\s+(\d+)\s+([A-Za-z]+)(?:s)?\s+(?:for|at)?\s+(?:₹|rs)?(\d+)", last_ai_message)
            if sell_match:
                try:
                    quantity = int(sell_match.group(1))
                    item_raw = sell_match.group(2)
                    price = int(sell_match.group(3))
                    
                    # Try to match the item name with our known items
                    item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
                    if item and quantity > 0 and price > 0:
                        return handle_sell(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
                except Exception:
                    continue  # If there's an error, try the next message
    
    # If it looks like a counter-offer, try to identify the item and new price
    elif is_counter:
        # Check for patterns like "how about 5 bulbs for 45" or "I'll pay 45 for each bulb"
        counter_match = re.search(r"(?i)(?:.*?)(\d+)\s+([A-Za-z]+)(?:s)?(?:\s+(?:for|at)?\s+(?:₹|rs)?)?(?:\s*)(\d+)", user_message)
        if counter_match:
            try:
                quantity = int(counter_match.group(1))
                item_raw = counter_match.group(2)
                price = int(counter_match.group(3))
                
                # Try to match the item name with our known items
                item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
                if item and quantity > 0 and price > 0:
                    # Check recent shop messages to determine if this was for buying or selling
                    for i in range(min(2, len(shop_transactions))):
                        last_ai_message = shop_transactions[-(i+1)]["reply"].lower()
                        if "i can sell" in last_ai_message or "buy from me" in last_ai_message:
                            return handle_buy(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
                        elif "i can buy" in last_ai_message or "sell to me" in last_ai_message:
                            return handle_sell(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
            except Exception:
                pass  # If parsing fails, we'll return None at the end
        
        # Alternative pattern: price first, then item (e.g., "I'll pay 45 for each bulb")
        alt_counter_match = re.search(r"(?i)(?:.*?)(\d+)(?:\s+(?:for|at)?\s+(?:₹|rs)?)?(?:\s+(?:per|each|for each|for a))?\s+([A-Za-z]+)", user_message)
        if alt_counter_match:
            try:
                price = int(alt_counter_match.group(1))
                item_raw = alt_counter_match.group(2)
                
                # Try to match the item name with our known items
                item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
                
                if item and price > 0:
                    # Look in the last AI message to find the quantity they were discussing
                    last_ai_message = shop_transactions[-1]["reply"]
                    
                    quantity_match = re.search(r"(\d+)\s+([A-Za-z]+)", last_ai_message)
                    if quantity_match and quantity_match.group(2).lower() == item_raw.lower():
                        quantity = int(quantity_match.group(1))
                        
                        # Default to 1 if we couldn't find a quantity
                        quantity = max(1, quantity)
                        
                        # Check recent shop messages to determine if this was for buying or selling
                        if "i can sell" in last_ai_message.lower() or "buy from me" in last_ai_message.lower():
                            return handle_buy(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
                        elif "i can buy" in last_ai_message.lower() or "sell to me" in last_ai_message.lower():
                            return handle_sell(shop_id, item, quantity, price, session.get('user_data', get_initial_user_data()))
            except Exception:
                pass  # If parsing fails, we'll return None at the end
    
    return None

def process_transaction(shop_id, message):
    """Process potential transaction commands from user"""
    user_data = session.get('user_data', get_initial_user_data())
    shop = shops[shop_id]
    
    # More robust pattern matching for buy commands
    # Match various formats like "buy 5 bulbs for ₹45", "buy 5 bulbs at 45", "buy 5 bulbs 45"
    buy_match = re.search(r"(?i)(?:buy|purchase|acquire)\s+(\d+)\s+([A-Za-z]+)(?:s)?(?:\s+(?:for|at|@)?\s+(?:₹|rs|price\s+)?)?(?:\s*)(\d+)", message)
    if buy_match:
        try:
            quantity = int(buy_match.group(1))
            item_raw = buy_match.group(2)
            price = int(buy_match.group(3))
            
            # Try to match the item name with our known items - case insensitive
            item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
            
            if item and quantity > 0 and price > 0:
                return handle_buy(shop_id, item, quantity, price, user_data)
            elif not item:
                return f"I don't recognize '{item_raw}'. Available items are: {', '.join(market_context['current_prices'].keys())}."
            else:
                return f"I couldn't understand that transaction. Please specify a valid item, positive quantity, and positive price."
        except Exception as e:
            return f"I couldn't process that transaction. Please try a format like 'buy 5 bulbs at ₹45'. Error: {str(e)}"
    
    # More robust pattern matching for sell commands
    # Match various formats like "sell 3 wires for ₹25", "sell 3 wires at 25", "sell 3 wires 25"
    sell_match = re.search(r"(?i)(?:sell|offer|give)\s+(\d+)\s+([A-Za-z]+)(?:s)?(?:\s+(?:for|at|@)?\s+(?:₹|rs|price\s+)?)?(?:\s*)(\d+)", message)
    if sell_match:
        try:
            quantity = int(sell_match.group(1))
            item_raw = sell_match.group(2)
            price = int(sell_match.group(3))
            
            # Try to match the item name with our known items - case insensitive
            item = next((i for i in market_context["current_prices"].keys() if i.lower() == item_raw.lower()), None)
            
            if item and quantity > 0 and price > 0:
                return handle_sell(shop_id, item, quantity, price, user_data)
            elif not item:
                return f"I don't recognize '{item_raw}'. Available items are: {', '.join(market_context['current_prices'].keys())}."
            else:
                return f"I couldn't understand that transaction. Please specify a valid item, positive quantity, and positive price."
        except Exception as e:
            return f"I couldn't process that transaction. Please try a format like 'sell 3 wires for ₹25'. Error: {str(e)}"
    
    return None

def handle_buy(shop_id, item, quantity, price, user_data):
    """Handle user buying from shop"""
    shop = shops[shop_id]
    current_market_price = market_context["current_prices"][item]
    shop_specialty_discount = 1.0
    
    # Validate inputs
    if quantity <= 0:
        return f"Invalid quantity. Please specify a positive number."
    if price <= 0:
        return f"Invalid price. Please specify a positive number."
    
    # Apply specialty discount if applicable
    if shop["specialty"] == item:
        shop_specialty_discount = shop["discount_rate"]
    
    shop_price = round(current_market_price * shop_specialty_discount)
    
    # Dynamic negotiation factors
    demand_factor = market_context["demand"][item]
    inventory_factor = 1.0
    
    # If shop has high demand, they are less flexible on price
    # If demand is low, they're more willing to negotiate
    negotiation_flexibility = 0.9  # Base acceptance threshold
    
    # Adjust flexibility based on demand - higher demand means less flexibility
    if demand_factor > 1.2:
        # High demand - shop is less flexible
        negotiation_flexibility = random.uniform(0.92, 0.95)
    elif demand_factor < 0.8:
        # Low demand - shop is more flexible
        negotiation_flexibility = random.uniform(0.8, 0.88)
    else:
        # Normal demand - standard flexibility
        negotiation_flexibility = random.uniform(0.85, 0.9)
    
    # If buying a lot, shop might be more flexible
    if quantity >= 10:
        negotiation_flexibility -= 0.05  # More flexible for bulk purchases
    
    # Calculate min acceptable price with all factors
    min_acceptable_price = round(shop_price * negotiation_flexibility)
    
    # Shop decides whether to accept user's price
    if price >= min_acceptable_price:
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
        
        # Different success messages based on how good the deal was
        if price > shop_price:
            return f"Deal! You purchased {quantity} {item}(s) for ₹{price} each. Total cost: ₹{total_cost}. Your new wallet balance is ₹{user_data['wallet']}. I appreciate your generosity!"
        elif price < shop_price:
            return f"Deal! You purchased {quantity} {item}(s) for ₹{price} each. Total cost: ₹{total_cost}. Your new wallet balance is ₹{user_data['wallet']}. You drove a hard bargain!"
        else:
            return f"Deal! You purchased {quantity} {item}(s) for ₹{price} each. Total cost: ₹{total_cost}. Your new wallet balance is ₹{user_data['wallet']}."
    else:
        # Dynamic rejection responses
        price_difference = min_acceptable_price - price
        discount_info = ""
        if shop["specialty"] == item:
            discount_info = f" (with {(1-shop['discount_rate'])*100:.0f}% specialty discount)"
        
        # Different responses based on how far off the offer was
        if price_difference > 10:
            return f"I can't accept that price. It's far too low. The current market price for {item} is ₹{current_market_price}, and my best offer is ₹{shop_price}{discount_info} per unit. Could you offer at least ₹{min_acceptable_price}?"
        elif price_difference > 5:
            return f"That's close, but still too low. The current market price for {item} is ₹{current_market_price}, and I can offer ₹{shop_price}{discount_info} per unit. How about ₹{min_acceptable_price}?"
        else:
            counter_offer = min_acceptable_price
            return f"You're almost there! I can meet you at ₹{counter_offer} per {item}. The market price is ₹{current_market_price}, but I'd be willing to make this deal. What do you say?"

def handle_sell(shop_id, item, quantity, price, user_data):
    """Handle user selling to shop"""
    shop = shops[shop_id]
    current_market_price = market_context["current_prices"][item]
    
    # Validate inputs
    if quantity <= 0:
        return f"Invalid quantity. Please specify a positive number."
    if price <= 0:
        return f"Invalid price. Please specify a positive number."
    
    # Check if user has enough of the item
    if item not in user_data["inventory"] or user_data["inventory"][item]["quantity"] < quantity:
        return f"You don't have enough {item}s to sell. You have {user_data['inventory'].get(item, {}).get('quantity', 0)} but want to sell {quantity}."
    
    # Dynamic negotiation factors for selling
    demand_factor = market_context["demand"][item]
    
    # Base flexibility - shop will pay more if demand is high, less if demand is low
    negotiation_flexibility = 1.1  # Base threshold - will pay up to 110% of market price
    
    # Adjust flexibility based on demand
    if demand_factor > 1.2:
        # High demand - shop is willing to pay more
        negotiation_flexibility = random.uniform(1.1, 1.2)
    elif demand_factor < 0.8:
        # Low demand - shop is less willing to pay premium
        negotiation_flexibility = random.uniform(1.0, 1.05)
    else:
        # Normal demand - standard flexibility
        negotiation_flexibility = random.uniform(1.05, 1.15)
    
    # Specialty adjustment - shops may pay more for items they specialize in
    if shop["specialty"] == item:
        negotiation_flexibility += 0.05
    
    # Quantity adjustment - might pay less per unit for large quantities
    if quantity > 15:
        negotiation_flexibility -= 0.03
    
    # Calculate max acceptable price
    max_acceptable_price = round(current_market_price * negotiation_flexibility)
    
    if price <= max_acceptable_price:
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
        
        # Dynamic success messages based on the deal
        profit_message = ""
        if transaction_profit > 0:
            profit_message = f" You made a profit of ₹{transaction_profit}!"
        elif transaction_profit < 0:
            profit_message = f" You took a loss of ₹{abs(transaction_profit)}."
        
        if price < current_market_price * 0.9:
            return f"Deal! I'm getting a great bargain here. You sold {quantity} {item}(s) for ₹{price} each. Total received: ₹{total_earning}.{profit_message} Your new wallet balance is ₹{user_data['wallet']}."
        elif price > current_market_price:
            return f"Deal! You drove a hard bargain. You sold {quantity} {item}(s) for ₹{price} each. Total received: ₹{total_earning}.{profit_message} Your new wallet balance is ₹{user_data['wallet']}."
        else:
            return f"Deal! You sold {quantity} {item}(s) for ₹{price} each. Total received: ₹{total_earning}.{profit_message} Your new wallet balance is ₹{user_data['wallet']}."
    else:
        # Dynamic rejection responses
        price_difference = price - max_acceptable_price
        price_percentage = (price / current_market_price - 1) * 100
        
        # Different responses based on how far off the offer was
        if price_percentage > 20:
            return f"That's far too expensive! I can't pay that much for {item}. The current market price is ₹{current_market_price}, and I can offer at most ₹{max_acceptable_price} per unit."
        elif price_percentage > 10:
            counter_offer = max_acceptable_price
            return f"Your price is a bit high. How about I pay you ₹{counter_offer} per {item} instead? That's still above the market rate of ₹{current_market_price}."
        else:
            counter_offer = max_acceptable_price
            return f"We're close! I can pay you ₹{counter_offer} per {item}. That's the best I can do, which is still {((counter_offer/current_market_price)-1)*100:.1f}% above the market price of ₹{current_market_price}."

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
