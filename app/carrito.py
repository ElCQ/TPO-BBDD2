from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from typing import Annotated
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone
from os import environ
from cassandra.cluster import Cluster
import uuid
from utilities import mongo, redis_client, cassandra, mongo_client, user_activity_log
from dotenv import load_dotenv

load_dotenv()

carrito = APIRouter(tags=["carrito"], prefix="/carrito")


class Carrito(BaseModel):
    product_id: str
    amount: int


@carrito.post("/agregar/user_id/{user_id}")
async def agregar_carrito(user_id, carrito: Carrito):
    """
    agrega producto al carrito activo
    """
    carrito_viejo = eval(redis_client.hget(f"user:{str(user_id)}", "carrito"))
    carrito_nuevo = carrito_viejo

    amount = None
    if carrito_nuevo:
        for producto in carrito_nuevo:
            if carrito.product_id == producto.get("product_id"):
                amount = producto.get("amount") + carrito.amount

                # Acá validaria el stock del producto
                # stock = get_stock(carrito.product_id)
                # if stock < amount:
                #     raise HTTPException(status_code=400,detail="No hay mas productos en el stock")

                producto["amount"] = amount

    if not amount:
        carrito_nuevo.apend(carrito.dict())

    redis_client.hset(f"user:{str(user_id)}", "carrito", str(carrito_nuevo))

    user_activity_log(user_id, "ADD_CART", carrito_viejo)

    return carrito_nuevo


@carrito.delete("/borrar/user_id/{user_id}")
async def borar_carrito():
    """
    """