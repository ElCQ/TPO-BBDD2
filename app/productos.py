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
