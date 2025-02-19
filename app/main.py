from fastapi import FastAPI, HTTPException, Depends, status
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
from utilities import mongo, redis_client, cassandra, mongo_client
from usuarios import usuario
from productos import productos
from carrito import carrito
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.include_router(router=usuario)
app.include_router(router=productos)
app.include_router(router=carrito)


@app.get("/health")
def health_check():
    status = {}

    # Chequeo de MongoDB
    try:
        mongo_client.admin.command("ping")
        status["MongoDB"] = "alive"
    except ConnectionFailure:
        status["MongoDB"] = "unreachable"

    # # Chequeo de Neo4j
    # try:
    #     with neo4j_driver.session() as session:
    #         session.run("RETURN 1")  # Ejecuta una consulta de prueba
    #     status["Neo4j"] = "alive"
    # except Exception as e:
    #     status["Neo4j"] = f"unreachable: {str(e)}"

    # Chequeo de Redis
    try:
        redis_client.ping()  # Enviar un ping a Redis
        status["Redis"] = "alive"
    except redis.ConnectionError:
        status["Redis"] = "unreachable"

    # Chequeo de Cassandra
    try:
        sesion = cassandra.connect()
        sesion.execute("SELECT now() FROM system.local")
        status["Cassandra"] = "alive"
        cassandra.shutdown()
    except Exception as e:
        status["Cassandra"] = f"unreachable: {str(e)}"

    return status
