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
from utilities import (
    mongo,
    redis_client,
    cassandra,
    mongo_client,
    user_activity_log,
    obtener_stock_producto,
)
from dotenv import load_dotenv

load_dotenv()

ventas = APIRouter(tags=["ventas"], prefix="/ventas")


# Modelo para seleccionar método de pago
class MetodoPago(BaseModel):
    metodo: str  # "Efectivo", "MP", "Tarjeta"
    numero_tarjeta: Optional[str] = None  # Solo si es tarjeta
    guardar_tarjeta: Optional[bool] = False


# Métodos de pago válidos
METODOS_VALIDOS = {"Efectivo", "MP", "Tarjeta"}


# Traer historial de compras
@ventas.get("/historial/{user_id}")
async def traer_historial_compras(user_id: str):
    compras = list(mongo.ventas.find({"idUser": user_id, "PagoCompleto": True}))
    if not compras:
        raise HTTPException(status_code=404, detail="No se encontraron compras")

    user_activity_log(
        user_id, "FETCH_PURCHASE_HISTORY", {"total_compras": len(compras)}
    )
    return compras


# Seleccionar método de pago
def seleccionar_metodo_pago(user_id: str, pago: MetodoPago):
    if pago.metodo == "Tarjeta" and not pago.numero_tarjeta:
        raise HTTPException(
            status_code=400, detail="Número de tarjeta requerido para pago con tarjeta"
        )

    if pago.guardar_tarjeta and pago.numero_tarjeta:
        mongo.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"TarjetasGuardadas": pago.numero_tarjeta}},
        )
        user_activity_log(user_id, "ADD_NEW_CARD", pago.numero_tarjeta)

    return {"message": "Método de pago seleccionado", "metodo": pago.metodo}


# Comprar
@ventas.post("/comprar/{user_id}/{venta_id}")
async def comprar(user_id: str, venta_id: str, compra: MetodoPago):
    if compra.metodo not in METODOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Método de pago inválido")

    seleccionar_metodo_pago(user_id, compra)

    venta = mongo.ventas.find_one({"_id": ObjectId(venta_id), "PagoCompleto": False})
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    # Validar y actualizar stock de forma atómica
    for item in venta["Carrito"]:
        stock = await obtener_stock_producto(item.get("product_id"))
        if stock < item.get("amount"):
            raise HTTPException(
                status_code=400,
                detail=f"No hay stock suficiente para el producto {item.get("product_id")}",
            )

    for item in venta["Carrito"]:
        producto = mongo.products.update_one(
            {"_id": ObjectId(item["product_id"])}, {"$inc": {"stock": -item["amount"]}}
        )
        print(producto)

    # Actualizar venta como pagada y guardar método de pago
    mongo.ventas.update_one(
        {"_id": ObjectId(venta_id)},
        {"$set": {"PagoCompleto": True, "MetodoPago": compra.metodo}},
    )

    # Recalcular categorización del usuario
    total_compras = mongo.ventas.count_documents(
        {"idUser": user_id, "PagoCompleto": True}
    )
    categoria = (
        "LOW" if total_compras <= 10 else "MEDIUM" if total_compras < 20 else "TOP"
    )
    mongo.users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"Categorización": categoria}}
    )

    user_activity_log(user_id, "PURCHASE", venta["Carrito"])

    redis_client.hset(f"user:{str(user_id)}", "carrito", str([]))

    return {"message": "Compra realizada con éxito", "nueva_categorizacion": categoria}
