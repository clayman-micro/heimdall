from pathlib import Path

import click
import structlog  # type: ignore
import uvloop  # type: ignore
from aiohttp_micro.management.server import server  # type: ignore
from config import (  # type: ignore
    ConsulConfig,
    EnvValueProvider,
    FileValueProvider,
    load,
    load_from_file,
)

from heimdall.app import AppConfig, init


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)


@click.group()
@click.option("--conf-dir", default=None)
@click.option("--debug", default=False, is_flag=True)
@click.pass_context
def cli(ctx, conf_dir: str = None, debug: bool = False):
    uvloop.install()

    consul_config = ConsulConfig()
    load(consul_config, providers=[EnvValueProvider()])

    if conf_dir:
        conf_path = Path(conf_dir)
    else:
        conf_path = Path.cwd()

    config = AppConfig(defaults={"consul": consul_config, "debug": debug})
    load(config, providers=[FileValueProvider(conf_path), EnvValueProvider()])

    load_from_file(config, path=conf_path / "config.json")

    app = init("heimdall", config)

    ctx.obj["app"] = app
    ctx.obj["config"] = config


cli.add_command(server, name="server")


if __name__ == "__main__":
    cli(obj={})
