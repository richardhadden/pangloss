import os
import subprocess
import typing
from pathlib import Path

import typer
from cookiecutter.exceptions import OutputDirExistsException
from cookiecutter.main import cookiecutter
from rich import print
from rich.panel import Panel

# from pangloss.model_setup.model_manager import ModelManager
from pangloss.cli.users import user_cli
from pangloss.cli.utils import get_project_path
from pangloss.exceptions import PanglossInitialisationError

# from pangloss.types_generation import type_generation_cli
# from pangloss.translation import translation_cli
from pangloss.indexes import install_indexes_and_constraints
from pangloss.initialisation import get_project_settings
from pangloss.neo4j.database import initialise_database_driver

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")

project_path = get_project_path()

if not project_path:
    raise PanglossInitialisationError(
        "No Pangloss Project specified in pyproject.toml or via --project flag"
    )


cli_app = typer.Typer(
    add_completion=False,
    help="Pangloss CLI",
    name="Pangloss CLI",
)

cli_app.add_typer(user_cli, name="users")


@cli_app.command(help="Create new project")
def createapp(app_name: typing.Annotated[str, typer.Argument()]):
    context = {"folder_name": app_name}
    try:
        cookiecutter(
            os.path.join(TEMPLATES_DIR, "app"),
            extra_context=context,
            no_input=True,
        )
    except OutputDirExistsException:
        print(
            "\n",
            Panel(
                f"[bold red]App creation failed:[/bold red] Folder [bold blue]{context['folder_name']}[/bold blue] already exists.",
                title="Creating Pangloss app",
                subtitle="😡",
                subtitle_align="right",
            ),
            "\n",
        )
    else:
        print(
            "\n",
            Panel(
                (
                    f"[bold green]App successfully created:[/bold green] Pangloss app [bold blue]{context['folder_name']}[/bold blue] created successfully!"
                    f'\n\nGo to your project [blue]settings.py[/blue] and add [blue]"{context["folder_name"]}"[/blue] to [blue]Settings.INSTALLED_APPS[/blue]:'
                    f"\n\nThen go to [blue]{context['folder_name']}/models.py[/blue] to add some models"
                ),
                title="Creating Pangloss project",
                subtitle="🍹",
                subtitle_align="right",
            ),
            "\n",
        )


@cli_app.command(help="Create new project")
def createproject(project_name: typing.Annotated[str, typer.Argument()]):
    context = {"folder_name": project_name}
    try:
        cookiecutter(
            os.path.join(TEMPLATES_DIR, "project"),
            extra_context=context,
            no_input=True,
        )
    except OutputDirExistsException:
        print(
            "\n",
            Panel(
                f"[bold red]Project creation failed:[/bold red] Folder [bold blue]{context['folder_name']}[/bold blue] already exists.",
                title="Creating Pangloss project",
                subtitle="😡",
                subtitle_align="right",
            ),
            "\n",
        )
    else:
        print(
            "\n",
            Panel(
                (
                    f"[bold green]Project successfully created:[/bold green] Pangloss project [bold blue]{context['folder_name']}[/bold blue] created successfully!"
                    f"\n\nGo to [blue]{context['folder_name']}/settings.py[/blue] to configure the database"
                    f"\n\nThen run [deep_pink4]pangloss run {context['folder_name']}[/deep_pink4] to run the development server"
                ),
                title="Creating Pangloss project",
                subtitle="🍹",
                subtitle_align="right",
            ),
            "\n",
        )


Project = typing.Annotated[
    Path, typer.Option(exists=True, help="The path of the project to run")
]


@cli_app.command(help="Starts development server")
def run():
    settings = get_project_settings(str(project_path))
    reload_watch_list = ["--reload-dir", project_path]
    for installed_app in settings.INSTALLED_APPS:
        m = __import__(installed_app)

        reload_watch_list.append("--reload-dir")
        reload_watch_list.append(m.__path__[0])

    panel = Panel(
        (
            f"Autoreloading on!\n\n   Watching project: [bold green]{str(project_path)}[/bold green]\n   "
            f"Watching installed apps: {', '.join(f'[bold blue]{a}[/bold blue]' for a in settings.INSTALLED_APPS)}"
        ),
        title="📜 Starting Pangloss development server!",
        subtitle="(tally ho!)",
        subtitle_align="right",
    )
    print("\n\n", panel, "\n\n")
    sc_command = [
        "uvicorn",
        f"{str(project_path)}.main:app",
        "--lifespan",
        "on",
        "--reload",
        *reload_watch_list,
    ]
    subprocess.call(sc_command)


@cli_app.command()
def setup_database():
    install_indexes_and_constraints()


try:
    settings = get_project_settings(project_path)
except PanglossInitialisationError:
    print("Cannot find settings")
try:
    initialise_database_driver(settings)
    for app in settings.INSTALLED_APPS:
        __import__(f"{app}.models")
        try:
            __import__(f"{app}.background_tasks")
        except ModuleNotFoundError:
            pass
        try:
            m = __import__(f"{app}.cli")
            c = m.cli.__dict__.get("cli")
            if c:
                cli_app.add_typer(c, name=c.info.name)
        except ModuleNotFoundError:
            raise PanglossInitialisationError(
                f"Could not find module {app} declared in {project_path}.settings.INSTALLED_APPS"
            )
except PanglossInitialisationError:
    print("Cannot start app")


def cli():
    """Initialises the Typer-based CLI by checking installed app folders
    for a cli.py file and finding Typer apps inside."""

    # ModelManager.initialise_models(depth=3)
    return cli_app()
