from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from typing import Annotated
import bcrypt
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone
from os import environ
from neo4j import GraphDatabase
import redis
import json
import jwt
from cassandra.cluster import Cluster
import uuid
from jwt.exceptions import InvalidTokenError
from utilities import mongo, redis_client, cassandra, mongo_client, user_activity_log
from dotenv import load_dotenv

load_dotenv()


productos = APIRouter(tags=["productos"], prefix="/productos")


class PutProducto(BaseModel):
    stock: Optional[int] = Field(default=None)
    price: Optional[float] = Field(default=None)


class Producto(BaseModel):
    name: str
    description: Optional[str] = Field(default=None)
    price: float
    stock: Optional[int] = Field(default=0)
    image: Optional[str] = Field(None)


def product_activity_log(user_id, product_id, event, producto):
    """
    Se guardan los logs de los diferentes productos
    """
    try:
        session = cassandra.connect()
        keyspace_query = """
            CREATE KEYSPACE IF NOT EXISTS productos
            WITH replication = {
              'class': 'SimpleStrategy',
              'replication_factor': '1'
            };
        """
        session.execute(keyspace_query)
        session_productos = cassandra.connect("productos")
        session_productos.execute(
            """
            CREATE TABLE IF NOT EXISTS productos_activity_log (
                user_id TEXT,
                product_id TEXT, -- Identificador único del producto
                event_time TIMESTAMP, -- Hora del evento
                event_type TEXT, -- Tipo de evento (ej. "agregar producto", "quitar producto")
                producto TEXT, -- JSON CON LOS DATOS DEL PRODUCTO ANTES DE SER REALIZADA LA ACCIÓN
                PRIMARY KEY (product_id, event_time)
            ) WITH CLUSTERING ORDER BY (event_time DESC);
        """
        )
        query = """
            INSERT INTO user_activity_log (
                user_id,
                product_id,
                event_time,
                event_type, 
                producto
            ) VALUES(
                %s, 
                %s, 
                %s, 
                %s
            )
        """
        session_productos.execute(
            query, (str(user_id), str(product_id), datetime.now(), event, str(producto))
        )
        session_productos.shutdown()
        return True
    except Exception as e:
        print(f"Error logeo de usario: {e}")
        return False


@productos.post("")
async def post_producto(product: Producto):
    """
    Se inserta un nuevo producto a la base
    """


@productos.patch("/id_product/{id_product}")
async def put_producto(id_product, data: PutProducto):
    """
    Actualiza un producto apartir del id producto
    """


@productos.get("")
@productos.get("/id_product/{id_product}")
async def get_producto(id_product=None):
    """
    Se obtiene uno varios productos
    """


@productos.delete("/id_product/{id_product}")
async def delete_producto(id_product):
    """
    Se elimina un producto en especifico
    """
