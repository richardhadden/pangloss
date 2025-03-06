from typing import Annotated

from authx import AuthX, AuthXConfig
from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel


class User(BaseModel):
    username: str


app = FastAPI(title="My Base App")


config = AuthXConfig()
config.JWT_ALGORITHM = "HS256"
config.JWT_SECRET_KEY = "SECRET_KEY"
config.JWT_TOKEN_LOCATION = ["headers", "query", "cookies", "json"]
config.JWT_ACCESS_COOKIE_NAME = "access-token"
config.JWT_REFRESH_COOKIE_NAME = "refresh-token"
config.JWT_CSRF_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

LOGGED_IN_USER_NAME_COOKIE_NAME = "logged_in_user_name"

security = AuthX[User](config=config)

app = FastAPI()

security.handle_errors(app)


@app.get("/")
async def index():
    return {"page": "Index"}


class LoginCredentials(BaseModel):
    username: str
    password: str


@security.set_subject_getter
def get_user_from_uid(email: str, *args) -> User:
    print(email)
    return User.model_validate({"username": "John Smith"})


@app.post("/token")
def get_token(credentials: LoginCredentials):
    if credentials.username == "test" and credentials.password == "test":
        token = security.create_access_token(uid=credentials.username)
        return {"access_token": token}
    raise HTTPException(401, detail={"message": "Bad credentials"})


@app.post("/session")
def get_session(response: Response, username: str, password: str):
    if username == "test" and password == "test":
        access_token = security.create_access_token(uid=username)
        response.set_cookie(
            config.JWT_ACCESS_COOKIE_NAME, access_token, httponly=True, secure=True
        )
        response.set_cookie(LOGGED_IN_USER_NAME_COOKIE_NAME, value=username)

        return {"message": "success"}
    raise HTTPException(401, detail={"message": "Bad credentials"})


@app.delete("/session")
def delete_session(response: Response):
    response.delete_cookie(config.JWT_ACCESS_COOKIE_NAME)
    response.delete_cookie(LOGGED_IN_USER_NAME_COOKIE_NAME)


@app.get("/protected", dependencies=[Depends(security.access_token_required)])
def get_protected():
    return {"message": "Hello World"}


@app.get("/whoami")
async def whoami(user: Annotated[User, Depends(security.get_current_subject)]):
    return f"You are: {user.username}"


def is_admin_user(user: Annotated[User, Depends(security.get_current_subject)]) -> User:
    raise HTTPException(403, detail={"message": "Admin user required"})
    return user


@app.get("/admin")
def is_admin(user: Annotated[User, Depends(is_admin_user)]):
    return {"message": "is admin!"}
