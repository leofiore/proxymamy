import os
from io import StringIO
from aiohttp import web, ClientSession
from bs4 import BeautifulSoup

routes = web.RouteTableDef()

TARGET_URL = os.environ.get("TARGET_URL")


@routes.get("/")
async def index(request):
    async with ClientSession() as session:
        res = await session.get(
            TARGET_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0"
            },
        )

        document = BeautifulSoup(await res.text())
    mainbody = rebuildpage(document, id="primaryTopWrapper")
    asyncio

    return web.Response(text=str(mainbody), content_type="text/html")


@routes.get("/{year}/{month}/{day}/{slug}/{slugid}/")
async def article(request):
    year, month, day, slug, slugid = (
        request.match_info["year"],
        request.match_info["month"],
        request.match_info["day"],
        request.match_info["slug"],
        request.match_info["slugid"],
    )
    async with ClientSession() as session:
        res = await session.get(
            f"{TARGET_URL}/{year}/{month}/{day}/{slug}/{slugid}",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )

        document = BeautifulSoup(await res.text())
    mainbody = rebuildpage(document, id="contenuto_articolo")
    return web.Response(text=str(mainbody), content_type="text/html")


@routes.get("/{cssdoc:.*.css}")
async def cssdocuments(request):
    ...


@routes.get("/{wpsomething:wp-.*}/{asset:.*}")
async def wp_assets(request):
    asset = request.match_info["asset"]
    wp_path = request.match_info["wpsomething"]
    async with ClientSession() as session:
        res = await session.get(
            f"{TARGET_URL}/{wp_path}/{asset}",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )
        body = await res.read()
        content_type = res.content_type
    return web.Response(body=body, content_type=content_type)


@routes.get("/robots.txt")
async def robots(request):
    return web.Response(text="User-agent:*\nDisallow: /")


def rebuildpage(document, **kwargs):
    newdoc = BeautifulSoup("<html><head></head><body></body></html>")

    mainbody = document.find(**kwargs)

    for link in mainbody.find_all("a"):
        href = link.get("href")
        if href.startswith(TARGET_URL):
            link["href"] = href.replace(TARGET_URL, "")

    for img in mainbody.find_all("img"):
        src = img.get("src")
        if src.startswith(TARGET_URL):
            img["src"] = src.replace(TARGET_URL, "")
            srcset = img.get("srcset")
            if srcset is not None:
                img["srcset"] = srcset.replace(TARGET_URL, "")

    for banner in mainbody.find_all(class_="banner"):
        banner.extract()
    for script in mainbody.find_all("script"):
        script.extract()
    head = document.html.head

    for style in head.find_all("link"):
        newdoc.html.head.append(style)

    for style in head.find_all("style"):
        href = style.get("href")
        if href and href.startswith(TARGET_URL):
            style["href"] = href.replace(TARGET_URL, "/")
        newdoc.html.head.append(style)

    newdoc.html.body.insert(1, mainbody)
    return newdoc


app = web.Application()
app.add_routes(routes)
web.run_app(app, port=int(os.environ.get("PORT", 8080)))
