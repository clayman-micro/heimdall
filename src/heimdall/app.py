from typing import Optional

import config  # type: ignore
from aiohttp import ClientSession, ClientTimeout, web
from aiohttp_micro import (  # type: ignore
    AppConfig as BaseConfig,
    setup as setup_micro,
    setup_logging,
    setup_metrics,
)


class ServiceConfig(config.Config):
    host = config.StrField()
    backend = config.StrField()


class ServicesConfig(config.Config):
    shortner = config.NestedField[ServiceConfig](ServiceConfig)
    wallet = config.NestedField[ServiceConfig](ServiceConfig)


class AppConfig(BaseConfig):
    passport = config.NestedField[ServiceConfig](ServiceConfig)
    services = config.NestedField[ServicesConfig](ServicesConfig)


async def remote(host: str, request: web.Request, access_token: Optional[str] = None) -> web.Response:
    body = None
    if request.can_read_body:
        body = await request.read()

    url = "".join(("http://", host, str(request.rel_url)))

    headers = dict(request.headers)
    if access_token:
        headers["X-ACCESS-TOKEN"] = access_token

    request.app["logger"].debug(
        "Call remote service",
        host=host,
        cookies=request.cookies,
        # headers=headers,
        method=request.method,
        url=request.rel_url,
        body=body,
    )

    async with ClientSession() as session:
        async with session.request(
            request.method, url, headers=headers, data=body, timeout=ClientTimeout(total=60),
        ) as resp:
            raw = await resp.read()

            request.app["logger"].debug(
                "Receive remote service response",
                host=host,
                cookies=request.cookies,
                # headers=headers,
                method=request.method,
                url=request.rel_url,
            )

    return web.Response(body=raw, status=resp.status, headers=resp.headers)


async def fetch_access_token(request: web.Request, timeout: ClientTimeout) -> Optional[str]:
    config: AppConfig = request.app["config"]
    logger = request.app["logger"]

    access_token = None

    if request.cookies:
        url = f"http://{config.passport.backend}/api/tokens/access"

        logger.debug(
            "Fetch access token",
            cookies=request.cookies,
            headers=request.headers,
            host=request.host,
            method=request.method,
            url=request.rel_url,
        )

        async with ClientSession(cookies=request.cookies) as session:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    access_token = resp.headers.get("X-ACCESS-TOKEN", None)
                else:
                    logger.error("Attempt to fetch access token failed")

    return access_token


async def proxy(request: web.Request) -> web.Response:
    config: AppConfig = request.app["config"]
    logger = request.app["logger"]

    logger.debug(
        "Handle request",
        cookies=request.cookies,
        headers=request.headers,
        host=request.host,
        method=request.method,
        url=request.rel_url,
    )

    access_token = request.headers.get("X-ACCESS-TOKEN", None)

    if request.host == config.passport.host:
        response = await remote(config.passport.backend, request)
    elif request.host in request.app["services"]:
        if not access_token:
            access_token = await fetch_access_token(request, timeout=ClientTimeout(total=60))

        response = await remote(request.app["services"][request.host], request, access_token=access_token,)
    else:
        logger.error(
            "Attempt to call unknown service", host=request.host, url=request.rel_url,
        )
        raise web.HTTPBadGateway()

    return response


def init(app_name: str, config: AppConfig) -> web.Application:
    app = web.Application()

    services = {}
    for service_name in ("shortner", "wallet"):
        service = getattr(config.services, service_name, None)
        if service:
            services[service.host] = service.backend

    app["services"] = services

    setup_micro(app, app_name, config)

    setup_logging(app)
    setup_metrics(app)

    app.router.add_route("*", "/{path:.*}", proxy)

    return app
