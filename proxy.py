import os
from io import StringIO
from aiohttp import web, ClientSession
from bs4 import BeautifulSoup

routes = web.RouteTableDef()


@routes.get("/")
async def index(request):
    async with ClientSession() as session:
        res = await session.get(
            "https://www.cronachemaceratesi.it/",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0"
            },
        )

        document = BeautifulSoup(await res.text())
    mainbody = rebuildpage(document, id="primaryTopWrapper")

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
            f"https://www.cronachemaceratesi.it/{year}/{month}/{day}/{slug}/{slugid}",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": "https://www.cronachemaceratesi.it",
            },
        )

        document = BeautifulSoup(await res.text())
    mainbody = rebuildpage(document, id="contenuto_articolo")
    return web.Response(text=str(mainbody), content_type="text/html")


def rebuildpage(document, **kwargs):
    newdoc = BeautifulSoup("<html><head></head><body></body></html>")

    mainbody = document.find(**kwargs)
    for link in mainbody.find_all("a"):
        href = link.get("href")
        if href.startswith("https://www.cronachemaceratesi.it/"):
            link["href"] = href.replace("https://www.cronachemaceratesi.it/", "/")
    for banner in mainbody.find_all(class_="banner"):
        banner.extract()
    for script in mainbody.find_all("script"):
        script.extract()
    head = document.html.head
    for style in head.find_all("link"):
        newdoc.html.head.append(style)
    for style in head.find_all("style"):
        newdoc.html.head.append(style)
    newdoc.html.body.insert(1, mainbody)
    return newdoc


app = web.Application()
app.add_routes(routes)
web.run_app(app, port=int(os.environ.get("PORT", 8080)))
