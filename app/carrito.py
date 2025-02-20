from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from typing import Annotated
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from os import environ
import copy
from cassandra.cluster import Cluster
import uuid
from productos import obtener_precio_producto
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

carrito = APIRouter(tags=["carrito"], prefix="/carrito")


class Carrito(BaseModel):
    product_id: str
    amount: int


class Pedido(BaseModel):
    idUser: str
    Fecha: Optional[datetime] = Field(default=datetime.today())
    Carrito: List[Carrito]
    TotalDeVenta: float
    MetodoPago: str = None
    PagoCompleto: bool = False


@carrito.post("/agregar/user_id/{user_id}")
async def agregar_carrito(user_id, carrito: Carrito):
    """
    agrega producto al carrito activo
    """
    carrito_viejo = eval(redis_client.hget(f"user:{str(user_id)}", "carrito"))
    carrito_nuevo = copy.deepcopy(carrito_viejo)
    stock = await obtener_stock_producto(carrito.product_id)
    if stock < carrito.amount:
        raise HTTPException(status_code=400, detail="No hay mas productos en el stock")
    amount = None
    if carrito_nuevo:
        for producto in carrito_nuevo:
            if carrito.product_id == producto.get("product_id"):
                amount = producto.get("amount") + carrito.amount
                if stock < amount:
                    raise HTTPException(
                        status_code=400, detail="No hay mas productos en el stock"
                    )
                producto["amount"] = amount
                break

    if not amount:
        carrito_nuevo.append(carrito.dict())

    redis_client.hset(f"user:{str(user_id)}", "carrito", str(carrito_nuevo))

    user_activity_log(user_id, "ADD_CART", carrito_viejo)

    return carrito_nuevo


@carrito.delete("/borrar/user_id/{user_id}")
async def borar_carrito(user_id, carrito: Carrito):
    """
    Borra o todo el producto del carrito si la cantidad esta en 0
    o
    n cantidad sin superar lo que esta en el carrito
    """
    carrito_viejo = eval(redis_client.hget(f"user:{str(user_id)}", "carrito"))
    carrito_nuevo = copy.deepcopy(carrito_viejo)

    if not carrito_nuevo:
        HTTPException(status_code=404, detail="No hay datos en el carrito")

    for producto in carrito_nuevo:
        if producto.get("product_id") == carrito.product_id:
            if carrito.amount == 0:
                carrito_nuevo.remove(producto)
            else:
                if (producto.get("amount") - carrito.amount) < 0:
                    raise HTTPException(
                        status_code=400,
                        detail="No hay suficientes productos en el carrito",
                    )
                    # carrito_nuevo.remove(producto)
                else:
                    amount = producto.get("amount") - carrito.amount
                    producto["amount"] = amount
            break

    redis_client.hset(f"user:{str(user_id)}", "carrito", str(carrito_nuevo))

    user_activity_log(user_id, "REDUCE_CART", carrito_viejo)

    return carrito_nuevo


@carrito.post("/confirmar/user_id/{user_id}")
async def confirmar_carrito(user_id):
    """ """
    carrito = eval(redis_client.hget(f"user:{str(user_id)}", "carrito"))

    if not carrito:
        raise HTTPException(status_code=400, detail="No hay carrito cargado")

    if verificar_otro_pedido(user_id):
        raise HTTPException(status_code=400, detail="Ya existe un pedido pendiente")

    total_venta = 0
    for producto in carrito:
        stock = await obtener_stock_producto(producto.get("product_id"))
        if stock < producto.get("amount"):
            raise HTTPException(
                status_code=400,
                detail=f"No hay stock suficiente para el producto {producto.get("product_id")}",
            )
        price = obtener_precio_producto(producto.get("product_id"))
        total_venta += price * producto.get("amount")

    pedido = Pedido(idUser=user_id, Carrito=carrito, TotalDeVenta=total_venta)

    id_venta = crear_venta(pedido.dict())

    user_activity_log(user_id, "ORDER_CREATED", carrito)

    return {
        "idVenta": id_venta,
        "Fecha": pedido.Fecha,
        "TotalDeVenta": pedido.TotalDeVenta,
    }


@carrito.delete("/pedido/user_id/{user_id}")
async def delete_pedido(user_id):
    """
    Elimina el pedido pendiente que tenga el usuario
    """
    return eliminar_pedido(user_id)


def crear_venta(pedido):
    collection = mongo.ventas
    try:
        post_id = collection.insert_one(pedido).inserted_id
        if not post_id:
            raise HTTPException(status_code=400, detail="Error al crear venta")
        return str(post_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error al cargar venta: {e}")
        raise HTTPException(status_code=500, detail=f"{e}")


def verificar_otro_pedido(user_id):
    collection = mongo.ventas
    try:
        data = collection.find_one({"idUser": user_id, "PagoCompleto": False})
        if data:
            return True
        else:
            return False
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error al cargar venta: {e}")
        raise HTTPException(status_code=500, detail=f"{e}")


def eliminar_pedido(user_id):
    collection = mongo.ventas
    try:
        if not verificar_otro_pedido(user_id):
            raise HTTPException(
                status_code=400, detail="No hay ningun pedido pendiente"
            )

        venta = collection.find_one({"idUser": user_id, "PagoCompleto": False})
        venta["idVenta"] = str(venta.get("_id"))
        venta.pop("_id")
        collection.delete_one({"idUser": user_id, "PagoCompleto": False})

        user_activity_log(user_id, "ORDER_DELETED", str(venta.get("Carrito")))

        return {"message": "Pedido eliminado con éxito", "venta": venta}

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error al cargar venta: {e}")
        raise HTTPException(status_code=500, detail=f"{e}")
