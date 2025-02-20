from pymongo import MongoClient
from os import environ
from neo4j import GraphDatabase
import redis
from cassandra.cluster import Cluster
import uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Depends, status
from bson import ObjectId


load_dotenv()


# Configurar la conexión a MongoDB
MONGO_URI = "mongodb://mongo:27017"
mongo_client = MongoClient(MONGO_URI)
mongo = mongo_client["mi_basedatos"]  # Nombre de la base de datos

# Configuración de Redis
REDIS_HOST = "redis"
REDIS_PORT = 6379
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

cassandra_host = environ.get("CASSANDRA_HOST", "cassandra")
cassandra = Cluster([cassandra_host], port=9042)


def user_activity_log(user_id, evento, carrito):
    try:
        session = cassandra.connect()
        keyspace_query = """
            CREATE KEYSPACE IF NOT EXISTS usuarios
            WITH replication = {
              'class': 'SimpleStrategy',
              'replication_factor': '1'
            };
        """
        session.execute(keyspace_query)
        session_usuario = cassandra.connect("usuarios")
        session_usuario.execute(
            f"""
            CREATE TABLE IF NOT EXISTS user_activity_log (
                user_id TEXT, -- Identificador único del usuario
                event_time TIMESTAMP, -- Hora del evento
                event_type TEXT, -- Tipo de evento (ej. "eliminar producto", "realizar compra", etc.)
                carrito TEXT,  
                PRIMARY KEY (user_id, event_time)
            ) WITH CLUSTERING ORDER BY (event_time DESC);
        """
        )
        query = f"""
            INSERT INTO user_activity_log (
                user_id, 
                event_time, 
                event_type, 
                carrito
            ) VALUES(
                %s, 
                %s, 
                %s, 
                %s
            )
        """
        session_usuario.execute(
            query, (str(user_id), datetime.now(), evento, str(carrito))
        )
        session_usuario.shutdown()
        return True
    except Exception as e:
        print(f"Error logeo de usario: {e}")
        return False


async def obtener_stock_producto(idProducto: str) -> int:
    """
    Devuelve el stock de un producto en la colección 'productos' en MongoDB.
    """
    collection = mongo.products
    try:
        # Buscar el producto por idProducto
        producto = collection.find_one(
            {"_id": ObjectId(idProducto), "disable_date": None}, {"stock": 1, "_id": 0}
        )

        # Si el producto no existe, lanzar error 404
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Devolver el stock como entero
        return producto.get("stock", 0)

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
