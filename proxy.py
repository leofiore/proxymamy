import os
import copy
from io import StringIO
from aiohttp import web, ClientSession
from bs4 import BeautifulSoup, Tag, NavigableString
import cssutils

routes = web.RouteTableDef()

TARGET_URL = os.environ.get("TARGET_URL")
CACHEABLE_URLS = os.environ.get("CACHEABLE_URLS", "").split(" ")


@routes.get("/")
async def index(request):
    async with ClientSession() as session:
        res = await session.get(
            TARGET_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0"
            },
        )

        document = BeautifulSoup(await res.text(), features="lxml")
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
            f"{TARGET_URL}/{year}/{month}/{day}/{slug}/{slugid}",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )

        document = BeautifulSoup(await res.text(), features="lxml")
    mainbody = rebuildpage(document, id="contenuto_articolo")
    return web.Response(text=str(mainbody), content_type="text/html")


@routes.get("/__CACHE__/{cssdoc:.*.css}")
async def cssdocuments(request):
    cssdoc = request.match_info["cssdoc"]
    async with ClientSession() as session:
        res = await session.get(
            cssdoc,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )
        sheet = await res.text()
    for cacheable in CACHEABLE_URLS + [TARGET_URL]:
        sheet = sheet.replace(cacheable, f"/__CACHE__/{cacheable}")
    return web.Response(body=sheet, content_type="text/css")


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


@routes.get("/__CACHE__/{remote:.*}")
async def wp_assets(request):
    remote = request.match_info["remote"]
    async with ClientSession() as session:
        res = await session.get(
            remote,
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
    newdoc = BeautifulSoup(
        "<html><head></head><body></body></html>",
        features="lxml",
    )

    mainbody = document.find(**kwargs)
    rewrite_urls(mainbody)
    reconciliate_tree(newdoc.html.body, mainbody, document.find("body"))

    for banner in mainbody.find_all(class_="banner"):
        banner.extract()
    for script in mainbody.find_all("script"):
        script.extract()
    head = document.html.head

    for link in head.find_all("link"):
        newdoc.html.head.append(link)
    for style in head.find_all("style"):
        newdoc.html.head.append(style)

    rewrite_urls(newdoc.html.head)

    return newdoc


def clone(node):
    if isinstance(node, NavigableString):
        return type(node)(node)
    new = Tag(None, node.builder, node.name, node.namespace, node.nsprefix)
    new.attrs = dict(node.attrs)
    for attr in ("can_be_empty_element", "hidden"):
        setattr(new, attr, getattr(node, attr))
    return new


def reconciliate_tree(new, target, original):
    if not isinstance(original, Tag):
        return
    if not isinstance(new, Tag):
        return
    for child in original.children:
        if child == target:
            new.append(child)
            return
        if child.name not in ["script", "iframe"]:
            newchild = clone(child)
            new.append(newchild)
        reconciliate_tree(newchild, target, child)


def rewrite_urls(tree):

    for link in tree.find_all("a"):
        href = link.get("href")
        if href.startswith(TARGET_URL):
            link["href"] = href.replace(TARGET_URL, "")
            continue
        for cacheable in CACHEABLE_URLS:
            if href.startswith(cacheable):
                link["href"] = href.replace(cacheable, f"/__CACHE__/{cacheable}")
                break

    for img in tree.find_all("img"):
        src = img.get("src")
        if src.startswith(TARGET_URL):
            img["src"] = f"/__CACHE__/{src}"
        for cacheable in CACHEABLE_URLS:
            if src.startswith(cacheable):
                img["src"] = src.replace(cacheable, f"/__CACHE__/{cacheable}")
        srcset = img.get("srcset")

        if srcset is not None:
            for cacheable in CACHEABLE_URLS:
                img["srcset"] = srcset.replace(cacheable, f"/__CACHE__/{cacheable}")
            img["srcset"] = srcset.replace(TARGET_URL, "")

    for link in tree.find_all("link"):
        href = link.get("href")
        if href.startswith(TARGET_URL):
            link["href"] = f"/__CACHE__/{href}"
            continue
        for cacheable in CACHEABLE_URLS:
            if href.startswith(cacheable):
                link["href"] = href.replace(cacheable, f"/__CACHE__/{cacheable}")
                break


app = web.Application()
app.add_routes(routes)
web.run_app(app, port=int(os.environ.get("PORT", 8080)))
