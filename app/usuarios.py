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
import redis
import json
from cassandra.cluster import Cluster
import uuid
from utilities import mongo, redis_client, cassandra, mongo_client, user_activity_log, chek_user_id
from dotenv import load_dotenv

load_dotenv()

usuario = APIRouter(tags=["usuario"], prefix="/usuario")


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    name: str
    last_name: Optional[str] = Field(default=None)
    user_name: str
    email: Optional[str] = Field(default=None)
    dni: Optional[str] = Field(min_length=8, max_length=16, default=None)


class UserInDb(User):
    password: str


def obtener_ultimo_carrito(user_id):
    session = cassandra.connect("usuarios")
    try:
        query = """
            SELECT 
                carrito
            FROM user_activity_log
            WHERE user_id = %(user_id)s
            AND event_type = 'LOGOUT'
            ORDER BY event_time DESC
            LIMIT 1
            ALLOW FILTERING;
        """
        result = session.execute(query, {"user_id": user_id})
        row = result.one()
        return row[0]
    except Exception as e:
        print(f"Error al obtener carrito: {e}")


def authenticate_user(username: str, password: str) -> User:
    try:
        data = get_user(username)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar la contraseña usando bcrypt.checkpw()
        hashed_password = data["password"]
        if not bcrypt.checkpw(password.encode("utf-8"), hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return User(**data), str(data.get("_id"))
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

refresh_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Refresh token inválido",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_user(username):
    "Obtiene el usuario"
    collection = mongo.users
    try:
        data = collection.find_one({"user_name": username})
        return data
    except Exception as e:
        raise credentials_exception


@usuario.post("/register")
async def post_new_user(user: UserInDb):
    collection = mongo.users
    try:
        user.password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
        user_dict = user.dict()
        user_dict["date"] = datetime.today()
        user_dict["active"] = True
        user_dict["categorization"] = "LOW"
        data = collection.find_one({"user_name": user.user_name})
        if data:
            raise HTTPException(status_code=409, detail="username ya existente")

        post_id = collection.insert_one(user_dict).inserted_id

        user_activity_log(str(post_id), "REGISTER", [])

        redis_client.hset(
            f"user:{str(post_id)}",
            mapping={"user": user.user_name, "id_user": str(post_id), "carrito": "[]"},
        )

        rsp = collection.find_one({"_id": post_id})
        rsp["idUser"] = str(rsp.get("_id"))
        rsp.pop("_id")

        return rsp
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@usuario.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    user, id = authenticate_user(form_data.username, form_data.password)

    if chek_user_id(id):
        raise HTTPException(status_code=400,detail="Usuario ya logeado")

    carrito = eval(obtener_ultimo_carrito(id))
    if not carrito:
        carrito = []
    user_activity_log(id, "LOGIN", carrito)

    redis_client.hset(
        f"user:{id}",
        mapping={"user": form_data.username, "id_user": id, "carrito": str(carrito)},
    )
    user_dict = user.dict()
    user_dict["idUser"] = id

    return user_dict


@usuario.delete("/logout/user_id/{user_id}")
async def logout(user_id):
    user = chek_user_id(user_id)
    
    carrito = redis_client.hget(f"user:{str(user_id)}", "carrito")

    if not carrito:
        raise HTTPException(status_code=400,detail="usuario no logeado")

    user_activity_log(str(user_id), "LOGOUT", carrito)

    redis_client.delete(f"user:{str(user_id)}")

    return True


@usuario.get("/tarjetas/user_id/{user_id}")
async def get_tarjetas(user_id=None):
    """
    Se devuelven todas las tarjetas asociadas al usuario.
    Devuelve error en caso que no tenga ninguna tarjeta asociada
    """
    user = chek_user_id(user_id)

    tarjetas = mongo.users.find_one({"_id":ObjectId(user_id)},{"TarjetasGuardadas":1,"_id":0})

    if not tarjetas:
        raise HTTPException(status_code=404,detail="No hay tarjetas guardadas")

    return tarjetas