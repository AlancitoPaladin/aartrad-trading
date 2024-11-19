import os
import json
from flask import Flask, jsonify, request
import pymongo
from bson.objectid import ObjectId
import yfinance as yf
import numpy as np
from bson import json_util
from bson.errors import InvalidId
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import pandas as pd

app = Flask(__name__)

uri = "mongodb+srv://alancarlos032104:Alan210304@arthulan.gx9ug.mongodb.net/cryptosimTwo?retryWrites=true&w=majority&appName=arthulan"

myClient = MongoClient(uri, server_api=ServerApi('1'))

myDb = myClient["cryptosimTwo"]
mySimulateCollection = myDb["simulate"]
myCryptosCollection = myDb["cryptos"]
myUserCollection = myDb["users"]

criptomonedas = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'DOGE-USD']


@app.route('/')
def home():
    return jsonify({"message": "API is running. Use /simulate to run simulations."}), 200


def get_data(cripto, start='2024-11-17', end='2024-11-18'):
    try:
        data = yf.download(cripto, start=start, end=end, interval='1h')
        return data
    except Exception as e:
        print(f"Error al descargar datos para {cripto}: {e}")
        return None


def monte_carlo_jump_diffusion(initial_price, mu, sigma, Lambda, a, b, days, simulations, kappa, theta, sigma_v):
    dt = 1 / days
    predictions = np.zeros((simulations, days, 4))  # Open, High, Low, Close

    for i in range(simulations):
        initial_price_simulation = initial_price * (1 + np.random.normal(0, 0.1))

        predictions[i, 0, 0] = initial_price_simulation  # Open
        predictions[i, 0, 3] = initial_price_simulation  # Close
        predictions[i, 0, 1] = initial_price_simulation  # High
        predictions[i, 0, 2] = initial_price_simulation  # Low

        V = sigma ** 2

        for t in range(1, days):
            epsilon = np.random.normal(0, 1)
            jump = np.random.poisson(Lambda * dt)
            jump_magnitude = np.exp(a + b * np.random.normal()) if jump > 0 else 1

            V = max(V + kappa * (theta - V) * dt + sigma_v * np.sqrt(V) * np.random.normal() * np.sqrt(dt), 0)

            price = predictions[i, t - 1, 3] * np.exp(
                (mu - 0.5 * V) * dt + np.sqrt(V) * epsilon * np.sqrt(dt)
            ) * jump_magnitude

            price = max(price, 0.01)

            predictions[i, t, 0] = predictions[i, t - 1, 3]  # Open
            predictions[i, t, 3] = price  # Close
            predictions[i, t, 1] = max(predictions[i, t, 0], price * (1 + np.random.uniform(0.009, 0.025)))  # High
            predictions[i, t, 2] = min(predictions[i, t, 0], price * (1 - np.random.uniform(0.009, 0.03)))  # Low

        return predictions.tolist()


@app.route('/simulate', methods=['GET'])
def simulate():
    try:
        mySimulateCollection.delete_many({})

        for cripto in criptomonedas:
            data = get_data(cripto)

            if data is not None and not data.empty:
                initial_price = data['Close'].iloc[-1]
                initial_price_float = float(initial_price.iloc[0])

                mu = 0.1
                sigma = 0.2
                Lambda = 0.1
                a = 0.1
                b = 0.1
                days = 90
                simulations = 1
                kappa = 0.5
                theta = 0.2
                sigma_v = 0.1

                resultados = monte_carlo_jump_diffusion(
                    initial_price_float, mu, sigma, Lambda, a, b, days, simulations,
                    kappa, theta, sigma_v
                )

                simulation_document = {
                    "crypto": cripto,
                    "simulation": resultados
                }
                mySimulateCollection.insert_one(simulation_document)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Simulación completada y guardada en la base de datos"})


def get_price(symbol):
    try:
        crypto = yf.Ticker(symbol)
        today_data = crypto.history(period='1d')
        if today_data.empty:
            return None
        return round(today_data['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"Error obtaining the price for {symbol}: {e}")
        return None


@app.route('/cryptocurrencies', methods=['GET'])
def get_cryptocurrencies():
    if myCryptosCollection.count_documents({}) == 0:
        myCryptosCollection.insert_many(cryptos_data())
    return all_cryptos()


def cryptos_data():
    return [
        {"Nombre": "Bitcoin", "Precio": get_price("BTC-USD"), "Cantidad": 0,
         "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Bitcoin.svg/1200px-Bitcoin.svg.png",
         "Descripcion": "Bitcoin, la primera criptomoneda descentralizada", "crypto": "BTC-USD"},
        {"Nombre": "Ethereum", "Precio": get_price("ETH-USD"), "Cantidad": 0,
         "image": "https://cryptologos.cc/logos/ethereum-eth-logo.png",
         "Descripcion": "Ethereum, plataforma de contratos inteligentes", "crypto": "ETH-USD"},
        {"Nombre": "Litecoin", "Precio": get_price("LTC-USD"), "Cantidad": 0,
         "image": "https://static.vecteezy.com/system/resources/previews/024/093/060/non_2x/litecoin-ltc-glass-crypto-coin-3d-illustration-free-png.png",
         "Descripcion": "Litecoin, criptomoneda basada en el protocolo de Bitcoin", "crypto": "LTC-USD"},
        {"Nombre": "Cardano", "Precio": get_price("ADA-USD"), "Cantidad": 0,
         "image": "https://cdn4.iconfinder.com/data/icons/crypto-currency-and-coin-2/256/cardano_ada-1024.png",
         "Descripcion": "Cardano, plataforma de blockchain con enfoque científico", "crypto": "ADA-USD"},
        {"Nombre": "Solana", "Precio": get_price("SOL-USD"), "Cantidad": 0,
         "image": "https://upload.wikimedia.org/wikipedia/en/b/b9/Solana_logo.png",
         "Descripcion": "Solana, blockchain de alto rendimiento", "crypto": "SOL-USD"},
        {"Nombre": "Dogecoin", "Precio": get_price("DOGE-USD"), "Cantidad": 0,
         "image": "https://upload.wikimedia.org/wikipedia/en/d/d0/Dogecoin_Logo.png",
         "Descripcion": "Dogecoin, criptomoneda meme creada como una broma", "crypto": "DOGE-USD"}
    ]


@app.route('/update_wallet', methods=['POST'])
def update_wallet():
    try:
        data = request.get_json()
        crypto_id = data['crypto_id']
        quantity = data['quantity']
        is_buying = data['is_buying']

        crypto = myCryptosCollection.find_one({"_id": ObjectId(crypto_id)})

        if not crypto:
            return jsonify({"error": "Criptomoneda no encontrada"}), 404

        new_quantity = crypto['Cantidad'] + quantity

        if new_quantity < 0:
            return jsonify({"error": "Cantidad insuficiente"}), 400

        myCryptosCollection.update_one(
            {"_id": ObjectId(crypto_id)},
            {"$set": {"Cantidad": new_quantity}}
        )
        return jsonify({"message": "Cantidad actualizada correctamente", "new_quantity": new_quantity}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/wallet', methods=['GET'])
def get_wallet():
    try:
        cryptos = list(myCryptosCollection.find({}, {"_id": 1, "Nombre": 1, "Cantidad": 1, "image": 1}))
        for crypto in cryptos:
            crypto['_id'] = str(crypto['_id'])
        return jsonify(cryptos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_cryptos', methods=['GET'])
def get_cryptos():
    return all_cryptos()


def all_cryptos():
    cryptos = list(myCryptosCollection.find())
    for crypto in cryptos:
        crypto['_id'] = str(crypto['_id'])
    return json_util.dumps(cryptos)


@app.route('/crypto_simulation/<crypto_id>', methods=['GET'])
def get_crypto_simulation(crypto_id):
    try:
        try:
            object_id = ObjectId(crypto_id)
        except InvalidId:
            return jsonify({"error": "ID no válido"}), 400

        crypto = myCryptosCollection.find_one({"_id": object_id})
        if not crypto:
            return jsonify({"message": "Criptomoneda no encontrada"}), 404

        simulation = mySimulateCollection.find_one({"crypto": crypto["crypto"]})
        if not simulation:
            return jsonify({"message": "Simulación no encontrada para la criptomoneda"}), 404

        crypto["_id"] = str(crypto["_id"])
        simulation["_id"] = str(simulation["_id"])

        response = {
            "crypto": crypto,
            "simulation": simulation
        }
        return json_util.dumps(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if myUserCollection.find_one({"email": email}):
        return jsonify({"error": "Email ya registrado"}), 409

    hashed_password = generate_password_hash(password)

    # Crear usuario con saldo inicial en 0
    user = {
        "firstName": data.get('firstName'),
        "lastName": data.get('lastName'),
        "middleName": data.get('middleName'),
        "email": email,
        "password": hashed_password,
        "saldo": 0.0
    }

    myUserCollection.insert_one(user)
    return jsonify({"message": "Usuario registrado exitosamente"}), 201


@app.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = myUserCollection.find_one({"email": email})
    if user and check_password_hash(user['password'], password):
        user["_id"] = str(user["_id"])
        user_data = {
            "id": user["_id"],
            "firstName": user["firstName"],
            "lastName": user["lastName"],
            "email": user["email"],
            "saldo": user["saldo"]
        }
        return jsonify(user_data)
    else:
        return jsonify({"error": "Email o contraseña incorrectos"}), 401


@app.route('/get_user', methods=['GET'])
def get_all_users():
    users = list(myUserCollection.find({}, {"password": 0}))
    for user in users:
        user["_id"] = str(user["_id"])
    return json_util.dumps(users)


@app.route('/user/deposit', methods=['POST'])
def deposit():
    data = request.get_json()
    email = data.get('email')
    amount = data.get('amount')

    if amount <= 0:
        return jsonify({"error": "Cantidad inválida"}), 400

    user = myUserCollection.find_one({"email": email})
    if user:
        new_balance = user['saldo'] + amount
        myUserCollection.update_one({"email": email}, {"$set": {"saldo": new_balance}})
        return jsonify({"message": "Depósito exitoso", "saldo": new_balance}), 200
    else:
        return jsonify({"error": "Usuario no encontrado"}), 404


@app.route('/user/withdraw', methods=['POST'])
def withdraw():
    data = request.get_json()
    email = data.get('email')
    amount = data.get('amount')

    if amount <= 0:
        return jsonify({"error": "Cantidad inválida"}), 400

    user = myUserCollection.find_one({"email": email})
    if user:
        if user['saldo'] >= amount:
            new_balance = user['saldo'] - amount
            myUserCollection.update_one({"email": email}, {"$set": {"saldo": new_balance}})
            return jsonify({"message": "Retiro exitoso", "saldo": new_balance}), 200
        else:
            return jsonify({"error": "Saldo insuficiente"}), 400
    else:
        return jsonify({"error": "Usuario no encontrado"}), 404


if __name__ == "__main__":
    app.run(debug=True)
