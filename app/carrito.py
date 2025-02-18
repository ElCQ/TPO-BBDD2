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

carrito = APIRouter(tags=["carrito"], prefix="/carrito")
