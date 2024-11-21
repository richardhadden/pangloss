import asyncio
from pathlib import Path
from typing import Annotated


from fastapi import (
    Depends,
    HTTPException,
    status,
    Response,
    APIRouter,
    FastAPI,
)

from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field, validate_email, EmailStr
from pydantic_core import PydanticCustomError
from rich import print
import typer

from pangloss.auth import (
    create_access_token,
    decode_token,
    get_password_hash,
    oauth2_scheme,
    verify_password,
)
from pangloss.database import read_transaction, write_transaction, Transaction
from pangloss.initialisation import (
    initialise_pangloss_application,
    get_project_settings,
)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None
    admin: bool = Field(default=False, json_schema_extra={"readOnly": True})
    disabled: bool = Field(default=False, json_schema_extra={"readOnly": True})


class UserView(BaseModel):
    username: str
    email: str
    full_name: str | None


class UserCreate(User):
    password: str


class UserInDB(User):
    hashed_password: str

    @write_transaction
    async def write_user(self, tx: Transaction):
        query = """
        CREATE (user:PGUser:PGInternal:PGCore)
        SET user = $user
        RETURN user.username
        """
        params = {"user": dict(self)}
        result = await tx.run(query, params)
        user = await result.value()
        return user[0]

    @classmethod
    @read_transaction
    async def get(cls, tx: Transaction, username: str) -> "UserInDB | None":
        query = """
        MATCH (user:PGUser)
        WHERE user.username = $username
        RETURN user
        """
        params = {"username": username}
        result = await tx.run(query, params)
        user = await result.value()
        try:
            if user and user[0]:
                return __class__(**user[0])
        except IndexError:
            return None


async def authenticate_user(username: str, password: str):
    user = await UserInDB.get(username=username)
    if not user:
        return False

    if not verify_password(password, user.hashed_password):
        return False
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)

        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    if token_data and token_data.username:
        user = await UserInDB.get(username=token_data.username)
    else:
        raise credentials_exception
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    if not current_user.admin:
        raise HTTPException(status_code=403, detail="Not authorised")
    return current_user


def setup_user_routes(_app: FastAPI, settings):
    api_router = APIRouter(prefix="/api/users", tags=["User"])

    @api_router.post("/login", response_model=Token, name="UserLogin")
    async def login_for_access_token(
        response: Response, form_data: OAuth2PasswordRequestForm = Depends()
    ):  # added response as a function parameter
        user = await authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        access_token = create_access_token(data={"sub": user.username})
        response.set_cookie(
            key="access_token", value=f"Bearer {access_token}", httponly=True
        )  # set HttpOnly cookie in response
        response.set_cookie(
            key="logged_in_user_name", value=user.username, httponly=False
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    @api_router.get("/logout", name="UserLogout")
    async def log_out(response: Response) -> dict[str, str]:
        response.delete_cookie(key="access_token", httponly=True)
        response.delete_cookie("logged_in_user_name", httponly=False, samesite="lax")
        return {"message": "Logged out"}

    @api_router.get("/current_user", name="CurrentUser")
    async def current_user(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> UserView:
        return UserView(**dict(current_user))

    @api_router.get("/me", response_model=User)
    async def read_users_me(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ):
        return current_user

    @api_router.get("/me/items")
    async def read_own_items(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ):
        return [{"item_id": "Foo", "owner": current_user.username}]

    @api_router.post("/new", name="CreateUser")
    async def create_user(
        new_user: UserCreate,
        current_user: Annotated[User, Depends(get_current_admin_user)],
    ):
        user_to_create = UserInDB(
            username=new_user.username,
            email=new_user.email,
            hashed_password=get_password_hash(new_user.password),
        )
        result = await user_to_create.write_user()
        return result

    _app.include_router(api_router)

    return _app


user_cli = typer.Typer(name="users")


def get_email():
    try:
        email = validate_email(typer.prompt("Email", type=str))
        return email
    except PydanticCustomError:
        print("[red bold]Invalid email[/red bold]")
        return get_email()


async def create_user(username: str, email: EmailStr, password: str, admin: bool):
    user_to_create = UserInDB(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        admin=admin,
    )

    assert verify_password(password, user_to_create.hashed_password)

    result = await user_to_create.write_user()
    return result


@user_cli.command(help="Add new user")
def create(
    project: Annotated[
        Path, typer.Option(exists=True, help="The path of the project to run")
    ],
):
    initialise_pangloss_application(get_project_settings(str(project)))

    print("[green bold]Creating a new user[/green bold]")
    username = typer.prompt("Username", type=str)

    _, email = get_email()

    password = str(
        typer.prompt(
            "Password",
            type=str,
            confirmation_prompt="Repeat password to confirm",
            hide_input=True,
        )
    )

    admin = typer.confirm("Make admin?")

    username = asyncio.run(
        create_user(
            username=username,
            email=email,
            password=password.strip(),
            admin=admin,
        )
    )

    print(f"\n[green bold]Done! Created user '{username}' [/green bold]")
