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

ventas = APIRouter(tags=["ventas"], prefix="/ventas")

# Modelo para seleccionar método de pago
class MetodoPago(BaseModel):
    metodo: str  # "Efectivo", "MP", "Tarjeta"
    numero_tarjeta: Optional[str] = None  # Solo si es tarjeta
    guardar_tarjeta: Optional[bool] = False

# Modelo para actualizar la compra con método de pago
class CompraUpdate(BaseModel):
    metodo_pago: str

# Traer historial de compras
@ventas.get("/historial/{user_id}")
def traer_historial_compras(user_id: str):
    compras = list(mongo.ventas.find({"idUser": user_id}, {"pagoCompletado": True}))
    if not compras:
        raise HTTPException(status_code=404, detail="No se encontraron compras")
    
    user_activity_log(user_id, "FETCH_PURCHASE_HISTORY", compras)
    return compras

# Seleccionar método de pago
@ventas.post("/metodo_pago/{user_id}")
def seleccionar_metodo_pago(user_id: str, pago: MetodoPago):
    if pago.metodo == "Tarjeta" and not pago.numero_tarjeta:
        raise HTTPException(status_code=400, detail="Número de tarjeta requerido para pago con tarjeta")
    
    if pago.guardar_tarjeta and pago.numero_tarjeta:
        mongo.users.update_one(
            {"idUser": user_id},
            {"$push": {"TarjetasGuardadas": pago.numero_tarjeta}}
        )
        user_activity_log(user_id, "ADD_NEW_CARD", pago.numero_tarjeta)
    
    return {"message": "Método de pago seleccionado", "metodo": pago.metodo}

# Comprar
@ventas.post("/comprar/{user_id}/{venta_id}")
def comprar(user_id: str, venta_id: str, compra: CompraUpdate):
    venta = mongo.ventas.find_one({"idVenta": venta_id})
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    # Validar stock
    for item in venta["Carrito"]:
        producto = mongo.productos.find_one({"Nombre": item["producto"]})
        if not producto or producto["Stock"] < item["cantidad"]:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {item['producto']}")
    
    # Descontar stock
    for item in venta["Carrito"]:
        mongo.productos.update_one(
            {"Nombre": item["producto"]},
            {"$inc": {"Stock": -item["cantidad"]}}
        )
    
    # Actualizar venta como pagada y guardar método de pago
    mongo.ventas.update_one(
        {"idVenta": venta_id},
        {"$set": {"PagoCompleto": True, "MetodoPago": compra.metodo_pago}}
    )
    
    # Recalcular categorización del usuario
    total_compras = mongo.ventas.count_documents({"idUser": user_id, "PagoCompleto": True})
    categoria = "LOW" if total_compras <= 10 else "MEDIUM" if total_compras < 20 else "TOP"
    mongo.users.update_one(
        {"idUser": user_id},
        {"$set": {"Categorización": categoria}}
    )
    
    user_activity_log(user_id, "PURCHASE", venta["Carrito"])
    return {"message": "Compra realizada con éxito", "nueva_categorizacion": categoria}
