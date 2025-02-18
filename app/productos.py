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
        print(f"Error logeo de producto: {e}")
        return False


@productos.post("")
async def post_producto(userid, product: Producto):
    """
    Se inserta un nuevo producto a la base
    """
    return await agregar_producto(userid, product)


@productos.patch("/id_product/{id_product}")
async def put_producto(userid, id_product, product: Producto):
    """
    Actualiza un producto apartir del id producto
    """
    return await actualizar_producto(userid, id_product, product)


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


async def agregar_producto(userid, producto: Producto):
    """
    Agrega un nuevo producto a la colección 'productos' en MongoDB.
    """
    collection = mongo.products
    try:
        # Verificar si el producto ya existe
        existing_product = collection.find_one({"name": producto.name})
        if existing_product:
            raise HTTPException(status_code=409, detail="El producto ya existe")

        # Construir el documento a insertar
        producto_dict = producto.dict(by_alias=True)
        producto_dict["date_added"] = datetime.utcnow()

        # Insertar el producto en la base de datos
        post_id = collection.insert_one(producto_dict).inserted_id

        product_activity_log(
            str(userid), str(post_id), "ADD_PRODUCT", str(producto_dict)
        )

        return {"message": "Producto agregado con éxito", "id": str(post_id)}

    except HTTPException as e:
        raise e
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


async def actualizar_producto(userid, idProducto: str, producto: Producto):
    """
    Actualiza un producto existente en la colección 'productos' en MongoDB.
    """
    collection = mongo.products
    try:
        # Verificar si el producto existe
        existing_product = collection.find_one({"idProducto": idProducto})
        if not existing_product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Convertir el objeto Producto en diccionario
        producto_dict = producto.dict(
            exclude_unset=True
        )  # Excluye valores no modificados
        producto_dict["date_updated"] = datetime.utcnow()

        # Actualizar el producto en la base de datos
        collection.update_one({"idProducto": idProducto}, {"$set": producto_dict})

        # Guardar log de actividad
        product_activity_log(userid, str(idProducto), "UPDATE_PRODUCT", producto_dict)

        return {"message": "Producto actualizado con éxito", "idProducto": idProducto}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def eliminar_producto(userid, idProducto: str):
    """
    Elimina un producto de la colección 'productos' en MongoDB.
    """
    collection = mongo.products
    try:
        # Verificar si el producto existe
        existing_product = collection.find_one({"idProducto": idProducto})
        if not existing_product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Eliminar el producto de la base de datos
        collection.delete_one({"idProducto": idProducto})

        # Guardar log de actividad
        product_activity_log(userid, idProducto, "DELETE_PRODUCT", existing_product)

        return {"message": "Producto eliminado con éxito", "idProducto": idProducto}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def obtener_log_productos(
    idProducto: Optional[str] = None,
    fechaDesde: Optional[str] = None,
    fechaHasta: Optional[str] = None,
    userId: Optional[str] = None,
):
    """
    Devuelve la lista de actividades de producto asociadas a la tabla de actividades de producto.
    Se puede buscar por idProducto, userId, y se requiere fechaDesde y fechaHasta.
    """

    try:
        session = cassandra.connect()
        # Si no se proporcionan fechas, se establecen desde ayer hasta hoy
        if not fechaDesde or not fechaHasta:
            hoy = datetime.utcnow()
            fechaDesde_dt = hoy - timedelta(days=1)  # Ayer
            fechaHasta_dt = hoy  # Hoy
        else:
            # Convertir fechas a formato datetime
            fechaDesde_dt = datetime.strptime(fechaDesde, "%Y-%m-%dT%H:%M:%S")
            fechaHasta_dt = datetime.strptime(fechaHasta, "%Y-%m-%dT%H:%M:%S")

            # Validar que fechaDesde no sea mayor que fechaHasta
            if fechaDesde_dt > fechaHasta_dt:
                raise HTTPException(
                    status_code=400,
                    detail="fechaDesde no puede ser mayor que fechaHasta",
                )

            # Validar que la diferencia entre ambas fechas no sea mayor a 3 meses
            if (fechaHasta_dt - fechaDesde_dt).days > 90:
                raise HTTPException(
                    status_code=400,
                    detail="El rango de fechas no puede ser mayor a 3 meses",
                )

        # Construcción de la consulta
        query = "SELECT * FROM productos_activity_log WHERE event_time >= %s AND event_time <= %s"
        values = [fechaDesde_dt, fechaHasta_dt]

        if idProducto:
            query += " AND product_id = %s"
            values.append(idProducto)

        if userId:
            query += " AND user_id = %s"
            values.append(userId)

        query += " ORDER BY event_time DESC"

        # Ejecutar la consulta
        rows = session.execute(query, tuple(values))

        # Convertir los resultados a una lista de diccionarios
        logs = [
            {
                "user_id": row.user_id,
                "product_id": row.product_id,
                "event_time": row.event_time.isoformat(),
                "event_type": row.event_type,
                "producto": row.producto,
            }
            for row in rows
        ]

        return {"logs": logs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
